import json, http.server, sys
# Optional argv[1]: number of initial requests to fail with HTTP 503 (to exercise retries).
fail_first = int(sys.argv[1]) if len(sys.argv) > 1 else 0
class H(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        global fail_first
        b = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        if fail_first > 0:
            fail_first -= 1
            self.send_response(503); self.end_headers()
            return
        c = b['messages'][0]['content']
        img = c[1]['image_url']['url']
        print(f"MOCK got path={self.path} model={b['model']} img_b64_len={len(img)} prompt_has_name={'Angel' in c[0]['text']}", flush=True)
        out = {"choices":[{"message":{"content":'Sure! {"decision": "DISLIKE", "reason": "Bio advertises a domme service."}'}}]}
        self.send_response(200); self.send_header('Content-Type','application/json'); self.end_headers()
        self.wfile.write(json.dumps(out).encode())
    def log_message(self, *a): pass
http.server.HTTPServer(('127.0.0.1', 18080), H).serve_forever()
