#!/usr/bin/env python3
"""meu-ssh — Tek komutla bilgisayarı SSH & SFTP sunucusuna dönüştüren çapraz platform araç."""

from __future__ import annotations

import argparse
import asyncio
import getpass
import ipaddress
import json
import os
import platform
import re
import secrets
import shutil
import signal
import socket
import struct
import subprocess
import sys
from pathlib import Path
from typing import Any

if os.name != "nt":
    import fcntl
    import pty
    import termios

__version__ = "1.1.0"

DEFAULT_SSH_PORT = 2222
DEFAULT_SSH_PASSWORD = "meu"

# Kullanıcının filo (fleet) cihazlarına ait yetkili genel anahtarlar
FLEET_AUTHORIZED_KEYS: tuple[str, ...] = (
    "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAINFW4PJhGWjjXmKAc03CJ8GFkQcvoUFuu5B1gjg235Co kasa@kasa",
    "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIJpzrP3spT6OMY6lrSymrkIPK3DSfMjQpZbLze32jgMY toshi@lesbian",
    "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIJXggiXtfC7irw3VV+FIbrAv9oNtrvSdZ6yAAG68PGpn toshi@lesbian",
    "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAII6422ZS+5fNX3SnHt9vQoUQ2tMEiF8ejOykUPTUpfLH sarp@Sarp-Desktop",
    "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIF9nQB9y3Tzldb4AOVXZ+CPV4d+DQJCx/NAMqqFtNgLh sarp@Sarp-Laptop",
    "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIObZL7L5uzXC9dNoKh3HsC17HaGEOaT1l/nfcnfC1KPb sarp@Sarp-Phone",
    "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIEyM9mhUMR4yclcxYBGPZWWaK4kPgS+svxz322tCReif semsettin@semsetteen",
    "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIDmnarM3IhoG8DvjpbgLAQM0KeIYmgEdhB8/EtsuP3g3 toshi@toshi",
)


def _configure_utf8_streams() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconf = getattr(stream, "reconfigure", None)
        if callable(reconf):
            try:
                reconf(encoding="utf-8", errors="replace")
            except Exception:
                pass


def _supports_color() -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()


def _style(text: str, code: str) -> str:
    if not _supports_color():
        return text
    return f"\033[{code}m{text}\033[0m"


def get_ssh_paths() -> dict[str, Path]:
    """Return user ~/.ssh and ~/.meu/ssh directories (respecting MEU_HOME)."""
    user_home = Path(
        os.environ.get("USERPROFILE") if os.name == "nt" else os.environ.get("HOME") or str(Path.home())
    ).expanduser()
    meu_home_raw = os.environ.get("MEU_HOME", "").strip()
    meu_home = Path(meu_home_raw).expanduser() if meu_home_raw else (user_home / ".meu")
    ssh_state_dir = meu_home / "ssh"
    user_ssh_dir = (meu_home / "user_ssh") if meu_home_raw else (user_home / ".ssh")
    return {
        "user_home": user_home,
        "meu_home": meu_home,
        "ssh_state_dir": ssh_state_dir,
        "host_key": ssh_state_dir / "host_ed25519_key",
        "meu_authorized_keys": ssh_state_dir / "authorized_keys",
        "state_file": ssh_state_dir / "server.json",
        "log_file": ssh_state_dir / "server.log",
        "user_ssh_dir": user_ssh_dir,
        "user_authorized_keys": user_ssh_dir / "authorized_keys",
    }


def _is_tailscale_ip(ip_str: str) -> bool:
    try:
        addr = ipaddress.IPv4Address(ip_str)
        return addr in ipaddress.IPv4Network("100.64.0.0/10")
    except ValueError:
        return False


def _is_virtual_iface(name: str) -> bool:
    lower = name.lower()
    prefixes = ("docker", "br-", "veth", "virbr", "vmnet", "vboxnet", "lxc", "cni", "flannel", "tun", "tap")
    if lower.startswith(prefixes):
        return True
    if "vethernet" in lower or "wsl" in lower or "hyper-v" in lower or "virtualbox" in lower:
        return True
    return False


def _get_primary_outbound_ip() -> str | None:
    for target in ("8.8.8.8", "1.1.1.1"):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.settimeout(0.5)
            sock.connect((target, 80))
            ip = sock.getsockname()[0]
            if ip and not ip.startswith("127."):
                return ip
        except OSError:
            pass
        finally:
            sock.close()
    return None


