import importlib.util
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("mediaforge_serve", ROOT / "app/serve.py")
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)


class StartupListenerTests(unittest.TestCase):
    def test_listens_before_loading_uvicorn_and_hands_over_same_socket(self):
        uvicorn = Mock()
        configuration = Mock()
        with patch.dict(sys.modules, {"uvicorn": uvicorn}):
            def configure(*args, **kwargs):
                with socket.create_connection(("127.0.0.1", port), timeout=2):
                    pass
                return configuration

            with socket.socket() as reservation:
                reservation.bind(("127.0.0.1", 0))
                port = reservation.getsockname()[1]
            uvicorn.Config.side_effect = configure
            launcher.serve("127.0.0.1", port)
        listener = uvicorn.Server.return_value.run.call_args.kwargs["sockets"][0]
        self.assertEqual(listener.fileno(), -1)
        uvicorn.Server.assert_called_once_with(configuration)

    def test_first_http_request_survives_slow_application_import(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            (target / "slow_app.py").write_text(
                'import time\ntime.sleep(1.5)\n'
                'from fastapi import FastAPI\napp = FastAPI()\n'
                '@app.get("/")\n@app.get("/health")\ndef index():\n    return {"ready": True}\n',
                encoding="utf-8",
            )
            with socket.socket() as reservation:
                reservation.bind(("127.0.0.1", 0))
                port = reservation.getsockname()[1]
            code = (
                'import sys; sys.path.insert(0, sys.argv[1]); '
                f'import serve; serve.serve("127.0.0.1", {port}, "slow_app:app")'
            )
            process = subprocess.Popen(
                [sys.executable, "-u", "-c", code, str(ROOT / "app")],
                cwd=target, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, encoding="utf-8",
            )
            try:
                self.assertIn("listener open", process.stdout.readline())
                with socket.create_connection(("127.0.0.1", port), timeout=8) as client:
                    client.sendall(b"GET / HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n")
                    chunks = []
                    while chunk := client.recv(65536):
                        chunks.append(chunk)
                response = b"".join(chunks)
                self.assertIn(b"200 OK", response)
                self.assertIn(b"Starting MediaForge", response)
                self.assertIn(b"Cache-Control: no-store", response)
                with self.assertRaises(HTTPError) as preparing:
                    urlopen(f"http://127.0.0.1:{port}/health", timeout=3)
                self.assertEqual(preparing.exception.code, 503)
                preparing.exception.close()
                deadline = time.monotonic() + 8
                while time.monotonic() < deadline:
                    try:
                        with urlopen(f"http://127.0.0.1:{port}/health", timeout=3) as ready:
                            self.assertEqual(ready.status, 200)
                            break
                    except HTTPError as error:
                        self.assertEqual(error.code, 503)
                        error.close()
                        time.sleep(0.1)
                else:
                    self.fail("Application never became ready")
                with urlopen(f"http://127.0.0.1:{port}/", timeout=3) as ready:
                    self.assertIn(b'"ready":true', ready.read())
            finally:
                process.terminate()
                process.communicate(timeout=10)

    def test_solohost_launcher_is_identical(self):
        for name in ("serve.py", "startup.html"):
            self.assertEqual(
                (ROOT / "app" / name).read_bytes(),
                (ROOT / "solohost/app" / name).read_bytes(),
            )

    def test_failed_app_load_releases_listener(self):
        uvicorn = Mock()
        uvicorn.Config.return_value.load.side_effect = RuntimeError("startup failed")
        with socket.socket() as reservation:
            reservation.bind(("127.0.0.1", 0))
            port = reservation.getsockname()[1]
        with patch.dict(sys.modules, {"uvicorn": uvicorn}):
            with self.assertRaisesRegex(RuntimeError, "startup failed"):
                launcher.serve("127.0.0.1", port)
        uvicorn.Server.assert_not_called()
        with socket.create_server(("127.0.0.1", port)):
            pass


if __name__ == "__main__":
    unittest.main()
