"""
Parser Agent — extracts structured requirements from a Jira ticket.
Supports: raw JSON, Jira REST API URL, and plain text descriptions.
"""
import json
import os
import re
import requests
from anthropic import Anthropic

client = Anthropic()

PARSE_SYSTEM = """You are a requirements analyst. Given a Jira ticket (raw JSON, API response, or description),
extract and structure all requirements. Return ONLY valid JSON:

{
  "ticket_id": "<id or null>",
  "title": "<summary>",
  "type": "feature" | "bug" | "refactor" | "other",
  "priority": "<priority or null>",
  "description": "<cleaned description>",
  "acceptance_criteria": [
    {"id": "AC-1", "text": "<criterion>", "testable": true}
  ],
  "labels": [],
  "components": []
}

For bugs: treat steps-to-reproduce + expected behaviour as acceptance criteria.
For refactors: treat code-quality goals (no new linting errors, test coverage ≥ N%) as criteria.
"""


class ParserAgent:
    def __init__(self):
        self.jira_base = os.getenv("JIRA_BASE_URL", "")
        self.jira_token = os.getenv("JIRA_API_TOKEN", "")
        self.jira_email = os.getenv("JIRA_EMAIL", "")

    def _fetch_from_jira_api(self, ticket_url: str) -> dict | None:
        """Try to fetch ticket via Jira REST API if credentials are available."""
        if not (self.jira_base and self.jira_token and self.jira_email):
            return None
        # Extract issue key from URL like https://org.atlassian.net/browse/PROJ-123
        match = re.search(r"/browse/([A-Z]+-\d+)", ticket_url)
        if not match:
            return None
        issue_key = match.group(1)
        url = f"{self.jira_base}/rest/api/3/issue/{issue_key}"
        resp = requests.get(
            url,
            headers={"Accept": "application/json"},
            auth=(self.jira_email, self.jira_token),
            timeout=15
        )
        if resp.status_code == 200:
            return resp.json()
        return None

    def parse(self, ticket_input: str) -> dict:
        """Parse a Jira ticket from URL, raw JSON string, or plain text."""
        raw_ticket = ticket_input

        # Try Jira API fetch
        if ticket_input.startswith("http") and "atlassian" in ticket_input:
            api_data = self._fetch_from_jira_api(ticket_input)
            if api_data:
                raw_ticket = json.dumps(api_data, indent=2)

        # Try parsing as JSON directly
        try:
            parsed = json.loads(ticket_input)
            raw_ticket = json.dumps(parsed, indent=2)
        except (json.JSONDecodeError, TypeError):
            pass  # treat as plain text / URL

        # Use Claude to extract structured requirements
        response = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=2048,
            system=PARSE_SYSTEM,
            messages=[{"role": "user", "content": f"Parse this Jira ticket:\n\n{raw_ticket}"}]
        )

        text = response.content[0].text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {"error": "Failed to parse ticket", "raw": text}
