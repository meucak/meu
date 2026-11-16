#!/usr/bin/env python3
"""meu — MEU Universal Package & Project Manager for Windows 10 & Linux."""

from __future__ import annotations

import argparse
import difflib
import importlib.util
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
import venv
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

__version__ = "1.0.0"

DEFAULT_OWNER = "meucak"

MEUCAK_CATALOG: dict[str, dict[str, Any]] = {
    "perf": {
        "name": "perf",
        "aliases": [],
        "kind": "python-cli",
        "description": "Sıfır bağımlılıklı ultra hafif terminal görev yöneticisi (CPU/RAM/GPU/Sıcaklık).",
        "entrypoints": [{"name": "perf", "target_type": "python_script", "script": "perf.py"}],
        "port": None,
        "apt_hints": [],
        "platforms": ["linux"],
    },
    "sortingen": {
        "name": "sortingen",
        "aliases": [],
        "kind": "python-cli",
        "description": "Klasörleri dosya tipi (--doctype), kategori (--category) veya tarihe (--date) göre düzenleyen akıllı CLI aracı.",
        "entrypoints": [{"name": "sortingen", "target_type": "python_script", "script": "sortingen.py"}],
        "port": None,
        "apt_hints": [],
        "platforms": ["linux", "windows"],
    },
    "recep": {
        "name": "recep",
        "aliases": ["cs-bomb", "monster-claw"],
        "kind": "pyqt-gui",
        "description": "Masaüstü canavar gözü widget'ı ve sesli retro CS C4 bomba imha simülatörü.",
        "entrypoints": [
            {"name": "recep", "target_type": "python_script", "script": "cs_bomb_game.py", "gui": True},
            {"name": "cs-bomb", "target_type": "python_script", "script": "cs_bomb_game.py", "gui": True},
            {"name": "monster-claw", "target_type": "python_script", "script": "monster_claw_widget.py", "gui": True},
        ],
        "port": None,
        "apt_hints": ["python3-pyqt6", "alsa-utils"],
        "platforms": ["linux", "windows"],
    },
    "borfek": {
        "name": "borfek",
        "aliases": [],
        "kind": "web-service",
        "description": "Ağ bağımsız, Cloudflare & P2P tabanlı sıfır-merkez şifreli mesajlaşma ve dosya paylaşım platformu.",
        "entrypoints": [{"name": "borfek", "target_type": "shell_pair", "port": 8093, "gui": True}],
        "port": 8093,
        "apt_hints": ["docker.io", "docker-compose-plugin"],
        "platforms": ["linux", "windows"],
    },
    "tessera": {
        "name": "tessera",
        "aliases": [],
        "kind": "web-service",
        "description": "Markdown editörü, FTS5 arama, Bilgi Grafiği, Spatial Canvas, Kanban ve FSRS tekrar stüdyosu.",
        "entrypoints": [{"name": "tessera", "target_type": "docker_web", "port": 8092, "gui": True}],
        "port": 8092,
        "apt_hints": ["docker.io", "docker-compose-plugin"],
        "platforms": ["linux", "windows"],
    },
    "toshi-camera": {
        "name": "toshi-camera",
        "aliases": ["kamera"],
        "kind": "pyqt-gui",
        "description": "PyQt6 masaüstü kamera stüdyosu ve QR kodlu telefon kamera/mikrofon köprüsü.",
        "entrypoints": [
            {
                "name": "toshi-camera",
                "target_type": "python_module",
                "module": "toshi_camera.main",
                "pythonpath": "src",
                "gui": True,
            },
            {
                "name": "kamera",
                "target_type": "python_module",
                "module": "toshi_camera.main",
                "pythonpath": "src",
                "gui": True,
            },
        ],
        "port": None,
        "apt_hints": ["python3-pyqt6", "python3-opencv", "python3-numpy", "python3-websockets", "ffmpeg", "v4l-utils"],
        "platforms": ["linux"],
    },
    "fil": {
        "name": "fil",
        "aliases": [],
        "kind": "web-service",
        "description": "Cloudflare Quick Tunnel, Tailscale ve LAN destekli evrensel dosya aktarımı ve sesli not köprüsü.",
        "entrypoints": [{"name": "fil", "target_type": "shell_pair", "port": 8090, "gui": True}],
        "port": 8090,
        "apt_hints": ["docker.io", "docker-compose-plugin"],
        "platforms": ["linux", "windows"],
    },
    "fleet-deck": {
        "name": "fleet-deck",
        "aliases": [],
        "kind": "web-service",
        "description": "Kasa, Toshi ve Quasimodo makineleri için sıfır-bulut çoklu cihaz görev kontrol panosu.",
        "entrypoints": [{"name": "fleet-deck", "target_type": "shell_pair", "port": 8091, "gui": True}],
        "port": 8091,
        "apt_hints": ["docker.io", "docker-compose-plugin"],
        "platforms": ["linux", "windows"],
    },
    "kush": {
        "name": "kush",
        "aliases": ["aura-lan", "saksogan"],
        "kind": "web-service",
        "description": "Yerel ağ ve Tailscale üzerinden sıfır gecikmeli mesajlaşma, pano ve dosya paylaşımı.",
        "entrypoints": [{"name": "kush", "target_type": "shell_pair", "port": 8088, "gui": True}],
        "port": 8088,
        "apt_hints": ["docker.io", "docker-compose-plugin"],
        "platforms": ["linux", "windows"],
    },
    "pdf-studio": {
        "name": "pdf-studio",
        "aliases": [],
        "kind": "static-web",
        "description": "Çevrimdışı çalışabilen PDF oluşturucu ve görsel PDF düzenleyici PWA web uygulaması.",
        "entrypoints": [{"name": "pdf-studio", "target_type": "static_web", "gui": True}],
        "port": None,
        "apt_hints": [],
        "platforms": ["linux", "windows"],
    },
    "antigravity-mobile-app": {
        "name": "antigravity-mobile-app",
        "aliases": ["makrotakip"],
        "kind": "static-web",
        "description": "Capacitor tabanlı MakroTakip mobil/web uygulaması.",
        "entrypoints": [{"name": "antigravity-mobile-app", "target_type": "static_web", "gui": True}],
        "port": None,
        "apt_hints": [],
        "platforms": ["linux", "windows"],
    },
    "MouseWithBorders-Android": {
        "name": "MouseWithBorders-Android",
        "aliases": ["mwb", "mousewithborders", "mouse-with-borders"],
        "kind": "python-gui",
        "description": "Windows PC ve Android cihazlar arasında yerel Wi-Fi UDP üzerinden <1ms fare/klavye paylaşımı.",
        "entrypoints": [
            {"name": "mwb", "target_type": "python_script", "script": "mouse_with_borders.py", "gui": True},
            {"name": "mouse-with-borders", "target_type": "python_script", "script": "mouse_with_borders.py", "gui": True},
        ],
        "port": None,
        "apt_hints": [],
        "platforms": ["windows", "linux"],
    },
}

ALIAS_MAP: dict[str, str] = {}
for _canonical_name, _meta in MEUCAK_CATALOG.items():
    ALIAS_MAP[_canonical_name.lower()] = _canonical_name
    for _alias in _meta.get("aliases", []):
        ALIAS_MAP[_alias.lower()] = _canonical_name
ALIAS_MAP.setdefault("cluckbeat", "dancing-chicken")


@dataclass(frozen=True)
class TargetSpec:
    owner: str
    repo: str
    branch: str | None
    clone_url: str
    zip_url: str
    html_url: str
    is_known_meucak: bool


def _canonicalize_repo_name(owner: str, repo: str) -> str:
    if owner.lower() == DEFAULT_OWNER.lower():
        return ALIAS_MAP.get(repo.lower(), repo)
    return repo


def _clean_repo_segment(segment: str) -> str:
    cleaned = segment.strip().strip("/")
    if cleaned.endswith(".git"):
        cleaned = cleaned[:-4]
    return cleaned


def resolve_target(raw: str) -> TargetSpec:
    """Normalize a project name, alias, owner/repo, or GitHub URL into a TargetSpec."""
    text = (raw or "").strip().strip('"').strip("'").strip()
    if not text:
        raise ValueError("Proje adı veya GitHub bağlantısı boş olamaz.")

    branch: str | None = None
    owner = DEFAULT_OWNER
    repo = ""

    # Handle SSH git@github.com:owner/repo.git
    ssh_match = re.match(r"^git@github\.com:([^/]+)/(.+?)(?:@([^/@]+))?$", text, re.IGNORECASE)
    if ssh_match:
        owner = ssh_match.group(1).strip()
        repo = _clean_repo_segment(ssh_match.group(2))
        branch = ssh_match.group(3).strip() if ssh_match.group(3) else None
    else:
        # Strip protocol or github.com prefix if present
        url_candidate = text
        # Handle @branch at the end if not part of user@host
        if "@" in url_candidate and not url_candidate.lower().startswith("git@"):
            base_part, maybe_branch = url_candidate.rsplit("@", 1)
            if maybe_branch and "/" not in maybe_branch:
                url_candidate = base_part
                branch = maybe_branch.strip()

        url_candidate = re.sub(r"^https?://", "", url_candidate, flags=re.IGNORECASE)
        if url_candidate.lower().startswith("www.github.com/"):
            url_candidate = url_candidate[len("www.github.com/") :]
        elif url_candidate.lower().startswith("github.com/"):
            url_candidate = url_candidate[len("github.com/") :]
        elif url_candidate.lower() == "github.com":
            raise ValueError(f"Geçersiz GitHub bağlantısı: {raw}")

        parts = [p for p in url_candidate.strip("/").split("/") if p]
        if not parts:
            raise ValueError(f"Geçersiz proje hedefi: {raw}")

        if len(parts) == 1:
            owner = DEFAULT_OWNER
            repo = _clean_repo_segment(parts[0])
        else:
            owner = parts[0].strip()
            repo = _clean_repo_segment(parts[1])
            if len(parts) >= 4 and parts[2].lower() in ("tree", "releases"):
                tree_branch = "/".join(parts[3:]).strip("/")
                if tree_branch and not branch:
                    branch = tree_branch

    if not owner or not repo or any(ch in repo for ch in (" ", "\\", ":", "?", "*")):
        raise ValueError(f"Geçersiz proje hedefi: {raw}")

    repo = _canonicalize_repo_name(owner, repo)
    is_known_meucak = owner.lower() == DEFAULT_OWNER.lower() and repo in MEUCAK_CATALOG
    clone_url = f"https://github.com/{owner}/{repo}.git"
    html_url = f"https://github.com/{owner}/{repo}"
    if branch:
        zip_url = f"https://codeload.github.com/{owner}/{repo}/zip/refs/heads/{branch}"
    else:
        zip_url = f"https://api.github.com/repos/{owner}/{repo}/zipball"

    return TargetSpec(
        owner=owner,
        repo=repo,
        branch=branch,
        clone_url=clone_url,
        zip_url=zip_url,
        html_url=html_url,
        is_known_meucak=is_known_meucak,
    )


