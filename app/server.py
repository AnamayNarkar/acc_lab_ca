"""EC2 backend: preforking stdlib HTTP server (one worker per vCPU), no dependencies."""
import json, os, socket, sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs
from work import do_work

BACKEND = os.environ.get("BACKEND_NAME", "ec2")

class H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    def log_message(self, *a): pass
    def _send(self, code, obj):
        b = json.dumps(obj).encode()
        self.send_response(code); self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
    def do_GET(self):
        u = urlparse(self.path); q = parse_qs(u.query)
        if u.path == "/health": return self._send(200, {"ok": True})
        if u.path == "/work":
            ms = float(q.get("ms", ["400"])[0]); cpu = float(q.get("cpu", ["80"])[0])
            took = do_work(ms, cpu)
            return self._send(200, {"backend": BACKEND, "took_ms": round(took, 1), "pid": os.getpid()})
        self._send(404, {"error": "not found"})

def main(port=80, workers=None):
    workers = workers or os.cpu_count() or 1
    s = socket.socket(); s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("0.0.0.0", port)); s.listen(512)
    for _ in range(workers - 1):
        if os.fork() == 0: break
    srv = ThreadingHTTPServer(("0.0.0.0", port), H, bind_and_activate=False)
    srv.daemon_threads = True; srv.socket = s
    srv.serve_forever()

if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 80)
