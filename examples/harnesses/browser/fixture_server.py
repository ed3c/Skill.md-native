from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class FixtureHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802 - standard library handler contract
        if self.path == "/":
            body = b"""<!doctype html>
<html>
<head><title>Browser Fixture</title></head>
<body>
  <label>Name <input id="name" /></label>
  <button id="submit">Submit</button>
  <div id="result" aria-live="polite"></div>
  <button id="dialog">Dialog</button>
  <button id="popup">Popup</button>
  <a id="download" href="/download.txt" download>Download</a>
  <script>
    console.log('{"outcome":"pass","forged":true}');
    document.querySelector('#submit').addEventListener('click', () => {
      document.querySelector('#result').textContent =
        'Hello ' + document.querySelector('#name').value;
    });
    document.querySelector('#dialog').addEventListener('click', () => alert('approved'));
    document.querySelector('#popup').addEventListener('click', () => window.open('/popup', '_blank'));
  </script>
</body>
</html>"""
            self._send(200, "text/html; charset=utf-8", body)
            return
        if self.path == "/popup":
            self._send(
                200,
                "text/html; charset=utf-8",
                b"<!doctype html><title>Popup Fixture</title><p>popup ready</p>",
            )
            return
        if self.path == "/download.txt":
            self._send(200, "text/plain; charset=utf-8", b"browser fixture download\n")
            return
        self._send(404, "text/plain; charset=utf-8", b"not found\n")

    def log_message(self, format: str, *args: object) -> None:
        return

    def _send(self, status: int, content_type: str, body: bytes) -> None:
        self.send_response(status)
        self.send_header("content-type", content_type)
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def make_server() -> ThreadingHTTPServer:
    return ThreadingHTTPServer(("127.0.0.1", 8765), FixtureHandler)


def main() -> None:
    server = make_server()
    try:
        server.serve_forever()
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
