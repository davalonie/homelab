"""Static synthetic audio only. No directory listings or arbitrary paths."""
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
import os
import re

DATA = Path(os.environ.get("FIXTURES_DIR", "/fixtures"))

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):
        pass
    def do_GET(self):
        if self.path not in ('/one.wav','/two.wav'):
            self.send_error(404)
            return
        data=(DATA / self.path[1:]).read_bytes()
        start,end=0,len(data)-1
        match=re.fullmatch(r'bytes=(\d+)-(\d*)',self.headers.get('Range',''))
        if match:
            start=int(match[1]);end=min(end,int(match[2])) if match[2] else end
            if start>=len(data) or end<start:
                self.send_response(416);self.send_header('Content-Range',f'bytes */{len(data)}');self.end_headers();return
        self.send_response(206 if match else 200)
        self.send_header('Content-Type','audio/wav')
        self.send_header('Accept-Ranges','bytes')
        self.send_header('Content-Length',str(end-start+1))
        if match:self.send_header('Content-Range',f'bytes {start}-{end}/{len(data)}')
        self.end_headers()
        try:self.wfile.write(data[start:end+1])
        except BrokenPipeError:pass
if __name__ == "__main__":
    HTTPServer(("0.0.0.0", 8100), Handler).serve_forever()