def suggest_similar_repos(name: str, catalog_names: list[str] | None = None) -> list[str]:
    """Return likely matching repo names from the catalog and alias map."""
    query = (name or "").strip().lower()
    if not query:
        return []
    pool = list(catalog_names) if catalog_names is not None else list(MEUCAK_CATALOG.keys())
    lower_to_canonical = {item.lower(): item for item in pool}
    for alias, target in ALIAS_MAP.items():
        if target in pool or catalog_names is None:
            lower_to_canonical.setdefault(alias, target)

    matches = difflib.get_close_matches(query, list(lower_to_canonical.keys()), n=5, cutoff=0.45)
    seen: list[str] = []
    for key in matches:
        canonical = lower_to_canonical[key]
        if canonical not in seen:
            seen.append(canonical)

    # Also include substring matches if fewer than 3
    for key, canonical in lower_to_canonical.items():
        if query in key and canonical not in seen:
            seen.append(canonical)
    return seen[:5]


def get_meu_paths(
    env: Mapping[str, str] | None = None,
    platform_name: str | None = None,
) -> dict[str, Path]:
    """Compute all filesystem directories used by meu in an OS-independent way."""
    environ = env if env is not None else os.environ
    plat = platform_name if platform_name is not None else os.name

    if plat == "nt":
        raw_user_home = environ.get("USERPROFILE") or environ.get("HOME") or str(Path.home())
    else:
        raw_user_home = environ.get("HOME") or str(Path.home())
    user_home = Path(raw_user_home).expanduser()

    has_custom_meu_home = bool(environ.get("MEU_HOME", "").strip())
    if has_custom_meu_home:
        home = Path(environ["MEU_HOME"]).expanduser()
    else:
        home = user_home / ".meu"

    internal_bin_dir = home / "bin"

    custom_bin_dir = environ.get("MEU_BIN_DIR", "").strip()
    if custom_bin_dir:
        bin_dir = Path(custom_bin_dir).expanduser()
    elif plat == "nt" or has_custom_meu_home:
        bin_dir = internal_bin_dir
    else:
        bin_dir = user_home / ".local" / "bin"

    custom_desktop_dir = environ.get("MEU_DESKTOP_DIR", "").strip()
    if custom_desktop_dir:
        desktop_dir = Path(custom_desktop_dir).expanduser()
    elif has_custom_meu_home:
        desktop_dir = home / "desktop"
    elif plat == "nt":
        desktop_dir = user_home / "Desktop"
    else:
        desktop_dir = user_home / ".local" / "share" / "applications"

    return {
        "home": home,
        "core_dir": home / "core",
        "apps_dir": home / "apps",
        "cache_dir": home / "cache",
        "internal_bin_dir": internal_bin_dir,
        "bin_dir": bin_dir,
        "registry_file": home / "registry.json",
        "desktop_dir": desktop_dir,
    }


def _handle_remove_readonly(func: Callable[..., Any], path: str, exc_info: Any) -> None:
    """Clear read-only attribute (Windows .git pack files) and retry removal."""
    try:
        os.chmod(path, stat.S_IWRITE | stat.S_IREAD)
    except OSError:
        pass
    func(path)


def rmtree_safe(path: Path) -> None:
    """Recursively delete a directory tree, handling read-only files on Windows & Linux."""
    target = Path(path)
    if not target.exists() and not target.is_symlink():
        return
    if target.is_symlink() or target.is_file():
        try:
            os.chmod(target, stat.S_IWRITE | stat.S_IREAD)
        except OSError:
            pass
        target.unlink()
        return

    if sys.version_info >= (3, 12):
        shutil.rmtree(target, onexc=_handle_remove_readonly)
    else:
        shutil.rmtree(target, onerror=_handle_remove_readonly)