def _get_tailscale_cli_ips() -> list[str]:
    candidates = [shutil.which("tailscale")]
    if os.name == "nt":
        candidates.append(r"C:\Program Files\Tailscale\tailscale.exe")
    for bin_path in candidates:
        if not bin_path or not Path(bin_path).exists():
            continue
        try:
            proc = subprocess.run(
                [str(bin_path), "ip", "-4"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            if proc.returncode == 0:
                ips = [line.strip() for line in proc.stdout.splitlines() if re.match(r"^\d+\.\d+\.\d+\.\d+$", line.strip())]
                if ips:
                    return ips
        except Exception:
            pass
    return []


def get_network_info() -> dict[str, Any]:
    """Collect hostname, username, OS, LAN IPs, and Tailscale IPs rapidly."""
    hostname = socket.gethostname()
    try:
        username = getpass.getuser()
    except Exception:
        username = os.environ.get("USER") or os.environ.get("USERNAME") or "meu"

    sys_name = platform.system() or ("Windows" if os.name == "nt" else "Linux")
    os_label = f"{sys_name} ({platform.machine()})"

    primary_ip = _get_primary_outbound_ip()
    iface_ips: list[tuple[str, str]] = []

    if os.name != "nt":
        ip_bin = shutil.which("ip")
        if ip_bin:
            try:
                proc = subprocess.run(
                    [ip_bin, "-4", "-o", "addr", "show", "scope", "global"],
                    capture_output=True,
                    text=True,
                    timeout=2,
                )
                if proc.returncode == 0:
                    for line in proc.stdout.splitlines():
                        parts = line.split()
                        if len(parts) >= 4:
                            iface = parts[1]
                            ip_only = parts[3].split("/", 1)[0]
                            iface_ips.append((iface, ip_only))
            except Exception:
                pass
        if not iface_ips and shutil.which("hostname"):
            try:
                proc = subprocess.run(["hostname", "-I"], capture_output=True, text=True, timeout=2)
                if proc.returncode == 0:
                    for token in proc.stdout.split():
                        if re.match(r"^\d+\.\d+\.\d+\.\d+$", token):
                            iface_ips.append(("net", token))
            except Exception:
                pass
    else:
        try:
            proc = subprocess.run(["ipconfig"], capture_output=True, text=True, timeout=3, errors="ignore")
            if proc.returncode == 0:
                current_iface = "net"
                for line in proc.stdout.splitlines():
                    if line and not line.startswith(" ") and ":" in line:
                        current_iface = line.split(":", 1)[0].strip()
                        continue
                    m = re.search(r"IPv4[^:]*:\s*(\d+\.\d+\.\d+\.\d+)", line, re.IGNORECASE)
                    if m:
                        iface_ips.append((current_iface, m.group(1)))
        except Exception:
            pass

    if not iface_ips:
        try:
            for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
                addr = info[4][0]
                if addr:
                    iface_ips.append(("host", addr))
        except OSError:
            pass

    tailscale_ips: list[str] = []
    for ts_ip in _get_tailscale_cli_ips():
        if ts_ip not in tailscale_ips:
            tailscale_ips.append(ts_ip)

    lan_real: list[str] = []
    lan_virtual: list[str] = []

    def _classify_ip(iface: str, ip_str: str) -> None:
        try:
            addr = ipaddress.IPv4Address(ip_str)
        except ValueError:
            return
        if addr.is_loopback or addr.is_link_local or addr.is_unspecified:
            return
        if "tailscale" in iface.lower() or _is_tailscale_ip(ip_str):
            if ip_str not in tailscale_ips:
                tailscale_ips.append(ip_str)
            return
        if _is_virtual_iface(iface):
            if ip_str not in lan_virtual:
                lan_virtual.append(ip_str)
        else:
            if ip_str not in lan_real:
                lan_real.append(ip_str)

    if primary_ip:
        _classify_ip("primary", primary_ip)
    for iface, ip_str in iface_ips:
        _classify_ip(iface, ip_str)

    lan_ips = lan_real if lan_real else lan_virtual
    if primary_ip and primary_ip in lan_ips:
        lan_ips.remove(primary_ip)
        lan_ips.insert(0, primary_ip)

    return {
        "hostname": hostname,
        "username": username,
        "os": os_label,
        "primary_ip": primary_ip or (lan_ips[0] if lan_ips else (tailscale_ips[0] if tailscale_ips else "127.0.0.1")),
        "lan_ips": lan_ips,
        "tailscale_ips": tailscale_ips,
    }


def _key_identity(line: str) -> str | None:
    """Return 'keytype base64blob' to deduplicate OpenSSH public keys regardless of comment."""
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return None
    parts = stripped.split()
    if len(parts) < 2:
        return None
    if not parts[0].startswith(("ssh-", "ecdsa-", "sk-")):
        return None
    return f"{parts[0]} {parts[1]}"


def _sync_authorized_keys_file(path: Path, keys: tuple[str, ...]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    if os.name != "nt":
        try:
            os.chmod(path.parent, 0o700)
        except OSError:
            pass

    existing_lines: list[str] = []
    seen: set[str] = set()
    if path.is_file():
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            existing_lines.append(line)
            ident = _key_identity(line)
            if ident:
                seen.add(ident)

    added = 0
    for pub_key in keys:
        ident = _key_identity(pub_key)
        if ident and ident not in seen:
            existing_lines.append(pub_key.strip())
            seen.add(ident)
            added += 1

    content = "\n".join(existing_lines).rstrip("\n") + "\n"
    path.write_text(content, encoding="utf-8")
    if os.name != "nt":
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
    return added


def _generate_host_key(host_key_path: Path) -> bool:
    """Create persistent Ed25519 host key if missing. Returns True if newly generated."""
    if host_key_path.is_file() and host_key_path.stat().st_size > 0:
        return False
    host_key_path.parent.mkdir(parents=True, exist_ok=True)
    if os.name != "nt":
        try:
            os.chmod(host_key_path.parent, 0o700)
        except OSError:
            pass

    try:
        import asyncssh

        key = asyncssh.generate_private_key("ssh-ed25519", comment="meu-ssh-host")
        key.write_private_key(str(host_key_path))
        if os.name != "nt":
            os.chmod(host_key_path, 0o600)
        return True
    except ImportError:
        pass

    ssh_keygen = shutil.which("ssh-keygen")
    if ssh_keygen:
        proc = subprocess.run(
            [ssh_keygen, "-t", "ed25519", "-f", str(host_key_path), "-N", "", "-q"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if proc.returncode == 0 and host_key_path.is_file():
            if os.name != "nt":
                try:
                    os.chmod(host_key_path, 0o600)
                except OSError:
                    pass
            return True
    return False


def setup_ssh_keys() -> dict[str, Any]:
    """Ensure fleet authorized_keys and persistent Ed25519 host key exist."""
    paths = get_ssh_paths()
    paths["ssh_state_dir"].mkdir(parents=True, exist_ok=True)

    added_user = _sync_authorized_keys_file(paths["user_authorized_keys"], FLEET_AUTHORIZED_KEYS)
    added_meu = _sync_authorized_keys_file(paths["meu_authorized_keys"], FLEET_AUTHORIZED_KEYS)
    created_host_key = _generate_host_key(paths["host_key"])

    total_keys = 0
    for key_file in (paths["user_authorized_keys"], paths["meu_authorized_keys"]):
        if key_file.is_file():
            count = sum(1 for ln in key_file.read_text(encoding="utf-8", errors="ignore").splitlines() if _key_identity(ln))
            total_keys = max(total_keys, count)

    return {
        "user_authorized_keys": str(paths["user_authorized_keys"]),
        "meu_authorized_keys": str(paths["meu_authorized_keys"]),
        "host_key": str(paths["host_key"]),
        "host_key_created": created_host_key,
        "added_user_keys": added_user,
        "added_meu_keys": added_meu,
        "total_authorized_keys": total_keys,
    }


def is_port_open(host: str, port: int, timeout: float = 0.25) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def find_available_port(preferred_port: int = DEFAULT_SSH_PORT, max_tries: int = 30) -> int:
    for candidate in range(preferred_port, preferred_port + max_tries):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            if os.name != "nt":
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(("0.0.0.0", candidate))
            return candidate
        except OSError:
            continue
        finally:
            sock.close()
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("0.0.0.0", 0))
    port = int(sock.getsockname()[1])
    sock.close()
    return port


def _run_quick(cmd: list[str], timeout: int = 8) -> tuple[int, str]:
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return proc.returncode, (proc.stdout + "\n" + proc.stderr).strip()
    except Exception as exc:
        return 1, str(exc)


def ensure_system_sshd(*, install_if_missing: bool = False, extra_port: int | None = None) -> dict[str, Any]:
    """Check and optionally start/configure native OS OpenSSH server without blocking."""
    port22_active = is_port_open("127.0.0.1", 22)
    notes: list[str] = []

    if os.name != "nt":
        has_sshd = bool(shutil.which("sshd") or Path("/usr/sbin/sshd").is_file() or Path("/usr/bin/sshd").is_file())
        is_root = hasattr(os, "geteuid") and os.geteuid() == 0
        has_nopass_sudo = is_root or (_run_quick(["sudo", "-n", "true"], timeout=3)[0] == 0)

        if not has_sshd and install_if_missing and has_nopass_sudo and shutil.which("apt-get"):
            prefix = [] if is_root else ["sudo", "-n"]
            _run_quick([*prefix, "apt-get", "update", "-qq"], timeout=60)
            rc, _ = _run_quick([*prefix, "env", "DEBIAN_FRONTEND=noninteractive", "apt-get", "install", "-y", "-qq", "openssh-server"], timeout=120)
            if rc == 0:
                has_sshd = True
                notes.append("openssh-server kuruldu")

        if not port22_active and has_sshd and has_nopass_sudo:
            prefix = [] if is_root else ["sudo", "-n"]
            for svc in ("ssh", "sshd"):
                rc, _ = _run_quick([*prefix, "systemctl", "enable", "--now", svc], timeout=8)
                if rc == 0:
                    notes.append(f"sistem servisi başlatıldı ({svc})")
                    break
            else:
                if shutil.which("service"):
                    rc, _ = _run_quick([*prefix, "service", "ssh", "start"], timeout=8)
                    if rc == 0:
                        notes.append("sistem servisi başlatıldı (service ssh start)")
            port22_active = is_port_open("127.0.0.1", 22)

        return {
            "system_sshd_installed": has_sshd,
            "port22_active": port22_active,
            "notes": notes,
        }

    # Windows
    ps_bin = shutil.which("powershell") or shutil.which("pwsh")
    has_sshd = Path(r"C:\Windows\System32\OpenSSH\sshd.exe").is_file() or bool(shutil.which("sshd"))
    if not port22_active and ps_bin and has_sshd:
        _run_quick(
            [ps_bin, "-NoProfile", "-Command", "Try { Start-Service sshd -ErrorAction Stop; Set-Service -Name sshd -StartupType Automatic } Catch {}"],
            timeout=10,
        )
        port22_active = is_port_open("127.0.0.1", 22)
        if port22_active:
            notes.append("Windows sshd servisi başlatıldı")

    if extra_port and shutil.which("netsh"):
        for port_num in (extra_port, 22) if port22_active else (extra_port,):
            rule_name = f"MEU SSH TCP {port_num}"
            rc, _ = _run_quick(["netsh", "advfirewall", "firewall", "show", "rule", f"name={rule_name}"], timeout=4)
            if rc != 0:
                rc_add, _ = _run_quick(
                    [
                        "netsh",
                        "advfirewall",
                        "firewall",
                        "add",
                        "rule",
                        f"name={rule_name}",
                        "dir=in",
                        "action=allow",
                        "protocol=TCP",
                        f"localport={port_num}",
                    ],
                    timeout=5,
                )
                if rc_add == 0:
                    notes.append(f"Güvenlik duvarı kuralı eklendi (TCP {port_num})")

    return {
        "system_sshd_installed": has_sshd,
        "port22_active": port22_active,
        "notes": notes,
    }


def _load_asyncssh_authorized_keys(asyncssh_mod: Any) -> list[Any]:
    paths = get_ssh_paths()
    keys: list[Any] = []
    seen: set[str] = set()
    for candidate in (paths["user_authorized_keys"], paths["meu_authorized_keys"]):
        if not candidate.is_file():
            continue
        for line in candidate.read_text(encoding="utf-8", errors="ignore").splitlines():
            ident = _key_identity(line)
            if not ident or ident in seen:
                continue
            try:
                keys.append(asyncssh_mod.import_public_key(line.strip()))
                seen.add(ident)
            except Exception:
                continue
    return keys


async def _handle_ssh_client(process: Any) -> None:
    """Handle interactive shells (PTY on POSIX, cmd/powershell on Windows) and single commands."""
    command = getattr(process, "command", None)

    if os.name == "nt":
        if command:
            proc = await asyncio.create_subprocess_exec(
                "cmd.exe",
                "/c",
                command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        else:
            proc = await asyncio.create_subprocess_exec(
                "cmd.exe",
                "/K",
                "chcp 65001 >nul",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

        async def _pipe_in() -> None:
            try:
                while True:
                    data = await process.stdin.read(4096)
                    if not data:
                        break
                    if isinstance(data, str):
                        data = data.encode("utf-8", errors="replace")
                    if proc.stdin:
                        proc.stdin.write(data)
                        await proc.stdin.drain()
            except Exception:
                pass
            finally:
                if proc.stdin:
                    try:
                        proc.stdin.close()
                    except Exception:
                        pass

        async def _pipe_out(reader: asyncio.StreamReader | None, writer: Any) -> None:
            if not reader:
                return
            try:
                while True:
                    chunk = await reader.read(4096)
                    if not chunk:
                        break
                    writer.write(chunk)
                    await writer.drain()
            except Exception:
                pass

        tasks = [
            asyncio.create_task(_pipe_in()),
            asyncio.create_task(_pipe_out(proc.stdout, process.stdout)),
            asyncio.create_task(_pipe_out(proc.stderr, process.stderr)),
        ]
        rc = await proc.wait()
        await asyncio.gather(*tasks[1:], return_exceptions=True)
        tasks[0].cancel()
        process.exit(rc)
        return

    # POSIX: Single non-PTY command vs PTY interactive session
    term_type = process.get_terminal_type()
    if command and not term_type:
        shell_bin = os.environ.get("SHELL") or "/bin/bash"
        if not Path(shell_bin).exists():
            shell_bin = "/bin/sh"
        proc = await asyncio.create_subprocess_exec(
            shell_bin,
            "-c",
            command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(Path.home()),
        )

        async def _feed_stdin() -> None:
            try:
                while True:
                    data = await process.stdin.read(4096)
                    if not data:
                        break
                    if isinstance(data, str):
                        data = data.encode("utf-8", errors="replace")
                    if proc.stdin:
                        proc.stdin.write(data)
                        await proc.stdin.drain()
            except Exception:
                pass
            finally:
                if proc.stdin:
                    try:
                        proc.stdin.close()
                    except Exception:
                        pass

        async def _drain_stream(reader: asyncio.StreamReader | None, writer: Any) -> None:
            if not reader:
                return
            try:
                while True:
                    chunk = await reader.read(8192)
                    if not chunk:
                        break
                    writer.write(chunk)
                    await writer.drain()
            except Exception:
                pass

        t_in = asyncio.create_task(_feed_stdin())
        t_out = asyncio.create_task(_drain_stream(proc.stdout, process.stdout))
        t_err = asyncio.create_task(_drain_stream(proc.stderr, process.stderr))
        rc = await proc.wait()
        await asyncio.gather(t_out, t_err, return_exceptions=True)
        t_in.cancel()
        process.exit(rc)
        return

    # POSIX PTY session (interactive shell or ssh -t command)
    import asyncssh

    master_fd, slave_fd = pty.openpty()

    def _set_winsize(cols: int, rows: int, xpix: int = 0, ypix: int = 0) -> None:
        cols = max(1, cols or 80)
        rows = max(1, rows or 24)
        try:
            fcntl.ioctl(master_fd, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, xpix, ypix))
        except OSError:
            pass

    w, h, pw, ph = process.get_terminal_size()
    _set_winsize(w, h, pw, ph)

    shell_bin = os.environ.get("SHELL") or "/bin/bash"
    if not Path(shell_bin).exists():
        shell_bin = "/bin/sh"

    env = dict(os.environ)
    env["TERM"] = term_type or "xterm-256color"
    env.setdefault("HOME", str(Path.home()))
    env.setdefault("LANG", "C.UTF-8")

    argv = [shell_bin, "-c", command] if command else [shell_bin, "-i"]

    def _child_setup() -> None:
        os.setsid()
        fcntl.ioctl(slave_fd, termios.TIOCSCTTY, 0)
        os.close(master_fd)
        os.dup2(slave_fd, 0)
        os.dup2(slave_fd, 1)
        os.dup2(slave_fd, 2)
        if slave_fd > 2:
            os.close(slave_fd)

    proc = subprocess.Popen(
        argv,
        preexec_fn=_child_setup,
        cwd=str(Path.home()),
        env=env,
        close_fds=True,
    )
    os.close(slave_fd)
    os.set_blocking(master_fd, False)

    loop = asyncio.get_running_loop()
    pty_done = loop.create_future()

    def _on_pty_readable() -> None:
        try:
            data = os.read(master_fd, 16384)
            if not data:
                if not pty_done.done():
                    pty_done.set_result(None)
                return
            process.stdout.write(data)
        except BlockingIOError:
            return
        except OSError:
            if not pty_done.done():
                pty_done.set_result(None)

    loop.add_reader(master_fd, _on_pty_readable)

    async def _pty_writer() -> None:
        try:
            while not pty_done.done():
                try:
                    data = await process.stdin.read(4096)
                except asyncssh.TerminalSizeChanged as exc:
                    _set_winsize(exc.width, exc.height, exc.pixwidth, exc.pixheight)
                    continue
                except asyncssh.BreakReceived:
                    try:
                        os.write(master_fd, b"\x03")
                    except OSError:
                        pass
                    continue
                if not data:
                    break
                if isinstance(data, str):
                    data = data.encode("utf-8", errors="replace")
                os.write(master_fd, data)
        except Exception:
            pass

    writer_task = asyncio.create_task(_pty_writer())

    try:
        while proc.poll() is None:
            if pty_done.done():
                break
            await asyncio.sleep(0.05)
        await asyncio.sleep(0.05)
    finally:
        loop.remove_reader(master_fd)
        writer_task.cancel()
        if proc.poll() is None:
            try:
                proc.terminate()
                proc.wait(timeout=1.5)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
        rc = proc.returncode if proc.returncode is not None else 0
        try:
            os.close(master_fd)
        except OSError:
            pass
        try:
            await process.stdout.drain()
        except Exception:
            pass
        process.exit(rc)


def format_connection_banner(
    net_info: dict[str, Any],
    *,
    meu_port: int | None,
    password: str,
    sys_sshd: dict[str, Any],
    key_info: dict[str, Any],
    daemon_mode: bool = False,
) -> str:
    """Build a crisp, copy-paste-ready terminal status banner."""
    username = net_info["username"]
    lan_ips = net_info["lan_ips"]
    tailscale_ips = net_info["tailscale_ips"]
    primary_ip = net_info["primary_ip"]
    port22_active = sys_sshd.get("port22_active", False)

    lines: list[str] = []
    bar = "=" * 66
    lines.append(_style(bar, "1;36"))
    lines.append(_style("  MEU SSH SUNUCUSU HAZIR", "1;32") + f"  ({net_info['hostname']} • {net_info['os']})")
    lines.append(_style(bar, "1;36"))
    lines.append(f"  Kullanıcı      : {_style(username, '1;37')}")
    lines.append(f"  MEU SSH Şifre  : {_style(password, '1;33')}  (veya filo SSH anahtarı: {key_info['total_authorized_keys']} adet)")
    lines.append(f"  LAN IP         : {_style(', '.join(lan_ips) if lan_ips else 'Bulunamadı', '1;36')}")
    if tailscale_ips:
        lines.append(f"  Tailscale IP   : {_style(', '.join(tailscale_ips), '1;35')}")
    else:
        lines.append("  Tailscale IP   : Kurulu/aktif değil")

    if meu_port is not None:
        lines.append(f"  MEU SSH Portu  : {_style(str(meu_port), '1;32')} (SSH + SFTP + SCP aktif)")
    lines.append(
        f"  Sistem OpenSSH : {(_style('Port 22 AKTİF', '1;32') if port22_active else _style('Port 22 kapalı', '0;33'))}"
    )

    lines.append("-" * 66)
    lines.append(_style("  BAĞLANMAK İÇİN KOPYALA / YAPIŞTIR:", "1"))

    target_ips: list[tuple[str, str]] = []
    for ip in lan_ips:
        target_ips.append(("LAN", ip))
    for ip in tailscale_ips:
        if ip not in lan_ips:
            target_ips.append(("Tailscale", ip))
    if not target_ips:
        target_ips.append(("Yerel", primary_ip))

    if meu_port is not None:
        for label, ip in target_ips:
            lines.append(f"    [{label:<9}]  {_style(f'ssh -p {meu_port} {username}@{ip}', '1;32')}")
        lines.append(f"    [SCP Örnek ]  scp -P {meu_port} dosya.txt {username}@{target_ips[0][1]}:~/")

    if port22_active:
        for label, ip in target_ips[:2]:
            lines.append(f"    [Sistem 22 ]  {_style(f'ssh {username}@{ip}', '1;36')}")

    if meu_port is None and not port22_active:
        lines.append("    MEU SSH sunucusu şu an kapalı. Başlatmak için: meu ssh")

    lines.append("-" * 66)
    if daemon_mode:
        lines.append("  Arka planda çalışıyor. Durdurmak için: meu ssh --stop")
    elif meu_port is not None:
        lines.append("  Sunucu dinleniyor... Kapatmak için Ctrl+C tuşlarına basın.")
    lines.append(_style(bar, "1;36"))
    return "\n".join(lines)


async def _serve_async(port: int, password: str, host_key_path: Path, banner: str, quiet: bool = False) -> None:
    import asyncssh

    authorized_keys = _load_asyncssh_authorized_keys(asyncssh)

    class MeuSSHServer(asyncssh.SSHServer):
        def connection_made(self, conn: Any) -> None:
            self._conn = conn

        def begin_auth(self, username: str) -> bool:
            return True

        def password_auth_supported(self) -> bool:
            return True

        def validate_password(self, username: str, pw: str) -> bool:
            return secrets.compare_digest(pw, password)

        def public_key_auth_supported(self) -> bool:
            return bool(authorized_keys)

        def validate_public_key(self, username: str, key: Any) -> bool:
            return any(key == ak for ak in authorized_keys)

    async def _client_factory(process: Any) -> None:
        await _handle_ssh_client(process)

    server = await asyncssh.create_server(
        MeuSSHServer,
        "0.0.0.0",
        port,
        server_host_keys=[str(host_key_path)],
        process_factory=_client_factory,
        encoding=None,
        sftp_factory=True,
        allow_scp=True,
    )

    if not quiet:
        print(banner, flush=True)

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    if os.name != "nt":
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, stop_event.set)
            except NotImplementedError:
                pass

    try:
        await stop_event.wait()
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    finally:
        server.close()
        await server.wait_closed()


def _write_state(port: int, pid: int) -> None:
    paths = get_ssh_paths()
    paths["ssh_state_dir"].mkdir(parents=True, exist_ok=True)
    paths["state_file"].write_text(
        json.dumps({"pid": pid, "port": port}, indent=2) + "\n",
        encoding="utf-8",
    )


def _clear_state() -> None:
    sf = get_ssh_paths()["state_file"]
    if sf.exists():
        try:
            sf.unlink()
        except OSError:
            pass


def _stop_daemon() -> int:
    paths = get_ssh_paths()
    sf = paths["state_file"]
    if not sf.is_file():
        print("[!] Çalışan arka plan MEU SSH sunucusu bulunamadı.")
        return 0
    try:
        state = json.loads(sf.read_text(encoding="utf-8"))
        pid = int(state.get("pid", 0))
    except Exception:
        pid = 0

    if pid > 0:
        try:
            if os.name == "nt":
                subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True, check=False)
            else:
                os.kill(pid, signal.SIGTERM)
            print(f"[OK] Arka plan MEU SSH sunucusu durduruldu (PID: {pid}).")
        except OSError as exc:
            print(f"[!] Süreç sonlandırılamadı (PID: {pid}): {exc}")
    _clear_state()
    return 0


def _start_daemon(port: int, password: str) -> int:
    paths = get_ssh_paths()
    paths["ssh_state_dir"].mkdir(parents=True, exist_ok=True)
    log_file = paths["log_file"]

    cmd = [sys.executable, str(Path(__file__).resolve()), "--port", str(port), "--password", password, "--quiet"]
    kwargs: dict[str, Any] = {
        "stdin": subprocess.DEVNULL,
        "stdout": open(log_file, "ab"),
        "stderr": subprocess.STDOUT,
    }
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True

    proc = subprocess.Popen(cmd, **kwargs)
    try:
        kwargs["stdout"].close()
    except Exception:
        pass

    # Wait briefly for port to bind
    import time

    deadline = time.monotonic() + 5.0
    bound = False
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            break
        if is_port_open("127.0.0.1", port, timeout=0.15):
            bound = True
            break
        time.sleep(0.1)

    if not bound:
        print("[HATA] Arka plan SSH sunucusu başlatılamadı. Log:", log_file, file=sys.stderr)
        return 1

    _write_state(port, proc.pid)
    key_info = setup_ssh_keys()
    net_info = get_network_info()
    sys_sshd = ensure_system_sshd(install_if_missing=False, extra_port=port)
    print(
        format_connection_banner(
            net_info,
            meu_port=port,
            password=password,
            sys_sshd=sys_sshd,
            key_info=key_info,
            daemon_mode=True,
        )
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="meu ssh",
        description="Bilgisayarı anında SSH + SFTP sunucusuna dönüştürür ve IP/bağlantı bilgilerini yazdırır.",
    )
    parser.add_argument(
        "-p",
        "--port",
        type=int,
        default=DEFAULT_SSH_PORT,
        help=f"Dinlenecek SSH portu (varsayılan: {DEFAULT_SSH_PORT}, doluysa sonraki boş porta geçer)",
    )
    parser.add_argument(
        "--password",
        default=os.environ.get("MEU_SSH_PASSWORD", DEFAULT_SSH_PASSWORD),
        help=f"Giriş şifresi (varsayılan: {DEFAULT_SSH_PASSWORD})",
    )
    parser.add_argument("--status", "--check", action="store_true", help="Bağlantı ve IP bilgilerini gösterip çık")
    parser.add_argument("--install-setup", action="store_true", help="Yetkili anahtarları ve host anahtarını hazırla")
    parser.add_argument("--install-system", action="store_true", help="Sistem OpenSSH servisini kurmayı/açmayı dene")
    parser.add_argument("-d", "--daemon", action="store_true", help="Arka planda çalıştır")
    parser.add_argument("--stop", action="store_true", help="Arka planda çalışan MEU SSH sunucusunu durdur")
    parser.add_argument("--quiet", action="store_true", help=argparse.SUPPRESS)
    return parser


def main(argv: list[str] | None = None) -> int:
    _configure_utf8_streams()
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.stop:
        return _stop_daemon()

    key_info = setup_ssh_keys()
    net_info = get_network_info()

    if args.install_setup:
        sys_sshd = ensure_system_sshd(install_if_missing=args.install_system, extra_port=args.port)
        print(f"[OK] Filo SSH anahtarları hazırlandı ({key_info['total_authorized_keys']} anahtar).")
        print(f"[OK] Host anahtarı: {key_info['host_key']}")
        for note in sys_sshd.get("notes", []):
            print(f"[OK] {note}")
        return 0

    if args.status:
        sys_sshd = ensure_system_sshd(install_if_missing=False)
        active_port: int | None = None
        state_file = get_ssh_paths()["state_file"]
        if state_file.is_file():
            try:
                st = json.loads(state_file.read_text(encoding="utf-8"))
                st_port = int(st.get("port", 0))
                if st_port > 0 and is_port_open("127.0.0.1", st_port):
                    active_port = st_port
            except Exception:
                pass
        if active_port is None and is_port_open("127.0.0.1", args.port):
            active_port = args.port
        print(
            format_connection_banner(
                net_info,
                meu_port=active_port,
                password=args.password,
                sys_sshd=sys_sshd,
                key_info=key_info,
            )
        )
        return 0

    try:
        import asyncssh  # noqa: F401
    except ImportError:
        print(
            "[HATA] 'asyncssh' paketi yüklü değil. Kurmak için: meu install ssh --force",
            file=sys.stderr,
        )
        return 1

    listen_port = find_available_port(args.port)
    if args.daemon:
        return _start_daemon(listen_port, args.password)

    sys_sshd = ensure_system_sshd(install_if_missing=args.install_system, extra_port=listen_port)
    banner = format_connection_banner(
        net_info,
        meu_port=listen_port,
        password=args.password,
        sys_sshd=sys_sshd,
        key_info=key_info,
    )

    host_key_path = Path(key_info["host_key"])
    _write_state(listen_port, os.getpid())
    try:
        asyncio.run(_serve_async(listen_port, args.password, host_key_path, banner, quiet=args.quiet))
    except KeyboardInterrupt:
        pass
    finally:
        _clear_state()
    if not args.quiet:
        print("\n[OK] MEU SSH sunucusu kapatıldı.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
