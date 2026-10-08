import json, http.server
class H(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        b = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        c = b['messages'][0]['content']
        img = c[1]['image_url']['url']
        print(f"MOCK got path={self.path} model={b['model']} img_b64_len={len(img)} prompt_has_name={'Angel' in c[0]['text']}", flush=True)
        out = {"choices":[{"message":{"content":'Sure! {"decision": "DISLIKE", "reason": "Bio advertises a domme service."}'}}]}
        self.send_response(200); self.send_header('Content-Type','application/json'); self.end_headers()
        self.wfile.write(json.dumps(out).encode())
    def log_message(self, *a): pass
http.server.HTTPServer(('127.0.0.1', 18080), H).serve_forever()
