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
        token = os.environ.get("GITHUB_PAT")
        if not token:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({"error": "GITHUB_PAT environment variable not configured on Vercel."}).encode('utf-8'))
            return

        owner = "vedangpoddar2-lang"
        repo = "Pricing-Tracker"
        runs_url = f"https://api.github.com/repos/{owner}/{repo}/actions/runs?per_page=1"
        
        req = urllib.request.Request(
            runs_url,
            headers={
                "Authorization": f"token {token}",
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "Vercel-Serverless-Function"
            },
            method="GET"
        )
        
        try:
            with urllib.request.urlopen(req) as response:
                runs_data = json.loads(response.read().decode('utf-8'))
                runs = runs_data.get("workflow_runs", [])
                if not runs:
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(json.dumps({"status": "idle"}).encode('utf-8'))
                    return
                
                run = runs[0]
                run_status = run.get("status")
                
                if run_status in ["queued", "in_progress"]:
                    run_id = run.get("id")
                    jobs_url = f"https://api.github.com/repos/{owner}/{repo}/actions/runs/{run_id}/jobs"
                    jobs_req = urllib.request.Request(
                        jobs_url,
                        headers={
                            "Authorization": f"token {token}",
                            "Accept": "application/vnd.github.v3+json",
                            "User-Agent": "Vercel-Serverless-Function"
                        },
                        method="GET"
                    )
                    
                    with urllib.request.urlopen(jobs_req) as jobs_resp:
                        jobs_data = json.loads(jobs_resp.read().decode('utf-8'))
                        self.send_response(200)
                        self.send_header('Content-Type', 'application/json')
                        self.send_header('Access-Control-Allow-Origin', '*')
                        self.end_headers()
                        self.wfile.write(json.dumps({
                            "status": "active",
                            "run_id": run_id,
                            "run_status": run_status,
                            "created_at": run.get("created_at"),
                            "updated_at": run.get("updated_at"),
                            "jobs": jobs_data.get("jobs", [])
                        }).encode('utf-8'))
                else:
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(json.dumps({
                        "status": "idle",
                        "last_run": {
                            "status": run_status,
                            "conclusion": run.get("conclusion"),
                            "updated_at": run.get("updated_at")
                        }
                    }).encode('utf-8'))
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))


