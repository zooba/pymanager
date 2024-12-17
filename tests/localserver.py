import os
import sys
import time

from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/stop":
            self.send_response(200)
            self.end_headers()
            self.server.shutdown()
            return
        if self.path == "/alive":
            self.send_response(200)
            self.end_headers()
            return
        if self.path == "/1kb":
            self.send_response(200)
            self.send_header("Content-Length", 1024)
            self.end_headers()
            self.wfile.write(os.urandom(1024))
            return
        if self.path == "/128kb":
            self.send_response(200)
            self.send_header("Content-Length", 128*1024)
            self.end_headers()
            for _ in range(128):
                self.wfile.write(os.urandom(1024))
                time.sleep(0.05)
            return
        if self.path == "/withauth":
            if "Authorization" not in self.headers:
                self.send_response(401)
                self.end_headers()
                return
            self.send_response(200)
            self.end_headers()
            from base64 import b64decode
            kind, _, auth = self.headers["Authorization"].partition(" ")
            self.wfile.write(kind.encode() + b" " + b64decode(auth.encode("ascii")))
            return
        self.send_error(404)

    def do_HEAD(self):
        if self.path == "/128kb":
            self.send_response(200)
            self.send_header("Content-Length", 128*1024)
            self.end_headers()
            return
        self.send_error(404)

SERVER_ADDR = "localhost", int(sys.argv[1])
HTTPD = ThreadingHTTPServer(SERVER_ADDR, Handler)
HTTPD.serve_forever()
