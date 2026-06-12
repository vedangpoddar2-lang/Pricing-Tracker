from http.server import BaseHTTPRequestHandler
import json
import urllib.request
import os

class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.end_headers()

    def do_POST(self):
        token = os.environ.get("GITHUB_PAT")
        if not token:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({"error": "GITHUB_PAT environment variable not configured on Vercel."}).encode('utf-8'))
            return

        # Trigger GitHub Actions workflow dispatch
        owner = "vedangpoddar2-lang"
        repo = "Pricing-Tracker"
        workflow = "scrape.yml"
        url = f"https://api.github.com/repos/{owner}/{repo}/actions/workflows/{workflow}/dispatches"
        
        req_data = json.dumps({"ref": "main"}).encode('utf-8')
        req = urllib.request.Request(
            url,
            data=req_data,
            headers={
                "Authorization": f"token {token}",
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "Vercel-Serverless-Function",
                "Content-Type": "application/json"
            },
            method="POST"
        )
        
        try:
            with urllib.request.urlopen(req) as response:
                status = response.status
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({"status": "success", "github_status": status}).encode('utf-8'))
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))
            
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps({
            "status": "online",
            "message": "GPU Price Tracker API is running. To trigger a scrape, make a POST request to this endpoint."
        }).encode('utf-8'))


