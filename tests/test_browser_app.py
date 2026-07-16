from __future__ import annotations

import os
import re
import signal
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.request
from pathlib import Path
from unittest.mock import MagicMock, patch

from hustlenest import browser_app


class BrowserAppLauncherTests(unittest.TestCase):
    def test_bundled_runtime_is_preferred_when_frozen(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = Path(directory) / "runtime"
            runtime.mkdir()
            executable = runtime / ("node.exe" if os.name == "nt" else "node")
            executable.write_bytes(b"")
            with (
                patch.object(sys, "frozen", True, create=True),
                patch.object(sys, "_MEIPASS", directory, create=True),
            ):
                self.assertEqual(browser_app._node_executable(), str(executable))

    def test_wait_for_frontend_rejects_early_process_exit(self) -> None:
        process = MagicMock()
        process.poll.return_value = 2
        process.returncode = 2
        with self.assertRaisesRegex(RuntimeError, "exit code 2"):
            browser_app._wait_for_frontend(process, "127.0.0.1", 3000, timeout=0.1)

    def test_run_starts_built_frontend_then_backend_and_cleans_up(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            web = Path(directory)
            (web / "package.json").write_text("{}", encoding="utf-8")
            (web / "dist" / "server").mkdir(parents=True)
            (web / "dist" / "server" / "index.js").write_text("", encoding="utf-8")
            (web / "node_modules" / "vinext" / "dist" / "server").mkdir(parents=True)
            (web / "node_modules" / "vinext" / "dist" / "server" / "prod-server.js").write_text("", encoding="utf-8")
            (web / "start-local.mjs").write_text("", encoding="utf-8")
            process = MagicMock(spec=subprocess.Popen)
            process.poll.return_value = None
            with (
                patch("hustlenest.browser_app._node_executable", return_value="node.exe"),
                patch("hustlenest.browser_app.subprocess.Popen", return_value=process) as popen,
                patch("hustlenest.browser_app._wait_for_frontend") as wait,
                patch("hustlenest.browser_app._stop_frontend") as stop,
                patch("hustlenest.browser_app.web_bridge.run") as backend,
            ):
                browser_app.run(web_directory=web, frontend_port=3010, backend_port=8877)
            popen.assert_called_once()
            self.assertEqual(
                popen.call_args.args[0],
                ["node.exe", str(web.resolve() / "start-local.mjs"), "-H", "127.0.0.1", "-p", "3010"],
            )
            wait.assert_called_once_with(process, "127.0.0.1", 3010)
            backend.assert_called_once_with("127.0.0.1", 8877, "http://localhost:3010")
            stop.assert_called_once_with(process, 3010)

    def test_run_requires_a_production_browser_build(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            web = Path(directory)
            (web / "package.json").write_text("{}", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "production build is missing"):
                browser_app.run(web_directory=web)

    @unittest.skipUnless(os.environ.get("HUSTLENEST_RUN_LAUNCHER_INTEGRATION") == "1", "explicit launcher integration check")
    def test_unified_launcher_serves_frontend_and_backend(self) -> None:
        root = Path(__file__).resolve().parent.parent
        creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
        process = subprocess.Popen(
            [sys.executable, "-m", "hustlenest.browser_app", "--frontend-port", "3011", "--backend-port", "8766", "--no-browser"],
            cwd=root,
            creationflags=creation_flags,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                try:
                    with urllib.request.urlopen("http://127.0.0.1:3011/", timeout=1) as frontend:
                        page = frontend.read().decode("utf-8")
                    stylesheet_path = re.search(r'href="([^"]+\.css)"', page)
                    if not stylesheet_path:
                        self.fail("Frontend HTML did not reference its compiled stylesheet.")
                    with urllib.request.urlopen(
                        f"http://127.0.0.1:3011{stylesheet_path.group(1)}", timeout=1
                    ) as stylesheet:
                        stylesheet_type = stylesheet.headers.get_content_type()
                        stylesheet_body = stylesheet.read().decode("utf-8")
                    with urllib.request.urlopen("http://127.0.0.1:8766/health", timeout=1) as backend:
                        health = backend.read().decode("utf-8")
                    break
                except OSError:
                    time.sleep(0.25)
            else:
                self.fail("Unified launcher did not become ready.")
            self.assertIn("HustleNest", page)
            self.assertEqual(stylesheet_type, "text/css")
            self.assertIn(".app-shell", stylesheet_body)
            self.assertIn('"status":"ready"', health)
        finally:
            if process.poll() is None:
                if os.name == "nt":
                    process.send_signal(signal.CTRL_BREAK_EVENT)
                else:
                    process.send_signal(signal.SIGINT)
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.terminate()
                    process.wait(timeout=5)


if __name__ == "__main__":
    unittest.main()
