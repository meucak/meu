from __future__ import annotations

import contextlib
import io
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import meu  # noqa: E402


class TestTargetResolutionAndCatalog(unittest.TestCase):
    def test_bare_name_resolves_to_meucak(self):
        spec = meu.resolve_target("recep")
        self.assertEqual(spec.owner, "meucak")
        self.assertEqual(spec.repo, "recep")
        self.assertIsNone(spec.branch)
        self.assertEqual(spec.clone_url, "https://github.com/meucak/recep.git")
        self.assertEqual(spec.html_url, "https://github.com/meucak/recep")
        self.assertTrue(spec.is_known_meucak)

    def test_case_insensitive_and_aliases(self):
        spec_upper = meu.resolve_target("RECEP")
        self.assertEqual(spec_upper.repo, "recep")

        spec_mwb = meu.resolve_target("mousewithborders-android")
        self.assertEqual(spec_mwb.repo, "MouseWithBorders-Android")
        self.assertTrue(spec_mwb.is_known_meucak)

        spec_mwb_alias = meu.resolve_target("mwb")
        self.assertEqual(spec_mwb_alias.repo, "MouseWithBorders-Android")

        spec_aura = meu.resolve_target("aura-lan")
        self.assertEqual(spec_aura.repo, "kush")

        spec_cam = meu.resolve_target("kamera")
        self.assertEqual(spec_cam.repo, "toshi-camera")

        spec_bomb = meu.resolve_target("cs-bomb")
        self.assertEqual(spec_bomb.repo, "recep")

    def test_github_url_variants(self):
        variants = [
            "github.com/meucak/recep",
            "https://github.com/meucak/recep/",
            "https://github.com/meucak/recep.git",
            "http://github.com/meucak/recep",
            "git@github.com:meucak/recep.git",
            "meucak/recep",
        ]
        for raw in variants:
            with self.subTest(raw=raw):
                spec = meu.resolve_target(raw)
                self.assertEqual(spec.owner, "meucak")
                self.assertEqual(spec.repo, "recep")
                self.assertIsNone(spec.branch)
                self.assertEqual(spec.clone_url, "https://github.com/meucak/recep.git")

    def test_tree_branch_and_at_branch(self):
        spec1 = meu.resolve_target("https://github.com/meucak/perf/tree/main")
        self.assertEqual(spec1.owner, "meucak")
        self.assertEqual(spec1.repo, "perf")
        self.assertEqual(spec1.branch, "main")

        spec2 = meu.resolve_target("meucak/tessera@dev")
        self.assertEqual(spec2.owner, "meucak")
        self.assertEqual(spec2.repo, "tessera")
        self.assertEqual(spec2.branch, "dev")

        spec3 = meu.resolve_target("sortingen@v1.1.0")
        self.assertEqual(spec3.owner, "meucak")
        self.assertEqual(spec3.repo, "sortingen")
        self.assertEqual(spec3.branch, "v1.1.0")

    def test_external_owner_allowed(self):
        spec = meu.resolve_target("https://github.com/octocat/Hello-World")
        self.assertEqual(spec.owner, "octocat")
        self.assertEqual(spec.repo, "Hello-World")
        self.assertFalse(spec.is_known_meucak)

    def test_invalid_target_raises(self):
        with self.assertRaises(ValueError):
            meu.resolve_target("")
        with self.assertRaises(ValueError):
            meu.resolve_target("   ")

    def test_suggest_similar_repos(self):
        self.assertIn("sortingen", meu.suggest_similar_repos("sortngn"))
        self.assertIn("recep", meu.suggest_similar_repos("recp"))
        self.assertIn("toshi-camera", meu.suggest_similar_repos("toshi-cam"))

    def test_catalog_completeness(self):
        expected = {
            "perf",
            "sortingen",
            "recep",
            "borfek",
            "tessera",
            "toshi-camera",
            "fil",
            "fleet-deck",
            "kush",
            "pdf-studio",
            "antigravity-mobile-app",
            "MouseWithBorders-Android",
        }
        self.assertTrue(expected.issubset(set(meu.MEUCAK_CATALOG.keys())))

    def test_get_meu_paths_isolated_posix_and_nt(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = {"MEU_HOME": tmp, "USERPROFILE": tmp}
            posix_paths = meu.get_meu_paths(env=env, platform_name="posix")
            self.assertEqual(posix_paths["home"], Path(tmp))
            self.assertEqual(posix_paths["apps_dir"], Path(tmp) / "apps")
            self.assertEqual(posix_paths["bin_dir"], Path(tmp) / "bin")
            self.assertEqual(posix_paths["internal_bin_dir"], Path(tmp) / "bin")
            self.assertEqual(posix_paths["registry_file"], Path(tmp) / "registry.json")
            self.assertEqual(posix_paths["desktop_dir"], Path(tmp) / "desktop")

            nt_paths = meu.get_meu_paths(env=env, platform_name="nt")
            self.assertEqual(nt_paths["home"], Path(tmp))
            self.assertEqual(nt_paths["bin_dir"], Path(tmp) / "bin")
            self.assertEqual(nt_paths["internal_bin_dir"], Path(tmp) / "bin")

    def test_get_meu_paths_default_posix_uses_local_bin(self):
        paths = meu.get_meu_paths(env={"HOME": "/home/tester"}, platform_name="posix")
        self.assertEqual(paths["home"], Path("/home/tester/.meu"))
        self.assertEqual(paths["bin_dir"], Path("/home/tester/.local/bin"))
        self.assertEqual(paths["internal_bin_dir"], Path("/home/tester/.meu/bin"))
        self.assertEqual(paths["desktop_dir"], Path("/home/tester/.local/share/applications"))


class TestRegistryAndDownloader(unittest.TestCase):
    def test_rmtree_safe_removes_readonly_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "readonly_tree"
            sub = root / ".git" / "objects"
            sub.mkdir(parents=True)
            locked = sub / "pack.idx"
            locked.write_text("packed", encoding="utf-8")
            os.chmod(locked, stat.S_IREAD)
            meu.rmtree_safe(root)
            self.assertFalse(root.exists())

    def test_registry_atomic_crud_and_corrupt_recovery(self):
        with tempfile.TemporaryDirectory() as tmp:
            reg_file = Path(tmp) / "registry.json"
            reg = meu.Registry(reg_file)
            self.assertEqual(reg.list_apps(), [])

            reg.set_app("recep", {"name": "recep", "kind": "pyqt-gui", "commands": ["recep"]})
            self.assertIsNotNone(reg.get_app("recep"))
            self.assertIsNotNone(reg.get_app("RECEP"))
            self.assertEqual(len(reg.list_apps()), 1)

            removed = reg.remove_app("recep")
            self.assertEqual(removed["name"], "recep")
            self.assertEqual(reg.list_apps(), [])

            reg_file.write_text("{bad json", encoding="utf-8")
            data = reg.load()
            self.assertEqual(data.get("apps"), {})

    def test_extract_zip_root_stripped_and_zip_slip_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            good_zip = tmp_path / "good.zip"
            with zipfile.ZipFile(good_zip, "w") as zf:
                zf.writestr("recep-main/README.md", "# recep\n")
                info = zipfile.ZipInfo("recep-main/cs_bomb_game.py")
                info.external_attr = (0o755 & 0xFFFF) << 16
                zf.writestr(info, "print('ok')\n")

            dest = tmp_path / "out"
            meu.extract_zip_root_stripped(good_zip, dest)
            self.assertTrue((dest / "README.md").is_file())
            self.assertTrue((dest / "cs_bomb_game.py").is_file())
            self.assertFalse((dest / "recep-main").exists())
            if os.name != "nt":
                self.assertTrue(os.access(dest / "cs_bomb_game.py", os.X_OK))

            bad_zip = tmp_path / "bad.zip"
            with zipfile.ZipFile(bad_zip, "w") as zf:
                zf.writestr("recep-main/../../evil.txt", "pwned")
            with self.assertRaises(ValueError):
                meu.extract_zip_root_stripped(bad_zip, tmp_path / "bad_out")

    def test_download_repo_zip_fallback_with_mock_opener(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w") as zf:
                zf.writestr("sortingen-main/sortingen.py", "print('hello')\n")
            zip_bytes = buf.getvalue()

            class FakeResp:
                def __init__(self, payload: bytes):
                    self._payload = payload

                def read(self, n: int = -1) -> bytes:
                    return self._payload

                def __enter__(self):
                    return self

                def __exit__(self, *exc):
                    return False

            called_urls: list[str] = []

            def fake_opener(req, timeout=30):
                url = getattr(req, "full_url", str(req))
                called_urls.append(url)
                return FakeResp(zip_bytes)

            spec = meu.resolve_target("sortingen")
            dest = tmp_path / "apps" / "sortingen"
            meta = meu.download_repo(
                spec,
                dest,
                prefer_git=False,
                cache_dir=tmp_path / "cache",
                opener=fake_opener,
            )
            self.assertEqual(meta["method"], "zip")
            self.assertTrue((dest / "sortingen.py").is_file())
            self.assertTrue(len(called_urls) >= 1)

    def test_download_repo_via_local_git_clone(self):
        import shutil

        if not shutil.which("git"):
            self.skipTest("git not available")
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            origin = tmp_path / "origin"
            origin.mkdir()
            subprocess.run(["git", "init", "-b", "main"], cwd=origin, check=True, stdout=subprocess.DEVNULL)
            subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=origin, check=True)
            subprocess.run(["git", "config", "user.name", "Tester"], cwd=origin, check=True)
            (origin / "perf.py").write_text("print('perf')\n", encoding="utf-8")
            subprocess.run(["git", "add", "."], cwd=origin, check=True)
            subprocess.run(["git", "commit", "-m", "init"], cwd=origin, check=True, stdout=subprocess.DEVNULL)

            spec = meu.TargetSpec(
                owner="meucak",
                repo="perf",
                branch="main",
                clone_url=origin.as_uri(),
                zip_url="",
                html_url="https://github.com/meucak/perf",
                is_known_meucak=True,
            )
            dest = tmp_path / "installed_perf"
            meta = meu.download_repo(spec, dest, prefer_git=True)
            self.assertEqual(meta["method"], "git")
            self.assertTrue((dest / "perf.py").is_file())
            self.assertTrue(bool(meta["version"]))


class TestInspectorCompatAndShims(unittest.TestCase):
    def test_inspect_known_and_unknown_projects(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            # 1. recep
            recep_dir = root / "recep"
            recep_dir.mkdir()
            (recep_dir / "cs_bomb_game.py").write_text("import PyQt6\n", encoding="utf-8")
            (recep_dir / "monster_claw_widget.py").write_text("import PyQt6\n", encoding="utf-8")
            (recep_dir / "requirements.txt").write_text("PyQt6>=6.4.0\n", encoding="utf-8")
            plan_recep = meu.inspect_project(recep_dir, "recep")
            self.assertEqual(plan_recep["kind"], "pyqt-gui")
            self.assertTrue(plan_recep["needs_venv"])
            cmd_names = [c["name"] for c in plan_recep["commands"]]
            self.assertEqual(cmd_names, ["recep", "cs-bomb", "monster-claw"])

            # 2. sortingen
            sort_dir = root / "sortingen"
            sort_dir.mkdir()
            (sort_dir / "sortingen.py").write_text("print('ok')\n", encoding="utf-8")
            plan_sort = meu.inspect_project(sort_dir, "sortingen")
            self.assertEqual(plan_sort["kind"], "python-cli")
            self.assertFalse(plan_sort["needs_venv"])
            self.assertEqual([c["name"] for c in plan_sort["commands"]], ["sortingen"])

            # 3. perf
            perf_dir = root / "perf"
            perf_dir.mkdir()
            (perf_dir / "perf.py").write_text("print('perf')\n", encoding="utf-8")
            plan_perf = meu.inspect_project(perf_dir, "perf")
            self.assertEqual(plan_perf["kind"], "python-cli")
            self.assertFalse(plan_perf["needs_venv"])
            self.assertEqual([c["name"] for c in plan_perf["commands"]], ["perf"])

            # 4. borfek
            borfek_dir = root / "borfek"
            borfek_dir.mkdir()
            (borfek_dir / "docker-compose.yml").write_text("services: {}\n", encoding="utf-8")
            (borfek_dir / "borfek-linux.sh").write_text("#!/usr/bin/env bash\n", encoding="utf-8")
            (borfek_dir / "borfek-windows.bat").write_text("@echo off\r\n", encoding="utf-8")
            plan_borfek = meu.inspect_project(borfek_dir, "borfek")
            self.assertEqual(plan_borfek["kind"], "web-service")
            self.assertTrue(plan_borfek["has_docker_compose"])
            self.assertEqual([c["name"] for c in plan_borfek["commands"]], ["borfek"])

            # 5. Unknown future Python project with requirements.txt
            hebele_dir = root / "hebele"
            hebele_dir.mkdir()
            (hebele_dir / "hebele.py").write_text("print('hebele')\n", encoding="utf-8")
            (hebele_dir / "requirements.txt").write_text("requests\n", encoding="utf-8")
            plan_hebele = meu.inspect_project(hebele_dir, "hebele")
            self.assertEqual(plan_hebele["kind"], "python-cli")
            self.assertTrue(plan_hebele["needs_venv"])
            self.assertEqual([c["name"] for c in plan_hebele["commands"]], ["hebele"])

            # 6. Unknown future static web project
            web_dir = root / "my-pwa"
            web_dir.mkdir()
            (web_dir / "index.html").write_text("<html></html>\n", encoding="utf-8")
            plan_web = meu.inspect_project(web_dir, "my-pwa")
            self.assertEqual(plan_web["kind"], "static-web")
            self.assertEqual(plan_web["commands"][0]["target_type"], "static_web")

    def test_apply_compat_patches_for_recep(self):
        with tempfile.TemporaryDirectory() as tmp:
            app_dir = Path(tmp) / "recep"
            app_dir.mkdir()
            (app_dir / "c4_skin.jpeg").write_bytes(b"JPEG")
            (app_dir / "cs_bomb_game.py").write_text(
                'import sys\nimport os\nimport math\nimport fcntl\n'
                'SKIN_PATH = os.path.expanduser("~/.local/share/cs-bomb/c4_skin.jpeg")\n'
                'def acquire_instance_lock():\n'
                '    global _lock_file\n'
                '    try:\n'
                '        _lock_file = open("/tmp/cs_bomb_game.lock", "w")\n'
                '        fcntl.flock(_lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)\n'
                '        return True\n'
                '    except (BlockingIOError, IOError):\n'
                '        return False\n',
                encoding="utf-8",
            )
            (app_dir / "monster_claw_widget.py").write_text(
                'import fcntl\nimport subprocess\nimport sys\n'
                'def acquire_widget_lock():\n'
                '    _widget_lock = open("/tmp/monster_claw_widget.lock", "w")\n'
                '    fcntl.flock(_widget_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)\n'
                'def on_click():\n'
                '    subprocess.Popen(["/home/toshi/.local/bin/cs-bomb"])\n',
                encoding="utf-8",
            )
            (app_dir / "sound_fx.py").write_text(
                'import os\nimport subprocess\n'
                'SOUNDS_DIR = os.path.expanduser("~/.local/share/cs-bomb/sounds")\n'
                'def ensure_sounds():\n    pass\n'
                'def play(name):\n'
                '    wav_path = os.path.join(SOUNDS_DIR, f"{name}.wav")\n'
                '    if os.path.exists(wav_path):\n'
                '        subprocess.Popen(["aplay", "-q", wav_path])\n',
                encoding="utf-8",
            )

            notes = meu.apply_compat_patches(app_dir, "recep")
            self.assertTrue(len(notes) >= 3)

            bomb_src = (app_dir / "cs_bomb_game.py").read_text(encoding="utf-8")
            self.assertIn("except ImportError:", bomb_src)
            self.assertIn("tempfile.gettempdir()", bomb_src)
            self.assertIn("os.path.dirname(os.path.abspath(__file__))", bomb_src)
            self.assertNotIn('open("/tmp/cs_bomb_game.lock"', bomb_src)

            claw_src = (app_dir / "monster_claw_widget.py").read_text(encoding="utf-8")
            self.assertIn("except ImportError:", claw_src)
            self.assertNotIn("/home/toshi/.local/bin/cs-bomb", claw_src)
            self.assertIn("sys.executable", claw_src)

            sound_src = (app_dir / "sound_fx.py").read_text(encoding="utf-8")
            self.assertIn("winsound", sound_src)

            # Idempotency check: running a second time keeps valid Python syntax
            meu.apply_compat_patches(app_dir, "recep")
            compile((app_dir / "cs_bomb_game.py").read_text(encoding="utf-8"), "cs_bomb_game.py", "exec")
            compile((app_dir / "monster_claw_widget.py").read_text(encoding="utf-8"), "monster_claw_widget.py", "exec")
            compile((app_dir / "sound_fx.py").read_text(encoding="utf-8"), "sound_fx.py", "exec")

    def test_create_command_shims_posix_and_windows(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            app_dir = root / "apps" / "sortingen"
            app_dir.mkdir(parents=True)
            (app_dir / "sortingen.py").write_text("print('hi')\n", encoding="utf-8")

            cmd_spec = {"name": "sortingen", "target_type": "python_script", "script": "sortingen.py", "gui": False}

            posix_bin = root / "posix_bin"
            posix_internal = root / "posix_internal"
            posix_shims = meu.create_command_shims(
                posix_bin,
                posix_internal,
                app_dir,
                cmd_spec,
                Path("/usr/bin/python3"),
                platform_name="posix",
            )
            self.assertTrue((posix_bin / "sortingen").is_file())
            self.assertTrue((posix_internal / "sortingen").is_file())
            self.assertEqual(len(posix_shims), 2)
            if os.name != "nt":
                self.assertTrue(os.access(posix_bin / "sortingen", os.X_OK))
            content = (posix_bin / "sortingen").read_text(encoding="utf-8")
            self.assertIn("sortingen.py", content)

            win_bin = root / "win_bin"
            win_shims = meu.create_command_shims(
                win_bin,
                win_bin,
                app_dir,
                cmd_spec,
                Path(r"C:\Python314\python.exe"),
                platform_name="nt",
            )
            self.assertTrue((win_bin / "sortingen.cmd").is_file())
            self.assertTrue((win_bin / "sortingen.ps1").is_file())
            self.assertTrue((win_bin / "sortingen").is_file())
            self.assertEqual(len(win_shims), 3)
            cmd_txt = (win_bin / "sortingen.cmd").read_text(encoding="utf-8")
            self.assertIn("@echo off", cmd_txt)
            self.assertIn("sortingen.py", cmd_txt)
            ps1_txt = (win_bin / "sortingen.ps1").read_text(encoding="utf-8")
            self.assertIn("@args", ps1_txt)


class TestCLILifecycle(unittest.TestCase):
    def _run_cli(self, argv: list[str], env: dict[str, str]) -> tuple[int, str, str]:
        out = io.StringIO()
        err = io.StringIO()
        with mock.patch.dict(os.environ, env, clear=False):
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                code = meu.main(argv)
        return code, out.getvalue(), err.getvalue()

    def test_search_and_info_commands(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = {"MEU_HOME": tmp}
            code, out, _ = self._run_cli(["search", "--offline"], env)
            self.assertEqual(code, 0)
            self.assertIn("recep", out)
            self.assertIn("sortingen", out)
            self.assertIn("perf", out)

            code2, out2, _ = self._run_cli(["info", "recep"], env)
            self.assertEqual(code2, 0)
            self.assertIn("https://github.com/meucak/recep", out2)
            self.assertIn("cs-bomb", out2)

    def test_full_install_list_run_update_uninstall_and_self_install(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            meu_home = tmp_path / "meu_home"
            env = {"MEU_HOME": str(meu_home)}

            # Pre-existing unrelated binary in bin_dir must survive uninstall
            bin_dir = meu_home / "bin"
            bin_dir.mkdir(parents=True)
            unrelated = bin_dir / "keep-me"
            unrelated.write_text("#!/bin/sh\necho keep\n", encoding="utf-8")

            def fake_download(spec, dest_dir, **kwargs):
                dest = Path(dest_dir)
                dest.mkdir(parents=True, exist_ok=True)
                (dest / "sortingen.py").write_text(
                    "import sys\n"
                    "if '--help' in sys.argv:\n"
                    "    print('sortingen help ok')\n"
                    "    sys.exit(0)\n"
                    "print('args:', sys.argv[1:])\n",
                    encoding="utf-8",
                )
                return {"method": "git", "version": "abc1234"}

            with mock.patch.object(meu, "download_repo", side_effect=fake_download):
                code, out, err = self._run_cli(["install", "sortingen"], env)
                self.assertEqual(code, 0, msg=f"stderr={err}\nstdout={out}")
                self.assertIn("sortingen", out)

            shim_path = bin_dir / ("sortingen.cmd" if os.name == "nt" else "sortingen")
            self.assertTrue(shim_path.is_file())

            # Execute generated shim directly
            proc = subprocess.run([str(shim_path), "--help"], capture_output=True, text=True, check=False)
            self.assertEqual(proc.returncode, 0)
            self.assertIn("sortingen help ok", proc.stdout)

            # List installed apps
            code_ls, out_ls, _ = self._run_cli(["list"], env)
            self.assertEqual(code_ls, 0)
            self.assertIn("sortingen", out_ls)
            self.assertIn("abc1234", out_ls)

            # Doctor check
            code_doc, out_doc, _ = self._run_cli(["doctor"], env)
            self.assertEqual(code_doc, 0)
            self.assertIn("Python", out_doc)

            # Update
            with mock.patch.object(meu, "download_repo", side_effect=fake_download):
                code_up, out_up, _ = self._run_cli(["update", "sortingen"], env)
                self.assertEqual(code_up, 0)
                self.assertIn("sortingen", out_up)

            # Uninstall must remove sortingen shim and app dir, but keep unrelated binary
            code_rm, out_rm, _ = self._run_cli(["uninstall", "sortingen"], env)
            self.assertEqual(code_rm, 0)
            self.assertFalse(shim_path.exists())
            self.assertFalse((meu_home / "apps" / "sortingen").exists())
            self.assertTrue(unrelated.is_file())

            code_ls2, out_ls2, _ = self._run_cli(["list"], env)
            self.assertEqual(code_ls2, 0)
            self.assertNotIn("abc1234", out_ls2)

            # Self-install inside isolated MEU_HOME
            code_si, out_si, _ = self._run_cli(["self-install"], env)
            self.assertEqual(code_si, 0)
            self.assertTrue((meu_home / "core" / "meu.py").is_file())
            meu_shim = bin_dir / ("meu.cmd" if os.name == "nt" else "meu")
            self.assertTrue(meu_shim.is_file())

    def test_setup_python_env_handles_missing_ensurepip_when_modules_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            app_dir = Path(tmp) / "recep"
            app_dir.mkdir()
            req = app_dir / "requirements.txt"
            req.write_text("json\n", encoding="utf-8")
            plan = {"needs_venv": True, "requirements_file": req}

            with mock.patch("importlib.util.find_spec", return_value=None):
                py_exe, has_venv = meu._setup_python_env(app_dir, plan, no_deps=False)
                self.assertTrue(py_exe.exists())
                if os.name != "nt":
                    self.assertTrue(has_venv)


if __name__ == "__main__":
    unittest.main()
