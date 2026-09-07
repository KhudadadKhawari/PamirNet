import base64
import hashlib
import json
import socket
import ssl
import struct
import urllib.error
import urllib.request


class MikroTikError(RuntimeError):
    pass


def _encode_length(length: int) -> bytes:
    if length < 0x80:
        return bytes([length])
    if length < 0x4000:
        return struct.pack(">H", length | 0x8000)
    if length < 0x200000:
        value = length | 0xC00000
        return bytes([(value >> 16) & 0xFF, (value >> 8) & 0xFF, value & 0xFF])
    if length < 0x10000000:
        return struct.pack(">I", length | 0xE0000000)
    return b"\xF0" + struct.pack(">I", length)


def _read_exact(sock, count: int) -> bytes:
    data = b""
    while len(data) < count:
        chunk = sock.recv(count - len(data))
        if not chunk:
            raise MikroTikError("RouterOS API connection closed unexpectedly.")
        data += chunk
    return data


def _decode_length(sock) -> int:
    first = _read_exact(sock, 1)[0]
    if first < 0x80:
        return first
    if first < 0xC0:
        return ((first & 0x3F) << 8) | _read_exact(sock, 1)[0]
    if first < 0xE0:
        rest = _read_exact(sock, 2)
        return ((first & 0x1F) << 16) | (rest[0] << 8) | rest[1]
    if first < 0xF0:
        rest = _read_exact(sock, 3)
        return (
            ((first & 0x0F) << 24)
            | (rest[0] << 16)
            | (rest[1] << 8)
            | rest[2]
        )
    if first == 0xF0:
        return struct.unpack(">I", _read_exact(sock, 4))[0]
    raise MikroTikError("Invalid RouterOS API word length.")


def _write_sentence(sock, words: list[str]):
    payload = b""
    for word in words:
        encoded = word.encode()
        payload += _encode_length(len(encoded)) + encoded
    sock.sendall(payload + b"\x00")


def _read_sentence(sock) -> list[str]:
    words = []
    while True:
        length = _decode_length(sock)
        if length == 0:
            return words
        words.append(_read_exact(sock, length).decode(errors="replace"))


def _attributes(sentence: list[str]) -> dict:
    result = {}
    for word in sentence[1:]:
        if word.startswith("="):
            _, key, value = word.split("=", 2)
            result[key] = value
    return result


class MikroTikClient:
    def __init__(self, router, timeout: float = 4.0):
        self.router = router
        self.timeout = timeout

    def resource(self) -> dict:
        if self.router.api_protocol == self.router.APIProtocol.REST:
            return self._rest_resource()
        ssl_enabled = self.router.api_protocol == self.router.APIProtocol.API_SSL
        return self._api_resource(ssl_enabled=ssl_enabled)

    def _rest_resource(self) -> dict:
        url = (
            f"https://{self.router.tunnel_ip}:{self.router.api_port}"
            "/rest/system/resource"
        )
        credentials = f"{self.router.api_username}:{self.router.get_api_password()}".encode()
        request = urllib.request.Request(
            url,
            headers={
                "Authorization": "Basic " + base64.b64encode(credentials).decode(),
                "Accept": "application/json",
            },
        )
        context = ssl.create_default_context()
        if not self.router.api_tls_verify:
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
        try:
            with urllib.request.urlopen(
                request,
                timeout=self.timeout,
                context=context,
            ) as response:
                payload = json.loads(response.read().decode())
        except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
            raise MikroTikError(f"RouterOS REST request failed: {exc}") from exc
        if isinstance(payload, list):
            return payload[0] if payload else {}
        return payload

    def _api_resource(self, *, ssl_enabled: bool) -> dict:
        address = (self.router.tunnel_ip, self.router.api_port)
        raw_sock = socket.create_connection(address, timeout=self.timeout)
        sock = raw_sock
        try:
            if ssl_enabled:
                context = ssl.create_default_context()
                if not self.router.api_tls_verify:
                    context.check_hostname = False
                    context.verify_mode = ssl.CERT_NONE
                sock = context.wrap_socket(raw_sock, server_hostname=self.router.tunnel_ip)
            self._login(sock)
            _write_sentence(sock, ["/system/resource/print"])
            records = self._collect(sock)
            return records[0] if records else {}
        except (OSError, ssl.SSLError) as exc:
            raise MikroTikError(f"RouterOS API request failed: {exc}") from exc
        finally:
            try:
                sock.close()
            except OSError:
                pass

    def _login(self, sock):
        username = self.router.api_username
        password = self.router.get_api_password()
        _write_sentence(sock, ["/login", f"=name={username}", f"=password={password}"])
        sentence = _read_sentence(sock)
        if not sentence:
            raise MikroTikError("Empty RouterOS API login response.")
        attrs = _attributes(sentence)
        if sentence[0] == "!done" and "ret" not in attrs:
            return
        challenge = attrs.get("ret")
        if challenge:
            challenge_bytes = bytes.fromhex(challenge)
            digest = hashlib.md5(
                b"\x00" + password.encode() + challenge_bytes
            ).hexdigest()
            _write_sentence(
                sock,
                ["/login", f"=name={username}", f"=response=00{digest}"],
            )
            sentence = _read_sentence(sock)
            if sentence and sentence[0] == "!done":
                return
        raise MikroTikError("RouterOS API authentication failed.")

    def _collect(self, sock) -> list[dict]:
        records = []
        while True:
            sentence = _read_sentence(sock)
            if not sentence:
                continue
            if sentence[0] == "!re":
                records.append(_attributes(sentence))
            elif sentence[0] == "!done":
                return records
            elif sentence[0] in {"!trap", "!fatal"}:
                message = _attributes(sentence).get("message", "RouterOS API error")
                raise MikroTikError(message)
