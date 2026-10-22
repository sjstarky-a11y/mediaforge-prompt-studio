"""Show a startup page before importing the web stack, using one HTTP socket."""

import socket


def serve(host="0.0.0.0", port=8080, app="main:app"):
    # SoloHost can open its webview as soon as Docker reports "running".
    # Uvicorn normally binds only after importing FastAPI and the application.
    # Keep the listening socket open throughout that work; TCP queues the first
    # request instead of refusing it and leaving an empty embedded browser.
    with socket.create_server((host, port), backlog=2048) as listener:
        print("MediaForge HTTP listener open; preparing application.", flush=True)
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        from pathlib import Path
        from threading import Thread

        page = Path(__file__).with_name("startup.html").read_bytes()

        class StartupHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                is_page = self.path.split("?", 1)[0] == "/"
                content = page if is_page else b'{"status":"starting"}'
                self.send_response(200 if is_page else 503)
                self.send_header("Content-Type", "text/html; charset=utf-8" if is_page else "application/json")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(content)))
                self.send_header("Retry-After", "1")
                self.end_headers()
                if self.command != "HEAD":
                    self.wfile.write(content)

            do_HEAD = do_GET

            def do_POST(self):
                self.send_error(503, "Application is starting; try again shortly.")

            def log_message(self, *args):
                pass

            def setup(self):
                self.request.settimeout(5)
                super().setup()

        startup = ThreadingHTTPServer(listener.getsockname(), StartupHandler, bind_and_activate=False)
        startup.socket.close()
        startup.socket = listener
        thread = Thread(target=startup.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
        thread.start()
        try:
            try:
                import uvicorn

                config = uvicorn.Config(app, host=host, port=port)
                config.load()
                server = uvicorn.Server(config)
            finally:
                startup.shutdown()
                thread.join()
            # Keep the same listening socket open during the handover. Requests
            # arriving here wait for ASGI startup rather than losing connection.
            server.run(sockets=[listener])
        finally:
            startup.server_close()


if __name__ == "__main__":
    serve()
