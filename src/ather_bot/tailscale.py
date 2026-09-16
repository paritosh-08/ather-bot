from __future__ import annotations

import json
import os
import re
import subprocess
import time
from pathlib import Path
from typing import Any

import requests

from .config import Paths

SOCKS_PORT = 1055
LOGIN_RE = re.compile(r"https://login\.tailscale\.com/\S+")


def _binary(paths: Paths, name: str):
    binary = paths.root / "bin" / name
    if not binary.exists():
        raise RuntimeError(
            "Tailscale binaries are missing; run scripts/download-tailscale.sh first."
        )
    return binary


def command(
    paths: Paths,
    *args: str,
    timeout: int = 30,
) -> subprocess.CompletedProcess[str]:
    socket = paths.tailscale / "tailscaled.sock"
    return subprocess.run(
        [str(_binary(paths, "tailscale")), f"--socket={socket}", *args],
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def start(paths: Paths) -> dict[str, Any]:
    paths.tailscale.mkdir(parents=True, exist_ok=True, mode=0o700)
    socket = paths.tailscale / "tailscaled.sock"
    if socket.exists():
        current = status(paths)
        if current.get("running"):
            return {"started": False, **current}
        socket.unlink(missing_ok=True)
    log_path = paths.tailscale / "tailscaled.log"
    log = log_path.open("ab")
    process = subprocess.Popen(
        [
            str(_binary(paths, "tailscaled")),
            "--state=mem:",
            f"--socket={socket}",
            "--tun=userspace-networking",
            f"--socks5-server=127.0.0.1:{SOCKS_PORT}",
        ],
        stdin=subprocess.DEVNULL,
        stdout=log,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    (paths.tailscale / "pid").write_text(str(process.pid), encoding="utf-8")
    os.chmod(paths.tailscale / "pid", 0o600)
    for _ in range(50):
        if socket.exists():
            return {"started": True, "pid": process.pid, "socket": str(socket)}
        if process.poll() is not None:
            break
        time.sleep(0.1)
    raise RuntimeError(f"tailscaled did not become ready; inspect {log_path}")


def login_url(paths: Paths) -> dict[str, Any]:
    try:
        result = command(
            paths,
            "up",
            "--accept-dns=false",
            "--accept-routes=false",
            "--timeout=5s",
            timeout=10,
        )
    except subprocess.TimeoutExpired as exc:
        def text(value: bytes | str | None) -> str:
            return value.decode(errors="replace") if isinstance(value, bytes) else (value or "")
        output = text(exc.stdout) + "\n" + text(exc.stderr)
    else:
        output = result.stdout + "\n" + result.stderr
        if result.returncode == 0:
            return {"authorized": True}
    match = LOGIN_RE.search(output)
    if not match:
        raise RuntimeError("Tailscale did not return a login URL.")
    return {"authorized": False, "login_url": match.group(0).rstrip(".")}


def set_exit_node(paths: Paths, ip: str) -> dict[str, Any]:
    if not re.fullmatch(r"(?:\d{1,3}\.){3}\d{1,3}", ip):
        raise ValueError("Exit node must be selected by its Tailscale IPv4 address.")
    available = {node["ip"] for node in status(paths).get("exit_nodes", [])}
    if ip not in available:
        raise ValueError("That address is not an advertised Tailscale exit node.")
    result = command(
        paths,
        "set",
        f"--exit-node={ip}",
        "--exit-node-allow-lan-access=false",
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip()[:300])
    return {"configured": True, "exit_node": ip, "socks_url": socks_url()}


def status(paths: Paths) -> dict[str, Any]:
    try:
        result = command(paths, "status", "--json")
    except (OSError, RuntimeError, subprocess.TimeoutExpired):
        return {"running": False}
    if result.returncode:
        return {"running": False, "error": result.stderr.strip()[:200]}
    payload = json.loads(result.stdout)
    peers = []
    for peer in payload.get("Peer", {}).values():
        if peer.get("ExitNodeOption"):
            peers.append(
                {
                    "name": peer.get("HostName"),
                    "ip": (peer.get("TailscaleIPs") or [""])[0],
                    "online": peer.get("Online", False),
                }
            )
    return {
        "running": True,
        "backend_state": payload.get("BackendState"),
        "exit_nodes": peers,
    }


def stop(paths: Paths) -> dict[str, Any]:
    pid_path = paths.tailscale / "pid"
    try:
        pid = int(pid_path.read_text(encoding="utf-8"))
        cmdline = (Path("/proc") / str(pid) / "cmdline").read_bytes().replace(b"\\0", b" ")
    except (OSError, ValueError):
        pid_path.unlink(missing_ok=True)
        return {"stopped": False, "reason": "not_running"}
    expected = str(paths.root / "bin" / "tailscaled").encode()
    if expected not in cmdline:
        raise RuntimeError("Refusing to stop an unrelated process.")
    os.kill(pid, 15)
    for _ in range(50):
        if not (Path("/proc") / str(pid)).exists():
            break
        time.sleep(0.1)
    else:
        raise RuntimeError("tailscaled did not stop cleanly.")
    pid_path.unlink(missing_ok=True)
    (paths.tailscale / "tailscaled.sock").unlink(missing_ok=True)
    return {"stopped": True}


def proof() -> dict[str, Any]:
    direct = requests.get("https://ipinfo.io/json", timeout=20).json()
    ather = requests.get(
        "https://cerberus.ather.io/",
        proxies={"http": socks_url(), "https": socks_url()},
        timeout=30,
    )
    route = subprocess.run(
        ["ip", "route", "show", "default"],
        check=False,
        capture_output=True,
        text=True,
        timeout=5,
    ).stdout.strip()
    return {
        "direct": {"ip": direct.get("ip"), "country": direct.get("country")},
        "ather_via_socks_http_status": ather.status_code,
        "default_route": route,
    }


def socks_url() -> str:
    return f"socks5h://127.0.0.1:{SOCKS_PORT}"
