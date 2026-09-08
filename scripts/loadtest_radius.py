#!/usr/bin/env python3
"""Synthetic load test for PamirNet's internal RADIUS REST endpoints.

Run only against staging or an isolated test tenant. Accounting mode writes real
session/usage data and can trigger FUP policies.
"""

from __future__ import annotations

import argparse
import json
import statistics
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--token", required=True)
    parser.add_argument("--nas-ip", required=True)
    parser.add_argument("--username")
    parser.add_argument("--usernames-file")
    parser.add_argument("--mode", choices=["authorize", "accounting", "mixed"], default="mixed")
    parser.add_argument("--requests", type=int, default=1000)
    parser.add_argument("--workers", type=int, default=50)
    parser.add_argument("--timeout", type=float, default=5.0)
    return parser.parse_args()


def load_usernames(args):
    if args.usernames_file:
        values = [line.strip() for line in Path(args.usernames_file).read_text().splitlines()]
        values = [value for value in values if value and not value.startswith("#")]
    elif args.username:
        values = [args.username]
    else:
        raise SystemExit("Provide --username or --usernames-file")
    return values


def percentile(values, q):
    if not values:
        return 0.0
    values = sorted(values)
    index = min(len(values) - 1, max(0, round((len(values) - 1) * q)))
    return values[index]


def main():
    args = parse_args()
    usernames = load_usernames(args)
    lock = threading.Lock()
    latencies = []
    failures = []

    def post(path, payload):
        body = json.dumps(payload).encode()
        request = urllib.request.Request(
            args.base_url.rstrip("/") + path,
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "X-PamirNet-Radius-Token": args.token,
            },
        )
        started = time.perf_counter()
        try:
            with urllib.request.urlopen(request, timeout=args.timeout) as response:
                response.read()
                ok = 200 <= response.status < 300
                error = "" if ok else f"HTTP {response.status}"
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            ok = False
            error = str(exc)
        elapsed = (time.perf_counter() - started) * 1000
        with lock:
            latencies.append(elapsed)
            if not ok:
                failures.append(error)
        return ok

    def authorize(index):
        username = usernames[index % len(usernames)]
        query = urllib.parse.urlencode(
            {
                "username": username,
                "packet_src_ip": args.nas_ip,
                "calling_station_id": f"02:00:00:{index // 65536:02X}:{(index // 256) % 256:02X}:{index % 256:02X}",
            }
        )
        return post(f"/api/internal/radius/authorize/?{query}", {})

    def accounting(index):
        username = usernames[index % len(usernames)]
        session_id = f"load-{int(time.time())}-{index}"
        common = {
            "packet_src_ip": args.nas_ip,
            "username": username,
            "acct_session_id": session_id,
            "acct_unique_session_id": f"unique-{session_id}",
            "calling_station_id": f"02:10:00:{index // 65536:02X}:{(index // 256) % 256:02X}:{index % 256:02X}",
            "framed_ip_address": f"10.254.{(index // 250) % 250}.{(index % 250) + 1}",
        }
        if not post("/api/internal/radius/accounting/", common | {"acct_status_type": "Start"}):
            return False
        if not post(
            "/api/internal/radius/accounting/",
            common
            | {
                "acct_status_type": "Interim-Update",
                "acct_input_octets": 16384,
                "acct_output_octets": 65536,
                "acct_session_time": 60,
            },
        ):
            return False
        return post(
            "/api/internal/radius/accounting/",
            common
            | {
                "acct_status_type": "Stop",
                "acct_input_octets": 32768,
                "acct_output_octets": 131072,
                "acct_session_time": 120,
                "acct_terminate_cause": "User-Request",
            },
        )

    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = []
        for index in range(args.requests):
            if args.mode == "authorize":
                futures.append(pool.submit(authorize, index))
            elif args.mode == "accounting":
                futures.append(pool.submit(accounting, index))
            else:
                futures.append(pool.submit(authorize if index % 2 == 0 else accounting, index))
        successful_jobs = sum(1 for future in as_completed(futures) if future.result())

    elapsed = time.perf_counter() - started
    total_http = len(latencies)
    print(f"mode={args.mode} jobs={args.requests} successful_jobs={successful_jobs}")
    print(f"http_requests={total_http} failures={len(failures)} elapsed={elapsed:.2f}s rps={total_http / max(elapsed, 0.001):.2f}")
    if latencies:
        print(
            "latency_ms "
            f"mean={statistics.mean(latencies):.2f} "
            f"p50={percentile(latencies, 0.50):.2f} "
            f"p95={percentile(latencies, 0.95):.2f} "
            f"p99={percentile(latencies, 0.99):.2f} "
            f"max={max(latencies):.2f}"
        )
    if failures:
        print("sample_failures:")
        for failure in failures[:10]:
            print(f"  - {failure}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
