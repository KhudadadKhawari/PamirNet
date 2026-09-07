import base64
import ipaddress
from dataclasses import dataclass

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
from django.conf import settings


class WireGuardConfigurationError(RuntimeError):
    pass


@dataclass(frozen=True)
class WireGuardKeyPair:
    private_key: str
    public_key: str


def generate_keypair() -> WireGuardKeyPair:
    private = X25519PrivateKey.generate()
    private_raw = private.private_bytes(
        serialization.Encoding.Raw,
        serialization.PrivateFormat.Raw,
        serialization.NoEncryption(),
    )
    public_raw = private.public_key().public_bytes(
        serialization.Encoding.Raw,
        serialization.PublicFormat.Raw,
    )
    return WireGuardKeyPair(
        private_key=base64.b64encode(private_raw).decode(),
        public_key=base64.b64encode(public_raw).decode(),
    )


def allocate_tunnel_ip() -> str:
    from .models import Router

    network = ipaddress.ip_network(settings.WIREGUARD_CLIENT_SUBNET, strict=False)
    server_ip = ipaddress.ip_interface(settings.WIREGUARD_SERVER_ADDRESS).ip
    used = set(Router.objects.values_list("tunnel_ip", flat=True))

    for index, host in enumerate(network.hosts(), start=1):
        if index < 10 or host == server_ip:
            continue
        candidate = str(host)
        if candidate not in used:
            return candidate
    raise WireGuardConfigurationError("WireGuard client subnet has no free addresses.")


def _quote(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _management_service(router) -> list[str]:
    server_ip = str(ipaddress.ip_interface(settings.WIREGUARD_SERVER_ADDRESS).ip)
    if router.api_protocol == router.APIProtocol.REST:
        return [
            (
                "/ip service set www-ssl disabled=no "
                f"address={server_ip}/32 port={router.api_port}"
            ),
            "# REST requires RouterOS 7 and a usable HTTPS certificate on the router.",
        ]
    service = "api-ssl" if router.api_protocol == router.APIProtocol.API_SSL else "api"
    return [
        (
            f"/ip service set {service} disabled=no "
            f"address={server_ip}/32 port={router.api_port}"
        )
    ]


def build_provisioning(
    router,
    client_private_key: str,
    old_public_key: str | None = None,
) -> dict:
    server_public_key = settings.WIREGUARD_SERVER_PUBLIC_KEY.strip()
    endpoint = settings.WIREGUARD_ENDPOINT.strip()
    if not server_public_key or not endpoint:
        raise WireGuardConfigurationError(
            "WIREGUARD_SERVER_PUBLIC_KEY and WIREGUARD_ENDPOINT must be configured "
            "before provisioning routers."
        )

    server_ip = str(ipaddress.ip_interface(settings.WIREGUARD_SERVER_ADDRESS).ip)
    client_ip = router.tunnel_ip
    radius_secret = router.get_radius_secret()
    interface = settings.WIREGUARD_INTERFACE
    port = settings.WIREGUARD_PORT

    commands = [
        "# PamirNet router provisioning - RouterOS 7+",
        (
            "/interface wireguard add name=pamirnet-wg "
            f"private-key={_quote(client_private_key)} listen-port=13231"
        ),
        (
            f"/ip address add address={client_ip}/32 interface=pamirnet-wg "
            f"comment={_quote('PamirNet tunnel')}"
        ),
        (
            "/interface wireguard peers add interface=pamirnet-wg "
            f"public-key={_quote(server_public_key)} "
            f"endpoint-address={_quote(endpoint)} endpoint-port={port} "
            f"allowed-address={server_ip}/32 persistent-keepalive=25s "
            f"comment={_quote('PamirNet VPS')}"
        ),
        (
            "/ip firewall filter add chain=input action=accept "
            f"in-interface=pamirnet-wg src-address={server_ip} "
            f"comment={_quote('PamirNet management')} place-before=0"
        ),
        (
            f"/radius add address={server_ip} secret={_quote(radius_secret)} "
            "service=hotspot,ppp authentication-port=1812 accounting-port=1813 "
            f"timeout=1s comment={_quote('PamirNet')}"
        ),
        "/radius incoming set accept=yes port=3799",
        "/ppp aaa set use-radius=yes accounting=yes interim-update=1m",
        "/ip hotspot profile set [find] use-radius=yes",
        *_management_service(router),
    ]
    routeros_script = "\n".join(commands) + "\n"

    apply_commands = []
    if old_public_key:
        apply_commands.append(
            f"sudo wg set {interface} peer {old_public_key} remove"
        )
    apply_commands.append(
        f"sudo wg set {interface} peer {router.wireguard_public_key} "
        f"allowed-ips {client_ip}/32"
    )

    return {
        "wireguard_private_key": client_private_key,
        "wireguard_public_key": router.wireguard_public_key,
        "tunnel_ip": client_ip,
        "server_address": server_ip,
        "server_public_key": server_public_key,
        "server_endpoint": endpoint,
        "server_port": port,
        "radius_server": server_ip,
        "radius_secret": radius_secret,
        "routeros_script": routeros_script,
        "server_peer_config": (
            f"[Peer]\nPublicKey = {router.wireguard_public_key}\n"
            f"AllowedIPs = {client_ip}/32\n"
        ),
        "server_apply_commands": apply_commands,
        "private_key_notice": (
            "The WireGuard private key is returned only in this response. "
            "Store the provisioning output securely."
        ),
    }
