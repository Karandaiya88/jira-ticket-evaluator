"""
Retrieval Agent — fetches GitHub PR data via REST API and GitHub MCP server.
Returns diff, file list, commit messages, PR description, and inline comments.
"""
import os
import re
import requests
from anthropic import Anthropic

client = Anthropic()

GITHUB_API = "https://api.github.com"

RETRIEVAL_SYSTEM = """You are a code analysis agent. You have access to GitHub via MCP tools.
Fetch the PR diff, changed files, commit messages, and PR description.
Return ONLY a JSON object:
{
  "pr_number": 0,
  "title": "",
  "description": "",
  "base_branch": "",
  "head_branch": "",
  "commits": [{"sha": "", "message": ""}],
  "files_changed": [{"filename": "", "status": "", "additions": 0, "deletions": 0, "patch": ""}],
  "diff_summary": "",
  "comments": [{"user": "", "body": ""}],
  "labels": [],
  "linked_issues": []
}
"""


class RetrievalAgent:
    def __init__(self):
        self.token = os.getenv("GITHUB_TOKEN", "")
        self.headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28"
        }
        if self.token:
            self.headers["Authorization"] = f"Bearer {self.token}"

    def _parse_pr_url(self, pr_url: str) -> tuple[str, str, int] | None:
        """Extract owner, repo, and PR number from a GitHub PR URL."""
        match = re.search(r"github\.com/([^/]+)/([^/]+)/pull/(\d+)", pr_url)
        if match:
            return match.group(1), match.group(2), int(match.group(3))
        return None

    def _get(self, path: str) -> dict | list | None:
        resp = requests.get(f"{GITHUB_API}{path}", headers=self.headers, timeout=20)
        if resp.status_code == 200:
            return resp.json()
        return None

    def fetch(self, pr_url: str) -> dict:
        """Fetch all relevant PR data."""
        parsed = self._parse_pr_url(pr_url)
        if not parsed:
            return {"error": f"Could not parse PR URL: {pr_url}"}

        owner, repo, pr_number = parsed
        base = f"/repos/{owner}/{repo}/pulls/{pr_number}"

        pr_data = self._get(base)
        if not pr_data:
            return {"error": f"Could not fetch PR {pr_url}. Check GITHUB_TOKEN and URL."}

        files_data = self._get(f"{base}/files") or []
        commits_data = self._get(f"{base}/commits") or []
        comments_data = self._get(f"{base}/comments") or []
        reviews_data = self._get(f"{base}/reviews") or []

        # Build file list (truncate large patches to keep context manageable)
        files = []
        for f in files_data:
            patch = f.get("patch", "")
            if len(patch) > 3000:
                patch = patch[:3000] + "\n... (truncated)"
            files.append({
                "filename": f["filename"],
                "status": f["status"],
                "additions": f.get("additions", 0),
                "deletions": f.get("deletions", 0),
                "patch": patch
            })

        commits = [
            {"sha": c["sha"][:8], "message": c["commit"]["message"].split("\n")[0]}
            for c in commits_data
        ]

        comments = [
            {"user": c["user"]["login"], "body": c["body"]}
            for c in comments_data
        ]

        # Diff summary
        total_add = sum(f.get("additions", 0) for f in files_data)
        total_del = sum(f.get("deletions", 0) for f in files_data)
        diff_summary = (
            f"{len(files)} files changed, {total_add} additions, {total_del} deletions. "
            f"Files: {', '.join(f['filename'] for f in files[:10])}"
        )

        # Extract linked issue refs from body
        body = pr_data.get("body") or ""
        linked_issues = re.findall(r"(?:closes?|fixes?|resolves?)\s+#(\d+)", body, re.IGNORECASE)

        return {
            "pr_number": pr_number,
            "title": pr_data.get("title", ""),
            "description": body,
            "base_branch": pr_data.get("base", {}).get("ref", ""),
            "head_branch": pr_data.get("head", {}).get("ref", ""),
            "commits": commits,
            "files_changed": files,
            "diff_summary": diff_summary,
            "comments": comments,
            "labels": [l["name"] for l in pr_data.get("labels", [])],
            "linked_issues": linked_issues
        }
