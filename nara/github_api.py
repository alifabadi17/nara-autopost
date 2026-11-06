"""Akses minimal ke GitHub REST API memakai GITHUB_TOKEN bawaan Actions."""
import json
import os
import urllib.error
import urllib.request

API = "https://api.github.com"
LABEL = "antrean-nara"


class GitHubError(Exception):
    pass


class GitHub:
    def __init__(self, token=None, repo=None):
        self.token = token or os.environ.get("GITHUB_TOKEN")
        self.repo = repo or os.environ.get("GITHUB_REPOSITORY")
        if not self.token or not self.repo:
            raise GitHubError("GITHUB_TOKEN / GITHUB_REPOSITORY tidak tersedia")

    def _req(self, method, path, body=None):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(f"{API}{path}", data=data, method=method)
        req.add_header("Authorization", f"Bearer {self.token}")
        req.add_header("Accept", "application/vnd.github+json")
        req.add_header("X-GitHub-Api-Version", "2022-11-28")
        if data:
            req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                raw = resp.read()
                return json.loads(raw) if raw else None
        except urllib.error.HTTPError as e:
            raise GitHubError(f"HTTP {e.code} {method} {path}: {e.read()[:300]!r}") from None

    def ensure_label(self):
        try:
            self._req("GET", f"/repos/{self.repo}/labels/{LABEL}")
        except GitHubError:
            self._req("POST", f"/repos/{self.repo}/labels",
                      {"name": LABEL, "color": "e99695", "description": "Antrean postingan Nara"})

    def find_queue_issue(self):
        issues = self._req("GET", f"/repos/{self.repo}/issues?labels={LABEL}&state=open&per_page=10")
        issues = [i for i in issues if "pull_request" not in i]
        return issues[0] if issues else None

    def create_issue(self, title, body):
        return self._req("POST", f"/repos/{self.repo}/issues",
                         {"title": title, "body": body, "labels": [LABEL]})

    def update_issue(self, number, body, title=None):
        data = {"body": body}
        if title:
            data["title"] = title
        return self._req("PATCH", f"/repos/{self.repo}/issues/{number}", data)

    def comment(self, number, body):
        return self._req("POST", f"/repos/{self.repo}/issues/{number}/comments", {"body": body})