class Registry:
    """Atomic JSON registry storing installed meu applications and metadata."""

    def __init__(self, registry_file: Path) -> None:
        self.registry_file = Path(registry_file)

    def _empty_state(self) -> dict[str, Any]:
        return {"schema_version": 1, "apps": {}}

    def load(self) -> dict[str, Any]:
        if not self.registry_file.exists():
            return self._empty_state()
        try:
            raw = self.registry_file.read_text(encoding="utf-8")
            data = json.loads(raw)
            if not isinstance(data, dict) or not isinstance(data.get("apps"), dict):
                return self._empty_state()
            return data
        except (OSError, json.JSONDecodeError):
            return self._empty_state()

    def save(self, data: dict[str, Any]) -> None:
        self.registry_file.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(
            dir=str(self.registry_file.parent),
            prefix=".registry_",
            suffix=".tmp",
        )
        tmp_path = Path(tmp_name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(data, handle, indent=2, ensure_ascii=False)
                handle.write("\n")
            os.replace(tmp_path, self.registry_file)
        except Exception:
            if tmp_path.exists():
                tmp_path.unlink()
            raise

    def _resolve_key(self, apps: dict[str, Any], name: str) -> str | None:
        if name in apps:
            return name
        target_lower = name.lower()
        canonical = ALIAS_MAP.get(target_lower, name).lower()
        for existing_key in apps:
            if existing_key.lower() in (target_lower, canonical):
                return existing_key
        return None

    def get_app(self, name: str) -> dict[str, Any] | None:
        data = self.load()
        apps = data["apps"]
        key = self._resolve_key(apps, name)
        return apps.get(key) if key is not None else None

    def set_app(self, name: str, record: dict[str, Any]) -> None:
        data = self.load()
        existing_key = self._resolve_key(data["apps"], name)
        if existing_key and existing_key != name:
            del data["apps"][existing_key]
        data["apps"][name] = record
        self.save(data)

    def remove_app(self, name: str) -> dict[str, Any] | None:
        data = self.load()
        key = self._resolve_key(data["apps"], name)
        if key is None:
            return None
        removed = data["apps"].pop(key)
        self.save(data)
        return removed

    def list_apps(self) -> list[dict[str, Any]]:
        data = self.load()
        return [data["apps"][k] for k in sorted(data["apps"], key=str.lower)]


def extract_zip_root_stripped(zip_path: Path, dest_dir: Path) -> str:
    """Safely extract a GitHub archive ZIP into dest_dir, stripping its single top-level directory."""
    dest = Path(dest_dir)
    dest.mkdir(parents=True, exist_ok=True)
    dest_resolved = dest.resolve()

    top_dirs: set[str] = set()
    with zipfile.ZipFile(zip_path, "r") as zf:
        members = zf.infolist()
        for member in members:
            norm = member.filename.replace("\\", "/")
            if norm.startswith("/") or ".." in Path(norm).parts:
                raise ValueError(f"Güvensiz ZIP yolu tespit edildi: {member.filename}")
            first_part = norm.split("/", 1)[0]
            if first_part:
                top_dirs.add(first_part)

        strip_prefix = ""
        if len(top_dirs) == 1:
            sole_root = next(iter(top_dirs))
            has_root_slash = any(
                m.filename.replace("\\", "/").startswith(f"{sole_root}/") for m in members
            )
            if has_root_slash:
                strip_prefix = f"{sole_root}/"

        for member in members:
            rel_name = member.filename.replace("\\", "/")
            if strip_prefix and rel_name.startswith(strip_prefix):
                rel_name = rel_name[len(strip_prefix) :]
            elif strip_prefix and rel_name.rstrip("/") == strip_prefix.rstrip("/"):
                continue

            if not rel_name or rel_name == "/":
                continue

            target_path = (dest / rel_name).resolve()
            try:
                target_path.relative_to(dest_resolved)
            except ValueError as exc:
                raise ValueError(f"ZIP hedef dizin dışına çıkıyor: {member.filename}") from exc

            if member.is_dir():
                target_path.mkdir(parents=True, exist_ok=True)
                continue

            target_path.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(member, "r") as src, open(target_path, "wb") as dst:
                shutil.copyfileobj(src, dst)

            unix_mode = (member.external_attr >> 16) & 0o777
            if os.name != "nt" and (unix_mode & 0o111):
                os.chmod(target_path, unix_mode | 0o644)

    return strip_prefix.rstrip("/")


def _git_version_info(repo_dir: Path) -> str:
    try:
        proc = subprocess.run(
            ["git", "-C", str(repo_dir), "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        )
        sha = proc.stdout.strip()
        if sha:
            return sha
    except Exception:
        pass
    return datetime.now(timezone.utc).strftime("%Y%m%d")


def _build_zip_candidates(spec: TargetSpec) -> list[str]:
    if spec.zip_url and spec.branch:
        return [spec.zip_url]
    candidates: list[str] = []
    if spec.zip_url:
        candidates.append(spec.zip_url)
    candidates.extend(
        [
            f"https://codeload.github.com/{spec.owner}/{spec.repo}/zip/refs/heads/main",
            f"https://codeload.github.com/{spec.owner}/{spec.repo}/zip/refs/heads/master",
        ]
    )
    return list(dict.fromkeys(candidates))


def download_repo(
    spec: TargetSpec,
    dest_dir: Path,
    prefer_git: bool = True,
    cache_dir: Path | None = None,
    opener: Callable[..., Any] | None = None,
) -> dict[str, str]:
    """Download a repository into dest_dir via git clone or GitHub ZIP fallback."""
    dest = Path(dest_dir)
    dest.parent.mkdir(parents=True, exist_ok=True)
    staging = dest.parent / f".staging_{dest.name}_{os.getpid()}"
    rmtree_safe(staging)

    git_bin = shutil.which("git") if prefer_git else None
    last_error = ""

    if git_bin:
        cmd = [git_bin, "clone", "--depth", "1"]
        if spec.branch:
            cmd.extend(["--branch", spec.branch])
        cmd.extend([spec.clone_url, str(staging)])
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
            if proc.returncode == 0:
                version = _git_version_info(staging)
                rmtree_safe(dest)
                os.replace(staging, dest)
                return {"method": "git", "version": version}
            last_error = (proc.stderr or proc.stdout or "").strip()
            rmtree_safe(staging)
        except Exception as exc:
            last_error = str(exc)
            rmtree_safe(staging)

    # Do not try GitHub HTTP fallback for local file:// clones used in tests
    if spec.clone_url.startswith("file://"):
        raise RuntimeError(f"Git klonlama başarısız oldu: {last_error}")

    http_open = opener if opener is not None else urllib.request.urlopen
    zip_candidates = _build_zip_candidates(spec)
    cache_root = cache_dir if cache_dir is not None else dest.parent / ".cache"
    cache_root.mkdir(parents=True, exist_ok=True)
    zip_file = cache_root / f"{spec.owner}_{spec.repo}.zip"

    downloaded = False
    not_found_count = 0
    for url in zip_candidates:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": f"meu/{__version__} (+https://github.com/meucak)"},
        )
        try:
            with http_open(req, timeout=60) as resp:
                payload = resp.read()
            if not payload:
                continue
            zip_file.write_bytes(payload)
            downloaded = True
            break
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                not_found_count += 1
            last_error = f"HTTP {exc.code}: {url}"
        except Exception as exc:
            last_error = str(exc)

    if not downloaded:
        if not_found_count == len(zip_candidates) and spec.owner.lower() == DEFAULT_OWNER.lower():
            suggestions = suggest_similar_repos(spec.repo)
            hint = f" Benzer projeler: {', '.join(suggestions)}" if suggestions else ""
            raise RuntimeError(f"GitHub deposu bulunamadı: {spec.owner}/{spec.repo}.{hint}")
        raise RuntimeError(f"Proje indirilemedi ({spec.html_url}): {last_error}")

    try:
        staging.mkdir(parents=True, exist_ok=True)
        root_tag = extract_zip_root_stripped(zip_file, staging)
        rmtree_safe(dest)
        os.replace(staging, dest)
        version = root_tag.split("-")[-1][:7] if "-" in root_tag else datetime.now(timezone.utc).strftime("%Y%m%d")
        return {"method": "zip", "version": version}
    finally:
        rmtree_safe(staging)
        if zip_file.exists():
            try:
                zip_file.unlink()
            except OSError:
                pass


def _find_python_gui_hint(app_dir: Path) -> bool:
    for py_file in app_dir.glob("*.py"):
        try:
            text = py_file.read_text(encoding="utf-8", errors="ignore")[:4000]
        except OSError:
            continue
        if any(mod in text for mod in ("PyQt6", "PyQt5", "PySide6", "tkinter")):
            return True
    return False


def _find_primary_python_scripts(app_dir: Path, repo_name: str) -> list[str]:
    skip = {"setup.py", "conftest.py"}
    py_files = [
        p.name
        for p in sorted(app_dir.glob("*.py"))
        if p.is_file() and not p.name.startswith("test_") and not p.name.startswith(".meu_") and p.name not in skip
    ]
    if not py_files:
        return []
    norm_repo = repo_name.lower().replace("-", "_")
    preferred = [
        f"{repo_name}.py",
        f"{norm_repo}.py",
        "main.py",
        "app.py",
        "cli.py",
        "run.py",
    ]
    for candidate in preferred:
        for existing in py_files:
            if existing.lower() == candidate.lower():
                return [existing]
    if len(py_files) == 1:
        return py_files
    # Prefer scripts containing __main__ guard
    main_scripts = []
    for name in py_files:
        try:
            txt = (app_dir / name).read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if '__name__ == "__main__"' in txt or "__name__ == '__main__'" in txt:
            main_scripts.append(name)
    return main_scripts[:1] if main_scripts else [py_files[0]]


def _detect_shell_pair(app_dir: Path, name: str) -> tuple[Path | None, Path | None]:
    sh_candidates = [
        app_dir / f"{name}-linux.sh",
        app_dir / f"{name}.sh",
        app_dir / "run.sh",
    ]
    bat_candidates = [
        app_dir / f"{name}-windows.bat",
        app_dir / f"{name}.bat",
        app_dir / "run.bat",
    ]
    sh_path = next((p for p in sh_candidates if p.is_file()), None)
    bat_path = next((p for p in bat_candidates if p.is_file()), None)
    return sh_path, bat_path


def _extract_port_from_compose(app_dir: Path) -> int | None:
    for fname in ("docker-compose.yml", "compose.yml"):
        fpath = app_dir / fname
        if fpath.is_file():
            try:
                content = fpath.read_text(encoding="utf-8", errors="ignore")
                match = re.search(r'["\']?(?:127\.0\.0\.1:)?(\d{4,5}):\d{4,5}["\']?', content)
                if match:
                    return int(match.group(1))
            except OSError:
                pass
    return None


def inspect_project(app_dir: Path, repo_name: str) -> dict[str, Any]:
    """Inspect a cloned/extracted repository and build a cross-platform install plan."""
    app_path = Path(app_dir)
    canonical = ALIAS_MAP.get(repo_name.lower(), repo_name)
    req_file = app_path / "requirements.txt"
    has_req = req_file.is_file()
    has_compose = (app_path / "docker-compose.yml").is_file() or (app_path / "compose.yml").is_file()

    # Tier 1: Explicit meu.json manifest inside the repository
    manifest_file = app_path / "meu.json"
    if manifest_file.is_file():
        try:
            manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
            if isinstance(manifest, dict) and manifest.get("commands"):
                kind = str(manifest.get("kind", "python-cli"))
                needs_venv = bool(manifest.get("needs_venv", has_req))
                return {
                    "name": manifest.get("name", canonical),
                    "kind": kind,
                    "needs_venv": needs_venv,
                    "requirements_file": req_file if has_req else None,
                    "commands": list(manifest["commands"]),
                    "has_docker_compose": has_compose,
                    "desktop_entry": manifest.get("desktop_entry"),
                    "description": manifest.get("description", ""),
                    "port": manifest.get("port"),
                    "apt_hints": list(manifest.get("apt_hints", [])),
                }
        except (OSError, json.JSONDecodeError):
            pass

    # Tier 2: Built-in MEUCAK_CATALOG recipe
    if canonical in MEUCAK_CATALOG:
        recipe = MEUCAK_CATALOG[canonical]
        kind = recipe["kind"]
        commands: list[dict[str, Any]] = []
        sh_path, bat_path = _detect_shell_pair(app_path, canonical)

        for entry in recipe["entrypoints"]:
            cmd = dict(entry)
            if cmd["target_type"] == "shell_pair":
                if sh_path:
                    cmd["sh_script"] = sh_path.name
                if bat_path:
                    cmd["bat_script"] = bat_path.name
            elif cmd["target_type"] == "static_web":
                if (app_path / "index.html").is_file():
                    cmd["html_path"] = "index.html"
                elif (app_path / "www" / "index.html").is_file():
                    cmd["html_path"] = "www/index.html"
            commands.append(cmd)

        needs_venv = has_req or kind == "pyqt-gui"
        is_gui = any(c.get("gui") for c in commands)
        desktop_entry = None
        if is_gui and commands:
            desktop_entry = {
                "name": canonical,
                "comment": recipe["description"],
                "command": commands[0]["name"],
                "icon": "applications-internet" if kind in ("web-service", "static-web") else "utilities-terminal",
                "categories": "Network;Utility;" if kind in ("web-service", "static-web") else "Utility;",
            }

        return {
            "name": canonical,
            "kind": kind,
            "needs_venv": needs_venv,
            "requirements_file": req_file if has_req else None,
            "commands": commands,
            "has_docker_compose": has_compose,
            "desktop_entry": desktop_entry,
            "description": recipe["description"],
            "port": recipe.get("port"),
            "apt_hints": list(recipe.get("apt_hints", [])),
        }

    # Tier 3: Universal Heuristic Auto-Detector for new/external repositories
    cmd_slug = canonical.lower()
    sh_path, bat_path = _detect_shell_pair(app_path, canonical)
    if sh_path is None and bat_path is None:
        sh_path, bat_path = _detect_shell_pair(app_path, cmd_slug)

    if has_compose or (sh_path and bat_path):
        port = _extract_port_from_compose(app_path)
        cmd_dict: dict[str, Any] = {
            "name": cmd_slug,
            "target_type": "shell_pair" if (sh_path or bat_path) else "docker_web",
            "port": port or 8080,
            "gui": True,
        }
        if sh_path:
            cmd_dict["sh_script"] = sh_path.name
        if bat_path:
            cmd_dict["bat_script"] = bat_path.name
        return {
            "name": canonical,
            "kind": "web-service",
            "needs_venv": False,
            "requirements_file": None,
            "commands": [cmd_dict],
            "has_docker_compose": has_compose,
            "desktop_entry": {
                "name": canonical,
                "comment": f"{canonical} servisi",
                "command": cmd_slug,
                "icon": "applications-internet",
                "categories": "Network;Utility;",
            },
            "description": f"{canonical} web/Docker uygulaması",
            "port": port,
            "apt_hints": ["docker.io", "docker-compose-plugin"] if has_compose else [],
        }

    # Check Python package under src/<pkg>/main.py or __main__.py
    src_dir = app_path / "src"
    if src_dir.is_dir():
        for pkg_dir in sorted(src_dir.iterdir()):
            if pkg_dir.is_dir() and ((pkg_dir / "main.py").is_file() or (pkg_dir / "__main__.py").is_file()):
                mod_suffix = "main" if (pkg_dir / "main.py").is_file() else "__main__"
                mod_name = f"{pkg_dir.name}.{mod_suffix}" if mod_suffix == "main" else pkg_dir.name
                is_gui = _find_python_gui_hint(pkg_dir)
                kind = "pyqt-gui" if is_gui else "python-cli"
                return {
                    "name": canonical,
                    "kind": kind,
                    "needs_venv": has_req or is_gui,
                    "requirements_file": req_file if has_req else None,
                    "commands": [
                        {
                            "name": cmd_slug,
                            "target_type": "python_module",
                            "module": mod_name,
                            "pythonpath": "src",
                            "gui": is_gui,
                        }
                    ],
                    "has_docker_compose": False,
                    "desktop_entry": (
                        {
                            "name": canonical,
                            "comment": f"{canonical} masaüstü uygulaması",
                            "command": cmd_slug,
                            "icon": "utilities-terminal",
                            "categories": "Utility;",
                        }
                        if is_gui
                        else None
                    ),
                    "description": f"{canonical} Python uygulaması",
                    "port": None,
                    "apt_hints": [],
                }

    py_scripts = _find_primary_python_scripts(app_path, canonical)
    if py_scripts:
        is_gui = _find_python_gui_hint(app_path)
        has_pyqt = any(
            "PyQt" in (app_path / p).read_text(encoding="utf-8", errors="ignore")[:4000]
            for p in py_scripts
        )
        if not has_pyqt and has_req:
            req_txt = req_file.read_text(encoding="utf-8", errors="ignore")
            has_pyqt = "PyQt" in req_txt or "PySide" in req_txt
        kind = "pyqt-gui" if has_pyqt else ("python-gui" if is_gui else "python-cli")
        return {
            "name": canonical,
            "kind": kind,
            "needs_venv": has_req or has_pyqt,
            "requirements_file": req_file if has_req else None,
            "commands": [
                {
                    "name": cmd_slug,
                    "target_type": "python_script",
                    "script": py_scripts[0],
                    "gui": is_gui,
                }
            ],
            "has_docker_compose": False,
            "desktop_entry": (
                {
                    "name": canonical,
                    "comment": f"{canonical} uygulaması",
                    "command": cmd_slug,
                    "icon": "utilities-terminal",
                    "categories": "Utility;",
                }
                if is_gui
                else None
            ),
            "description": f"{canonical} Python projesi",
            "port": None,
            "apt_hints": [],
        }

    # Static web app
    for html_rel in ("index.html", "www/index.html", "public/index.html"):
        if (app_path / html_rel).is_file():
            return {
                "name": canonical,
                "kind": "static-web",
                "needs_venv": False,
                "requirements_file": None,
                "commands": [
                    {
                        "name": cmd_slug,
                        "target_type": "static_web",
                        "html_path": html_rel,
                        "gui": True,
                    }
                ],
                "has_docker_compose": False,
                "desktop_entry": {
                    "name": canonical,
                    "comment": f"{canonical} web uygulaması",
                    "command": cmd_slug,
                    "icon": "applications-internet",
                    "categories": "Network;Utility;",
                },
                "description": f"{canonical} web uygulaması",
                "port": None,
                "apt_hints": [],
            }

    return {
        "name": canonical,
        "kind": "script",
        "needs_venv": has_req,
        "requirements_file": req_file if has_req else None,
        "commands": [],
        "has_docker_compose": False,
        "desktop_entry": None,
        "description": f"{canonical} deposu",
        "port": None,
        "apt_hints": [],
    }


def _patch_fcntl_cross_platform(text: str, lock_filename: str) -> tuple[str, bool]:
    """Make Unix fcntl lock usage safe on Windows while preserving Linux flock behavior."""
    changed = False
    if "except ImportError:" not in text and re.search(r"^\s*import fcntl\s*$", text, re.MULTILINE):
        guard = (
            "import os\n"
            "import tempfile\n"
            "try:\n"
            "    import fcntl\n"
            "except ImportError:\n"
            "    fcntl = None"
        )
        text = re.sub(r"^\s*import fcntl\s*$", guard, text, count=1, flags=re.MULTILINE)
        changed = True

    old_lock_open = f'open("/tmp/{lock_filename}", "w")'
    new_lock_open = f'open(os.path.join(tempfile.gettempdir(), "{lock_filename}"), "w")'
    if old_lock_open in text:
        text = text.replace(old_lock_open, new_lock_open)
        changed = True

    text, n_subs = re.subn(
        r"^([ \t]*)fcntl\.flock\((.+)\)[ \t]*$",
        r"\1if fcntl is not None:\n\1    fcntl.flock(\2)",
        text,
        flags=re.MULTILINE,
    )
    # Prevent double-wrapping if already guarded
    text = text.replace(
        "if fcntl is not None:\n    if fcntl is not None:\n",
        "if fcntl is not None:\n",
    )
    if n_subs > 0:
        changed = True
    return text, changed


def apply_compat_patches(app_dir: Path, repo_name: str) -> list[str]:
    """Apply cross-platform compatibility adapters (e.g., recep Windows/Linux fixes)."""
    app_path = Path(app_dir)
    notes: list[str] = []
    canonical = ALIAS_MAP.get(repo_name.lower(), repo_name)

    is_recep = canonical.lower() == "recep" or (
        (app_path / "cs_bomb_game.py").is_file() and (app_path / "monster_claw_widget.py").is_file()
    )
    if not is_recep:
        return notes

    # 1. Copy c4_skin.jpeg to ~/.local/share/cs-bomb when running live (outside isolated MEU_HOME tests)
    local_skin = app_path / "c4_skin.jpeg"
    if local_skin.is_file() and not os.environ.get("MEU_HOME"):
        try:
            share_dir = Path.home() / ".local" / "share" / "cs-bomb"
            share_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(local_skin, share_dir / "c4_skin.jpeg")
            notes.append("c4_skin.jpeg ~/.local/share/cs-bomb/ altına kopyalandı")
        except OSError:
            pass

    # 2. Patch cs_bomb_game.py (SKIN_PATH local fallback + cross-platform fcntl lock)
    bomb_file = app_path / "cs_bomb_game.py"
    if bomb_file.is_file():
        src = bomb_file.read_text(encoding="utf-8")
        orig = src
        old_skin_line = 'SKIN_PATH = os.path.expanduser("~/.local/share/cs-bomb/c4_skin.jpeg")'
        new_skin_block = (
            '_LOCAL_SKIN = os.path.join(os.path.dirname(os.path.abspath(__file__)), "c4_skin.jpeg")\n'
            'SKIN_PATH = _LOCAL_SKIN if os.path.exists(_LOCAL_SKIN) else os.path.expanduser("~/.local/share/cs-bomb/c4_skin.jpeg")'
        )
        if old_skin_line in src and "_LOCAL_SKIN" not in src:
            src = src.replace(old_skin_line, new_skin_block, 1)
        src, _ = _patch_fcntl_cross_platform(src, "cs_bomb_game.lock")
        if src != orig:
            bomb_file.write_text(src, encoding="utf-8")
            notes.append("cs_bomb_game.py çapraz platform (fcntl + skin) uyumlu hale getirildi")

    # 3. Patch monster_claw_widget.py (cross-platform fcntl + dynamic cs_bomb_game.py launch)
    claw_file = app_path / "monster_claw_widget.py"
    if claw_file.is_file():
        src = claw_file.read_text(encoding="utf-8")
        orig = src
        src, _ = _patch_fcntl_cross_platform(src, "monster_claw_widget.lock")
        if '"/home/toshi/.local/bin/cs-bomb"' in src:
            if "import sys" not in src:
                src = "import sys\n" + src
            src = src.replace(
                '["/home/toshi/.local/bin/cs-bomb"]',
                '[sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), "cs_bomb_game.py")]',
            )
        if src != orig:
            claw_file.write_text(src, encoding="utf-8")
            notes.append("monster_claw_widget.py dinamik başlatıcı ve çapraz platform kilitle güncellendi")

    # 4. Patch sound_fx.py (Windows winsound + Linux aplay/paplay/pw-play + local wav fallback)
    sound_file = app_path / "sound_fx.py"
    if sound_file.is_file():
        src = sound_file.read_text(encoding="utf-8")
        if "winsound" not in src:
            header_imports = ""
            if "import shutil" not in src:
                header_imports += "import shutil\n"
            if "import sys" not in src:
                header_imports += "import sys\n"
            if header_imports:
                src = header_imports + src

            compat_play = (
                "\ndef _meu_find_wav(name):\n"
                "    primary = os.path.join(SOUNDS_DIR, f\"{name}.wav\")\n"
                "    if os.path.exists(primary):\n"
                "        return primary\n"
                "    local = os.path.join(os.path.dirname(os.path.abspath(__file__)), \"sounds\", f\"{name}.wav\")\n"
                "    if os.path.exists(local):\n"
                "        return local\n"
                "    try:\n"
                "        ensure_sounds()\n"
                "    except Exception:\n"
                "        pass\n"
                "    return primary if os.path.exists(primary) else None\n\n"
                "def play(name):\n"
                "    wav_path = _meu_find_wav(name)\n"
                "    if not wav_path:\n"
                "        return\n"
                "    if sys.platform == \"win32\":\n"
                "        try:\n"
                "            import winsound\n"
                "            winsound.PlaySound(wav_path, winsound.SND_FILENAME | winsound.SND_ASYNC)\n"
                "        except Exception:\n"
                "            pass\n"
                "        return\n"
                "    for player, args in ((\"aplay\", [\"-q\"]), (\"paplay\", []), (\"pw-play\", [])):\n"
                "        if shutil.which(player):\n"
                "            try:\n"
                "                subprocess.Popen([player, *args, wav_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)\n"
                "            except Exception:\n"
                "                pass\n"
                "            return\n"
            )
            play_pattern = re.compile(
                r"def play\(name\):.*?(?=\nif __name__ ==|\Z)",
                re.DOTALL,
            )
            if play_pattern.search(src):
                src = play_pattern.sub(compat_play.lstrip("\n") + "\n", src, count=1)
            else:
                src = src.rstrip() + "\n" + compat_play
            sound_file.write_text(src, encoding="utf-8")
            notes.append("sound_fx.py Windows (winsound) ve Linux ses oynatıcıları için güncellendi")

    return notes


def _ensure_web_launcher_script(app_dir: Path, cmd_spec: dict[str, Any]) -> Path:
    """Create a tiny cross-platform Python launcher for static_web / docker_web targets."""
    cmd_name = cmd_spec["name"]
    safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", cmd_name)
    launcher = app_dir / f".meu_launch_{safe_name}.py"
    target_type = cmd_spec["target_type"]

    if target_type == "static_web":
        rel_html = cmd_spec.get("html_path", "index.html")
        code = (
            "from pathlib import Path\n"
            "import webbrowser\n"
            f"target = Path(__file__).resolve().parent / {rel_html!r}\n"
            "print(f'Açılıyor: {target}')\n"
            "webbrowser.open(target.as_uri())\n"
        )
    else:
        port = int(cmd_spec.get("port") or 8080)
        code = (
            "import shutil, subprocess, sys, urllib.request, webbrowser\n"
            "from pathlib import Path\n"
            f"url = 'http://127.0.0.1:{port}'\n"
            "app_dir = Path(__file__).resolve().parent\n"
            "def is_up():\n"
            "    try:\n"
            "        with urllib.request.urlopen(url, timeout=1.5):\n"
            "            return True\n"
            "    except Exception:\n"
            "        return False\n"
            "if not is_up() and shutil.which('docker'):\n"
            "    print(f'Docker servisi başlatılıyor ({app_dir})...')\n"
            "    subprocess.run(['docker', 'compose', 'up', '-d'], cwd=str(app_dir))\n"
            "print(f'Tarayıcıda açılıyor: {url}')\n"
            "webbrowser.open(url)\n"
        )
    launcher.write_text(code, encoding="utf-8")
    return launcher


def _build_posix_shim_content(app_dir: Path, cmd_spec: dict[str, Any], python_exe: Path) -> str:
    ttype = cmd_spec["target_type"]
    lines = ["#!/usr/bin/env bash"]
    py_path_rel = cmd_spec.get("pythonpath")
    if py_path_rel:
        lines.append(f'export PYTHONPATH="{app_dir / py_path_rel}${{PYTHONPATH:+:$PYTHONPATH}}"')

    if ttype == "python_script":
        script_path = app_dir / cmd_spec["script"]
        lines.append(f'exec "{python_exe}" "{script_path}" "$@"')
    elif ttype == "python_module":
        lines.append(f'exec "{python_exe}" -m "{cmd_spec["module"]}" "$@"')
    elif ttype == "shell_pair" and cmd_spec.get("sh_script"):
        sh_path = app_dir / cmd_spec["sh_script"]
        lines.append(f'exec bash "{sh_path}" "$@"')
    else:
        launcher = _ensure_web_launcher_script(app_dir, cmd_spec)
        lines.append(f'exec "{python_exe}" "{launcher}" "$@"')

    return "\n".join(lines) + "\n"


def _build_windows_cmd_content(app_dir: Path, cmd_spec: dict[str, Any], python_exe: Path) -> str:
    ttype = cmd_spec["target_type"]
    lines = ["@echo off", "setlocal"]
    py_path_rel = cmd_spec.get("pythonpath")
    if py_path_rel:
        lines.append(f'set "PYTHONPATH={app_dir / py_path_rel};%PYTHONPATH%"')

    if ttype == "python_script":
        script_path = app_dir / cmd_spec["script"]
        lines.append(f'"{python_exe}" "{script_path}" %*')
    elif ttype == "python_module":
        lines.append(f'"{python_exe}" -m "{cmd_spec["module"]}" %*')
    elif ttype == "shell_pair" and cmd_spec.get("bat_script"):
        bat_path = app_dir / cmd_spec["bat_script"]
        lines.append(f'call "{bat_path}" %*')
    else:
        launcher = _ensure_web_launcher_script(app_dir, cmd_spec)
        lines.append(f'"{python_exe}" "{launcher}" %*')

    lines.append("exit /b %ERRORLEVEL%")
    return "\r\n".join(lines) + "\r\n"


def _build_windows_ps1_content(app_dir: Path, cmd_spec: dict[str, Any], python_exe: Path) -> str:
    ttype = cmd_spec["target_type"]
    lines = []
    py_path_rel = cmd_spec.get("pythonpath")
    if py_path_rel:
        lines.append(f'$env:PYTHONPATH = "{app_dir / py_path_rel};" + $env:PYTHONPATH')

    if ttype == "python_script":
        script_path = app_dir / cmd_spec["script"]
        lines.append(f'& "{python_exe}" "{script_path}" @args')
    elif ttype == "python_module":
        lines.append(f'& "{python_exe}" -m "{cmd_spec["module"]}" @args')
    elif ttype == "shell_pair" and cmd_spec.get("bat_script"):
        bat_path = app_dir / cmd_spec["bat_script"]
        lines.append(f'& cmd.exe /c "`"{bat_path}`"" @args')
    else:
        launcher = _ensure_web_launcher_script(app_dir, cmd_spec)
        lines.append(f'& "{python_exe}" "{launcher}" @args')

    lines.append("exit $LASTEXITCODE")
    return "\r\n".join(lines) + "\r\n"


def create_command_shims(
    bin_dir: Path,
    internal_bin_dir: Path,
    app_dir: Path,
    cmd_spec: dict[str, Any],
    python_exe: Path,
    platform_name: str | None = None,
) -> list[Path]:
    """Create executable CLI wrappers (POSIX bash on Linux, .cmd/.ps1/bash on Windows)."""
    plat = platform_name if platform_name is not None else os.name
    cmd_name = cmd_spec["name"]
    created: list[Path] = []
    target_dirs = [Path(bin_dir)]
    if Path(internal_bin_dir) != Path(bin_dir):
        target_dirs.append(Path(internal_bin_dir))

    posix_text = _build_posix_shim_content(app_dir, cmd_spec, python_exe)
    win_cmd_text = _build_windows_cmd_content(app_dir, cmd_spec, python_exe) if plat == "nt" else ""
    win_ps1_text = _build_windows_ps1_content(app_dir, cmd_spec, python_exe) if plat == "nt" else ""

    for d in target_dirs:
        d.mkdir(parents=True, exist_ok=True)
        sh_file = d / cmd_name
        sh_file.write_text(posix_text, encoding="utf-8")
        if os.name != "nt":
            os.chmod(sh_file, 0o755)
        created.append(sh_file)

        if plat == "nt":
            cmd_file = d / f"{cmd_name}.cmd"
            cmd_file.write_text(win_cmd_text, encoding="utf-8")
            created.append(cmd_file)

            ps1_file = d / f"{cmd_name}.ps1"
            ps1_file.write_text(win_ps1_text, encoding="utf-8")
            created.append(ps1_file)

    return created


def _supports_color() -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()


def _style(text: str, code: str) -> str:
    if not _supports_color():
        return text
    return f"\033[{code}m{text}\033[0m"


def _info(msg: str) -> None:
    print(f"{_style('::', '1;36')} {msg}")


def _ok(msg: str) -> None:
    print(f"{_style('[OK]', '1;32')} {msg}")


def _warn(msg: str) -> None:
    print(f"{_style('[!]', '1;33')} {msg}")


def _err(msg: str) -> None:
    print(f"{_style('[HATA]', '1;31')} {msg}", file=sys.stderr)


def _configure_utf8_streams() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconf = getattr(stream, "reconfigure", None)
        if callable(reconf):
            try:
                reconf(encoding="utf-8", errors="replace")
            except Exception:
                pass


def _parse_requirement_modules(req_file: Path) -> list[str]:
    modules: list[str] = []
    pkg_to_import = {
        "pyqt6": "PyQt6",
        "pyqt5": "PyQt5",
        "pyside6": "PySide6",
        "opencv-python": "cv2",
        "pillow": "PIL",
        "pyyaml": "yaml",
    }
    for line in req_file.read_text(encoding="utf-8", errors="ignore").splitlines():
        clean = line.split("#", 1)[0].strip()
        if not clean or clean.startswith("-"):
            continue
        pkg = re.split(r"[<>=!~;\[]", clean, maxsplit=1)[0].strip()
        if pkg:
            modules.append(pkg_to_import.get(pkg.lower(), pkg.replace("-", "_")))
    return modules


def _modules_importable(python_exe: Path, modules: list[str]) -> bool:
    if not modules:
        return True
    check_code = "; ".join(f"import {m}" for m in modules)
    try:
        proc = subprocess.run(
            [str(python_exe), "-c", check_code],
            capture_output=True,
            text=True,
            timeout=15,
        )
        return proc.returncode == 0
    except Exception:
        return False


def _venv_has_pip(venv_python: Path) -> bool:
    try:
        proc = subprocess.run(
            [str(venv_python), "-m", "pip", "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return proc.returncode == 0
    except Exception:
        return False


def _bootstrap_pip_in_venv(venv_python: Path) -> bool:
    """Download get-pip.py into a temp file and install pip inside venv when ensurepip is absent."""
    get_pip_url = "https://bootstrap.pypa.io/get-pip.py"
    req = urllib.request.Request(get_pip_url, headers={"User-Agent": f"meu/{__version__}"})
    fd, tmp_name = tempfile.mkstemp(prefix="meu_get_pip_", suffix=".py")
    tmp_path = Path(tmp_name)
    try:
        os.close(fd)
        with urllib.request.urlopen(req, timeout=30) as resp:
            tmp_path.write_bytes(resp.read())
        proc = subprocess.run(
            [str(venv_python), str(tmp_path), "--disable-pip-version-check", "-q"],
            capture_output=True,
            text=True,
            timeout=180,
        )
        return proc.returncode == 0 and _venv_has_pip(venv_python)
    except Exception:
        return False
    finally:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass


def _setup_python_env(app_dir: Path, plan: dict[str, Any], no_deps: bool) -> tuple[Path, bool]:
    """Create isolated .venv and install requirements when needed."""
    sys_python = Path(sys.executable)
    if no_deps or not plan.get("needs_venv"):
        return sys_python, False

    venv_dir = app_dir / ".venv"
    venv_python = venv_dir / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    req_file: Path | None = plan.get("requirements_file")

    if not venv_python.is_file():
        _info("İzole Python sanal ortamı (.venv) oluşturuluyor...")
        has_ensurepip = importlib.util.find_spec("ensurepip") is not None
        sys_site_pkgs = os.name != "nt"
        created = False
        last_exc: BaseException | None = None

        if has_ensurepip:
            try:
                venv.EnvBuilder(with_pip=True, system_site_packages=sys_site_pkgs).create(str(venv_dir))
                created = venv_python.is_file()
            except (Exception, SystemExit) as exc:
                last_exc = exc
                rmtree_safe(venv_dir)

        if not created:
            try:
                venv.EnvBuilder(with_pip=False, system_site_packages=sys_site_pkgs).create(str(venv_dir))
                created = venv_python.is_file()
            except (Exception, SystemExit) as exc:
                last_exc = exc
                rmtree_safe(venv_dir)

        if not created:
            if req_file and _modules_importable(sys_python, _parse_requirement_modules(req_file)):
                _warn(f".venv oluşturulamadı ({last_exc}); sistem Python bağımlılıkları zaten mevcut, devam ediliyor.")
                return sys_python, False
            raise RuntimeError(
                f"Sanal ortam (.venv) oluşturulamadı: {last_exc}. Linux'ta 'sudo apt install python3-venv' gerekebilir."
            )

    if req_file and req_file.is_file():
        modules = _parse_requirement_modules(req_file)
        if os.name != "nt" and _modules_importable(venv_python, modules):
            _info("Python bağımlılıkları sistem/sanal ortamda zaten karşılanıyor.")
            return venv_python, True

        if not _venv_has_pip(venv_python):
            uv_bin = shutil.which("uv")
            if uv_bin:
                _info(f"Bağımlılıklar uv ile kuruluyor: {req_file.name}")
                uv_proc = subprocess.run(
                    [uv_bin, "pip", "install", "--python", str(venv_python), "-q", "-r", str(req_file)],
                    capture_output=True,
                    text=True,
                    timeout=300,
                )
                if uv_proc.returncode == 0:
                    return venv_python, True

            _info("ensurepip bulunamadı; sanal ortam için pip önyükleniyor...")
            if not _bootstrap_pip_in_venv(venv_python):
                raise RuntimeError(
                    "Sanal ortam içinde pip bulunamadı (python3-venv eksik). "
                    "Çözüm: 'sudo apt install -y python3-venv' veya '--no-deps' kullanın."
                )

        _info(f"Bağımlılıklar kuruluyor: {req_file.name}")
        proc = subprocess.run(
            [str(venv_python), "-m", "pip", "install", "--disable-pip-version-check", "-q", "-r", str(req_file)],
            capture_output=True,
            text=True,
            timeout=300,
        )
        if proc.returncode != 0:
            if _modules_importable(venv_python, modules):
                _warn("pip kurulumu uyarı verdi ancak gerekli modüller içe aktarılabiliyor; devam ediliyor.")
            else:
                detail = (proc.stderr or proc.stdout or "").strip()
                raise RuntimeError(f"pip bağımlılık kurulumu başarısız oldu:\n{detail}")

    return venv_python, True


def _create_desktop_shortcuts(
    paths: dict[str, Path],
    plan: dict[str, Any],
    repo_name: str,
) -> list[Path]:
    """Create .desktop launcher on Linux or .lnk shortcut on Windows Desktop when appropriate."""
    entry = plan.get("desktop_entry")
    if not entry:
        return []

    desktop_dir = paths["desktop_dir"]
    desktop_dir.mkdir(parents=True, exist_ok=True)
    cmd_name = entry["command"]
    display_name = entry.get("name", repo_name)
    comment = entry.get("comment", display_name)
    created: list[Path] = []

    if os.name != "nt":
        exec_path = paths["bin_dir"] / cmd_name
        desktop_file = desktop_dir / f"meu-{repo_name.lower()}.desktop"
        content = (
            "[Desktop Entry]\n"
            "Type=Application\n"
            f"Name={display_name}\n"
            f"Comment={comment}\n"
            f"Exec={exec_path}\n"
            f"Icon={entry.get('icon', 'utilities-terminal')}\n"
            "Terminal=false\n"
            f"Categories={entry.get('categories', 'Utility;')}\n"
        )
        desktop_file.write_text(content, encoding="utf-8")
        os.chmod(desktop_file, 0o755)
        created.append(desktop_file)
    elif not os.environ.get("MEU_HOME"):
        target_cmd = paths["bin_dir"] / f"{cmd_name}.cmd"
        lnk_path = desktop_dir / f"{display_name}.lnk"
        ps_cmd = (
            "$ws = New-Object -ComObject WScript.Shell; "
            f"$s = $ws.CreateShortcut('{str(lnk_path).replace(chr(39), chr(39)*2)}'); "
            f"$s.TargetPath = '{str(target_cmd).replace(chr(39), chr(39)*2)}'; "
            f"$s.WorkingDirectory = '{str(paths['apps_dir'] / repo_name).replace(chr(39), chr(39)*2)}'; "
            f"$s.Description = '{str(comment).replace(chr(39), chr(39)*2)}'; "
            "$s.Save()"
        )
        ps_bin = shutil.which("powershell") or shutil.which("pwsh")
        if ps_bin:
            proc = subprocess.run([ps_bin, "-NoProfile", "-Command", ps_cmd], capture_output=True, text=True, timeout=20)
            if proc.returncode == 0 and lnk_path.exists():
                created.append(lnk_path)

    return created


def _check_missing_apt_packages(apt_hints: list[str]) -> list[str]:
    if os.name == "nt" or not apt_hints or not shutil.which("dpkg-query"):
        return []
    missing: list[str] = []
    for pkg in apt_hints:
        proc = subprocess.run(
            ["dpkg-query", "-W", "-f=${Status}", pkg],
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0 or "install ok installed" not in proc.stdout:
            missing.append(pkg)
    return missing


def _path_contains_dir(target_dir: Path) -> bool:
    norm_target = os.path.normcase(os.path.normpath(str(target_dir)))
    for part in os.environ.get("PATH", "").split(os.pathsep):
        if not part:
            continue
        if os.path.normcase(os.path.normpath(part)) == norm_target:
            return True
    return False


def _ensure_user_path(bin_dir: Path) -> bool:
    """Idempotently add bin_dir to the user's persistent PATH on Linux or Windows."""
    if os.environ.get("MEU_HOME"):
        return False

    if os.name == "nt":
        try:
            import ctypes
            import winreg

            target_str = str(bin_dir)
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_READ | winreg.KEY_WRITE) as key:
                try:
                    current_val, val_type = winreg.QueryValueEx(key, "Path")
                except FileNotFoundError:
                    current_val, val_type = "", winreg.REG_EXPAND_SZ
                entries = [p for p in current_val.split(";") if p.strip()]
                norm_target = os.path.normcase(os.path.normpath(target_str))
                already = any(os.path.normcase(os.path.normpath(p)) == norm_target for p in entries)
                if not already:
                    entries.append(target_str)
                    new_val = ";".join(entries)
                    winreg.SetValueEx(key, "Path", 0, val_type or winreg.REG_EXPAND_SZ, new_val)
                    try:
                        ctypes.windll.user32.SendMessageTimeoutW(
                            0xFFFF, 0x001A, 0, "Environment", 0x0002, 2000, None
                        )
                    except Exception:
                        pass
                if not _path_contains_dir(bin_dir):
                    os.environ["PATH"] = f"{target_str};{os.environ.get('PATH', '')}"
                return not already
        except Exception as exc:
            _warn(f"Windows PATH otomatik güncellenemedi: {exc}")
            return False

    # POSIX: ~/.bashrc and ~/.profile
    export_block = (
        "\n# >>> meu path >>>\n"
        f'if [ -d "{bin_dir}" ] && [[ ":$PATH:" != *":{bin_dir}:"* ]]; then\n'
        f'    export PATH="{bin_dir}:$PATH"\n'
        "fi\n"
        "# <<< meu path <<<\n"
    )
    updated_any = False
    for rc_name in (".bashrc", ".profile"):
        rc_path = Path.home() / rc_name
        try:
            existing = rc_path.read_text(encoding="utf-8") if rc_path.exists() else ""
            if "# >>> meu path >>>" not in existing and str(bin_dir) not in existing:
                rc_path.write_text(existing.rstrip("\n") + export_block, encoding="utf-8")
                updated_any = True
        except OSError:
            pass
    return updated_any


def _install_single(
    raw_target: str,
    *,
    force: bool = False,
    no_deps: bool = False,
    no_desktop: bool = False,
    branch_override: str | None = None,
    docker_up: bool = False,
    prefer_git: bool = True,
) -> int:
    paths = get_meu_paths()
    registry = Registry(paths["registry_file"])

    spec = resolve_target(raw_target)
    if branch_override:
        spec = TargetSpec(
            owner=spec.owner,
            repo=spec.repo,
            branch=branch_override,
            clone_url=spec.clone_url,
            zip_url=f"https://codeload.github.com/{spec.owner}/{spec.repo}/zip/refs/heads/{branch_override}",
            html_url=spec.html_url,
            is_known_meucak=spec.is_known_meucak,
        )

    existing = registry.get_app(spec.repo)
    app_dir = paths["apps_dir"] / spec.repo
    if existing and app_dir.exists() and not force:
        cmds = ", ".join(existing.get("commands", [])) or spec.repo
        _ok(f"{spec.repo} zaten kurulu (sürüm: {existing.get('version', '?')}, komutlar: {cmds}).")
        _info(f"Güncellemek için: meu update {spec.repo}  |  Yeniden kurmak için: meu install {spec.repo} --force")
        return 0

    _info(f"{spec.owner}/{spec.repo} indiriliyor ({spec.html_url})...")
    dl_meta = download_repo(
        spec,
        app_dir,
        prefer_git=prefer_git,
        cache_dir=paths["cache_dir"],
    )
    _ok(f"İndirildi ({dl_meta['method']} • {dl_meta['version']}) -> {app_dir}")

    compat_notes = apply_compat_patches(app_dir, spec.repo)
    for note in compat_notes:
        _info(f"Uyumluluk uyarlaması: {note}")

    plan = inspect_project(app_dir, spec.repo)
    python_exe, has_venv = _setup_python_env(app_dir, plan, no_deps=no_deps)

    # Remove stale shims if reinstalling/updating
    if existing:
        for old_shim in existing.get("shims", []):
            p = Path(old_shim)
            if p.exists() or p.is_symlink():
                try:
                    p.unlink()
                except OSError:
                    pass

    all_shims: list[Path] = []
    for cmd_spec in plan["commands"]:
        shims = create_command_shims(
            paths["bin_dir"],
            paths["internal_bin_dir"],
            app_dir,
            cmd_spec,
            python_exe,
        )
        all_shims.extend(shims)

    desktop_files: list[Path] = []
    if not no_desktop:
        desktop_files = _create_desktop_shortcuts(paths, plan, spec.repo)

    if docker_up and plan.get("has_docker_compose"):
        docker_bin = shutil.which("docker")
        if docker_bin:
            _info(f"Docker servisi ayağa kaldırılıyor: {spec.repo}")
            subprocess.run([docker_bin, "compose", "up", "-d"], cwd=str(app_dir), check=False)
        else:
            _warn("Docker bulunamadı; sadece başlatıcı kısayolları kuruldu.")

    now_iso = datetime.now(timezone.utc).isoformat(timespec="seconds")
    installed_at = existing.get("installed_at", now_iso) if existing else now_iso
    cmd_names = [c["name"] for c in plan["commands"]]

    record = {
        "name": spec.repo,
        "owner": spec.owner,
        "html_url": spec.html_url,
        "branch": spec.branch,
        "method": dl_meta["method"],
        "version": dl_meta["version"],
        "kind": plan["kind"],
        "description": plan.get("description", ""),
        "app_dir": str(app_dir),
        "python_exe": str(python_exe),
        "commands": cmd_names,
        "shims": [str(p) for p in all_shims],
        "desktop_files": [str(p) for p in desktop_files],
        "has_venv": has_venv,
        "installed_at": installed_at,
        "updated_at": now_iso,
    }
    registry.set_app(spec.repo, record)

    _ok(f"{spec.repo} başarıyla kuruldu!")
    if cmd_names:
        _info(f"Terminal komutu: {', '.join(cmd_names)}")
    if desktop_files:
        _info(f"Masaüstü kısayolu: {', '.join(str(p) for p in desktop_files)}")

    missing_apt = _check_missing_apt_packages(plan.get("apt_hints", []))
    if missing_apt:
        _warn(f"Önerilen sistem paketleri eksik olabilir: sudo apt install -y {' '.join(missing_apt)}")

    if not os.environ.get("MEU_HOME") and not _path_contains_dir(paths["bin_dir"]):
        _warn(f"'{paths['bin_dir']}' PATH içinde görünmüyor. Eklemek için: meu doctor --fix")

    return 0


def cmd_install(args: argparse.Namespace) -> int:
    exit_code = 0
    for target in args.targets:
        try:
            rc = _install_single(
                target,
                force=args.force,
                no_deps=args.no_deps,
                no_desktop=args.no_desktop,
                branch_override=args.branch,
                docker_up=args.docker,
                prefer_git=not args.zip,
            )
            if rc != 0:
                exit_code = rc
        except Exception as exc:
            _err(f"{target}: {exc}")
            exit_code = 1
    return exit_code


def cmd_uninstall(args: argparse.Namespace) -> int:
    paths = get_meu_paths()
    registry = Registry(paths["registry_file"])
    exit_code = 0

    for target in args.targets:
        record = registry.get_app(target)
        if record is None:
            try:
                spec = resolve_target(target)
                record = registry.get_app(spec.repo)
            except ValueError:
                record = None

        if record is None:
            _err(f"Kurulu proje bulunamadı: {target}")
            exit_code = 1
            continue

        for shim in record.get("shims", []):
            p = Path(shim)
            if p.exists() or p.is_symlink():
                try:
                    p.unlink()
                except OSError as exc:
                    _warn(f"Komut kaldırılamadı ({p}): {exc}")

        for dfile in record.get("desktop_files", []):
            p = Path(dfile)
            if p.exists() or p.is_symlink():
                try:
                    p.unlink()
                except OSError as exc:
                    _warn(f"Kısayol kaldırılamadı ({p}): {exc}")

        app_dir = Path(record["app_dir"])
        if app_dir.exists():
            rmtree_safe(app_dir)

        registry.remove_app(record["name"])
        _ok(f"{record['name']} tamamen kaldırıldı.")
    return exit_code


def cmd_update(args: argparse.Namespace) -> int:
    paths = get_meu_paths()
    registry = Registry(paths["registry_file"])
    targets = list(args.targets)

    if args.all or not targets:
        installed = registry.list_apps()
        if not installed:
            _info("Güncellenecek kurulu proje yok.")
            return 0
        targets = [app["name"] for app in installed]

    exit_code = 0
    for target in targets:
        rec = registry.get_app(target)
        src_ref = f"{rec['owner']}/{rec['name']}" if rec and rec.get("owner") else target
        try:
            rc = _install_single(
                src_ref,
                force=True,
                no_deps=args.no_deps,
                no_desktop=args.no_desktop,
                branch_override=rec.get("branch") if rec else None,
            )
            if rc != 0:
                exit_code = rc
        except Exception as exc:
            _err(f"{target} güncellenemedi: {exc}")
            exit_code = 1
    return exit_code


def cmd_list(args: argparse.Namespace) -> int:
    paths = get_meu_paths()
    registry = Registry(paths["registry_file"])
    apps = registry.list_apps()

    if getattr(args, "json", False):
        print(json.dumps(apps, indent=2, ensure_ascii=False))
        return 0

    if not apps:
        _info("Henüz meu ile kurulmuş proje yok. Mevcut projeler için: meu search")
        return 0

    rows = []
    for app in apps:
        app_exists = Path(app.get("app_dir", "")).is_dir()
        status = "Hazır" if app_exists else "Eksik"
        cmds = ", ".join(app.get("commands", [])) or "-"
        rows.append(
            (
                app.get("name", "?"),
                app.get("kind", "?"),
                cmds,
                app.get("version", "?"),
                app.get("method", "?"),
                status,
            )
        )

    headers = ("PROJE", "TÜR", "KOMUTLAR", "SÜRÜM", "YÖNTEM", "DURUM")
    widths = [max(len(h), *(len(r[i]) for r in rows)) for i, h in enumerate(headers)]
    fmt = "  ".join(f"{{:<{w}}}" for w in widths)
    print(_style(fmt.format(*headers), "1"))
    print("  ".join("-" * w for w in widths))
    for r in rows:
        print(fmt.format(*r))
    return 0


def _fetch_live_meucak_repos(timeout: float = 4.0) -> list[dict[str, Any]]:
    url = f"https://api.github.com/users/{DEFAULT_OWNER}/repos?per_page=100&sort=updated"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": f"meu/{__version__}",
            "Accept": "application/vnd.github+json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
            if isinstance(payload, list):
                return [item for item in payload if isinstance(item, dict) and item.get("name")]
    except Exception:
        pass
    return []


def cmd_search(args: argparse.Namespace) -> int:
    paths = get_meu_paths()
    registry = Registry(paths["registry_file"])
    installed_names = {app["name"].lower() for app in registry.list_apps()}

    catalog: dict[str, dict[str, Any]] = {
        name: {
            "name": name,
            "kind": meta["kind"],
            "description": meta["description"],
            "aliases": meta.get("aliases", []),
            "commands": [e["name"] for e in meta.get("entrypoints", [])],
        }
        for name, meta in MEUCAK_CATALOG.items()
    }

    if not args.offline:
        for repo in _fetch_live_meucak_repos():
            rname = repo["name"]
            if rname not in catalog and rname != ".github":
                catalog[rname] = {
                    "name": rname,
                    "kind": (repo.get("language") or "repo").lower(),
                    "description": repo.get("description") or "GitHub deposu (otomatik algılama)",
                    "aliases": [],
                    "commands": [rname.lower()],
                }
            elif rname in catalog and not catalog[rname]["description"] and repo.get("description"):
                catalog[rname]["description"] = repo["description"]

    query = (args.query or "").strip().lower()
    items = []
    for name in sorted(catalog, key=str.lower):
        entry = catalog[name]
        haystack = " ".join(
            [
                entry["name"],
                entry["description"],
                entry["kind"],
                " ".join(entry["aliases"]),
                " ".join(entry["commands"]),
            ]
        ).lower()
        if not query or query in haystack:
            items.append(entry)

    if not items:
        suggestions = suggest_similar_repos(query, list(catalog.keys()))
        _warn(f"'{args.query}' için eşleşen proje bulunamadı.")
        if suggestions:
            _info(f"Bunu mu aradınız: {', '.join(suggestions)}")
        return 0

    for entry in items:
        badge = _style("[KURULU]", "1;32") if entry["name"].lower() in installed_names else _style("[MEVCUT]", "0;36")
        alias_str = f" (diğer ad: {', '.join(entry['aliases'])})" if entry["aliases"] else ""
        print(f"{badge} {_style(entry['name'], '1')}{alias_str}  [{entry['kind']}]")
        print(f"         {entry['description']}")
        print(f"         Kurulum: meu install {entry['name']}")
    return 0


def cmd_info(args: argparse.Namespace) -> int:
    paths = get_meu_paths()
    registry = Registry(paths["registry_file"])
    spec = resolve_target(args.target)
    rec = registry.get_app(spec.repo)
    cat = MEUCAK_CATALOG.get(spec.repo)

    print(_style(f"Proje: {spec.owner}/{spec.repo}", "1"))
    print(f"GitHub: {spec.html_url}")
    if cat:
        print(f"Tür: {cat['kind']}")
        print(f"Açıklama: {cat['description']}")
        if cat.get("aliases"):
            print(f"Kısa Adlar: {', '.join(cat['aliases'])}")
        print(f"Platformlar: {', '.join(cat.get('platforms', []))}")
        cmds = [e["name"] for e in cat.get("entrypoints", [])]
        if cmds:
            print(f"Komutlar: {', '.join(cmds)}")
        if cat.get("port"):
            print(f"Varsayılan Port: {cat['port']}")
    if rec:
        print(f"Durum: {_style('Kurulu', '1;32')} ({rec.get('version', '?')} • {rec.get('method', '?')})")
        print(f"Dizin: {rec.get('app_dir')}")
        print(f"Komutlar: {', '.join(rec.get('commands', []))}")
        if rec.get("desktop_files"):
            print(f"Kısayollar: {', '.join(rec['desktop_files'])}")
    else:
        print(f"Durum: Kurulu değil (kurmak için: meu install {spec.repo})")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    paths = get_meu_paths()
    registry = Registry(paths["registry_file"])
    spec = resolve_target(args.target)
    rec = registry.get_app(spec.repo)

    if rec is None or not Path(rec.get("app_dir", "")).is_dir():
        _info(f"{spec.repo} kurulu değil; önce otomatik indirip kuruluyor...")
        rc = _install_single(args.target)
        if rc != 0:
            return rc
        rec = registry.get_app(spec.repo)
        if rec is None:
            _err(f"{spec.repo} kurulumu doğrulanamadı.")
            return 1

    commands = rec.get("commands", [])
    if not commands:
        _err(f"{rec['name']} için tanımlı çalıştırılabilir komut yok. Dizin: {rec.get('app_dir')}")
        return 1

    primary_cmd = commands[0]
    if os.name == "nt":
        shim = paths["bin_dir"] / f"{primary_cmd}.cmd"
        cmd_list = ["cmd", "/c", str(shim), *args.extra_args]
    else:
        shim = paths["bin_dir"] / primary_cmd
        cmd_list = [str(shim), *args.extra_args]

    if not shim.exists():
        _err(f"Başlatıcı bulunamadı: {shim}. Onarmak için: meu install {rec['name']} --force")
        return 1

    proc = subprocess.run(cmd_list)
    return proc.returncode


def cmd_doctor(args: argparse.Namespace) -> int:
    paths = get_meu_paths()
    registry = Registry(paths["registry_file"])

    print(_style(f"meu v{__version__} Sistem Tanılama ({os.name})", "1"))
    print(f"MEU Ana Dizini : {paths['home']}")
    print(f"Uygulamalar    : {paths['apps_dir']}")
    print(f"Komut Dizini   : {paths['bin_dir']}")
    print(f"Kısayol Dizini : {paths['desktop_dir']}")

    py_ok = sys.version_info >= (3, 8)
    print(f"Python         : {sys.version.split()[0]} ({sys.executable}) [{'OK' if py_ok else 'ESKİ'}]")

    git_bin = shutil.which("git")
    print(f"Git            : {git_bin or 'Yok (ZIP yedek indirme kullanılacak)'}")

    docker_bin = shutil.which("docker")
    print(f"Docker         : {docker_bin or 'Yok (yalnızca konteyner servisleri için gerekli)'}")

    in_path = _path_contains_dir(paths["bin_dir"])
    print(f"PATH Durumu    : {'Hazır' if in_path else 'Eksik (' + str(paths['bin_dir']) + ')'}")

    if args.fix:
        for key in ("home", "core_dir", "apps_dir", "cache_dir", "bin_dir", "internal_bin_dir", "desktop_dir"):
            paths[key].mkdir(parents=True, exist_ok=True)
        if _ensure_user_path(paths["bin_dir"]):
            _ok(f"PATH güncellendi: {paths['bin_dir']} (yeni terminalde aktif olur)")
        else:
            _ok("Dizinler ve PATH doğrulandı.")

    apps = registry.list_apps()
    broken = 0
    for app in apps:
        app_ok = Path(app.get("app_dir", "")).is_dir()
        shims_ok = all(Path(s).exists() for s in app.get("shims", []))
        if not (app_ok and shims_ok):
            broken += 1
            _warn(f"Bozuk kurulum tespit edildi: {app['name']} (onarmak için: meu install {app['name']} --force)")

    if broken == 0:
        _ok(f"Kayıtlı {len(apps)} uygulamanın tamamı sağlıklı.")
    return 0


def cmd_self_install(args: argparse.Namespace) -> int:
    paths = get_meu_paths()
    for key in ("home", "core_dir", "apps_dir", "cache_dir", "bin_dir", "internal_bin_dir"):
        paths[key].mkdir(parents=True, exist_ok=True)

    src_self = Path(__file__).resolve()
    dst_self = paths["core_dir"] / "meu.py"
    if src_self != dst_self.resolve():
        shutil.copy2(src_self, dst_self)
        if os.name != "nt":
            os.chmod(dst_self, 0o755)

    cmd_spec = {"name": "meu", "target_type": "python_script", "script": "meu.py", "gui": False}
    shims = create_command_shims(
        paths["bin_dir"],
        paths["internal_bin_dir"],
        paths["core_dir"],
        cmd_spec,
        Path(sys.executable),
    )

    path_added = _ensure_user_path(paths["bin_dir"])
    _ok(f"meu v{__version__} başarıyla kuruldu!")
    _info(f"Çekirdek : {dst_self}")
    _info(f"Komutlar : {', '.join(str(p) for p in shims)}")
    if path_added:
        _info(f"PATH eklendi ({paths['bin_dir']}). Yeni bir terminal açarak doğrudan 'meu' yazabilirsiniz.")
    elif not os.environ.get("MEU_HOME") and not _path_contains_dir(paths["bin_dir"]):
        _warn(f"'{paths['bin_dir']}' PATH içinde değil; eklemek için: meu doctor --fix")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="meu",
        description="meu — Windows 10 ve Linux için GitHub (meucak) proje & paket yöneticisi.",
    )
    parser.add_argument("-V", "--version", action="version", version=f"meu {__version__}")
    sub = parser.add_subparsers(dest="command", metavar="KOMUT")

    p_install = sub.add_parser(
        "install",
        aliases=["i", "add", "kur", "indir"],
        help="GitHub proje adı veya linkinden indir ve kur (örn. meu install recep)",
    )
    p_install.add_argument("targets", nargs="+", help="Proje adı (recep) veya GitHub linki")
    p_install.add_argument("-f", "--force", action="store_true", help="Mevcut kurulumun üzerine yeniden kur")
    p_install.add_argument("--no-deps", action="store_true", help="Python sanal ortam/pip kurulumunu atla")
    p_install.add_argument("--no-desktop", action="store_true", help="Masaüstü/uygulama kısayolu oluşturma")
    p_install.add_argument("-b", "--branch", default=None, help="Belirli bir Git dalı/etiketi kur")
    p_install.add_argument("--docker", action="store_true", help="Docker Compose servisi varsa kurulumda başlat")
    p_install.add_argument("--zip", action="store_true", help="Git yerine doğrudan GitHub ZIP arşivi kullan")
    p_install.set_defaults(func=cmd_install)

    p_uninstall = sub.add_parser(
        "uninstall",
        aliases=["remove", "rm", "sil", "kaldir"],
        help="Kurulu projeyi komut ve kısayollarıyla birlikte temizce kaldır",
    )
    p_uninstall.add_argument("targets", nargs="+", help="Kaldırılacak proje adları")
    p_uninstall.set_defaults(func=cmd_uninstall)

    p_update = sub.add_parser(
        "update",
        aliases=["upgrade", "guncelle"],
        help="Kurulu projeyi veya tüm projeleri GitHub'dan güncelle",
    )
    p_update.add_argument("targets", nargs="*", help="Güncellenecek proje adları (boşsa tümü)")
    p_update.add_argument("--all", action="store_true", help="Kurulu tüm projeleri güncelle")
    p_update.add_argument("--no-deps", action="store_true", help="Bağımlılık kurulumunu atla")
    p_update.add_argument("--no-desktop", action="store_true", help="Kısayol oluşturmayı atla")
    p_update.set_defaults(func=cmd_update)

    p_list = sub.add_parser(
        "list",
        aliases=["ls", "liste"],
        help="Kurulu projeleri listele",
    )
    p_list.add_argument("--json", action="store_true", help="JSON biçiminde yazdır")
    p_list.set_defaults(func=cmd_list)

    p_search = sub.add_parser(
        "search",
        aliases=["catalog", "katalog", "ara"],
        help="Mevcut meucak projelerini listele veya ara",
    )
    p_search.add_argument("query", nargs="?", default="", help="Arama kelimesi")
    p_search.add_argument("--offline", action="store_true", help="Yalnızca yerleşik kataloğu kullan")
    p_search.set_defaults(func=cmd_search)

    p_info = sub.add_parser(
        "info",
        aliases=["show", "bilgi"],
        help="Proje hakkında ayrıntılı bilgi göster",
    )
    p_info.add_argument("target", help="Proje adı veya GitHub linki")
    p_info.set_defaults(func=cmd_info)

    p_run = sub.add_parser(
        "run",
        aliases=["start", "exec", "calistir", "ac"],
        help="Kurulu projeyi çalıştır (kurulu değilse önce otomatik kurar)",
    )
    p_run.add_argument("target", help="Çalıştırılacak proje adı veya linki")
    p_run.add_argument("extra_args", nargs=argparse.REMAINDER, help="Uygulamaya iletilecek argümanlar")
    p_run.set_defaults(func=cmd_run)

    p_doctor = sub.add_parser(
        "doctor",
        aliases=["check", "kontrol"],
        help="Sistem gereksinimlerini, PATH ayarını ve kurulumları denetle",
    )
    p_doctor.add_argument("--fix", action="store_true", help="Eksik dizinleri ve kullanıcı PATH ayarını onar")
    p_doctor.set_defaults(func=cmd_doctor)

    p_self = sub.add_parser(
        "self-install",
        aliases=["setup"],
        help="meu aracının kendisini sisteme ve PATH'e kur",
    )
    p_self.set_defaults(func=cmd_self_install)

    return parser


def main(argv: list[str] | None = None) -> int:
    _configure_utf8_streams()
    parser = build_parser()
    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        parser.print_help()
        return 0
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
