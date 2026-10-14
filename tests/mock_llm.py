import json, http.server, sys
# argv[1]: number of initial requests to fail with HTTP 503 (to exercise retries).
# argv[2]: "limit" to answer the daily-limit question with true (default false).
fail_first = int(sys.argv[1]) if len(sys.argv) > 1 else 0
limit = len(sys.argv) > 2 and sys.argv[2] == "limit"
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
        if '"daily_limit"' in c[0]['text']:
            reply = json.dumps({"daily_limit": limit})
        else:
            reply = 'Sure! {"decision": "DISLIKE", "reason": "Bio advertises a domme service."}'
        out = {"choices":[{"message":{"content":reply}}]}
        self.send_response(200); self.send_header('Content-Type','application/json'); self.end_headers()
        self.wfile.write(json.dumps(out).encode())
    def log_message(self, *a): pass
http.server.HTTPServer(('127.0.0.1', 18080), H).serve_forever()
