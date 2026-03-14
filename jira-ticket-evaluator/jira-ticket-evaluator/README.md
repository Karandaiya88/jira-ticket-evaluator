# Jira Ticket Evaluator

An AI-powered system that autonomously evaluates whether a GitHub Pull Request satisfies the requirements in its linked Jira ticket. Built with multi-agent architecture, MCP tool integration, and Claude AI.

## Architecture

```
Input: Jira Ticket + GitHub PR URL
       │
       ▼
┌─────────────────────────────┐
│     Orchestrator Agent      │  ← Plans evaluation, routes to sub-agents
│  (multi-step reasoning loop)│
└──────┬──────────┬──────────┬┘
       │          │          │
       ▼          ▼          ▼
  Parser      Retrieval   Test-Gen
  Agent       Agent       Agent
  (Jira →     (GitHub     (Writes &
  criteria)   diff/meta)  runs tests)
       │          │          │
       ▼          ▼          ▼
  Jira MCP   GitHub MCP  Filesystem
   Server     Server      MCP Server
       │          │          │
       └──────────┴──────────┘
                  │
                  ▼
        Structured Verdict JSON
        (Pass / Partial / Fail)
        + per-requirement breakdown
        + evidence + test results
```

## Quickstart

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env and add your API keys
```

Required:
- `ANTHROPIC_API_KEY` — from https://console.anthropic.com

Optional but recommended:
- `GITHUB_TOKEN` — for private repos and higher rate limits
- `JIRA_BASE_URL`, `JIRA_EMAIL`, `JIRA_API_TOKEN` — for live Jira fetch

### 3. Run via CLI

```bash
# With a Jira URL
python -m src.main \
  --jira "https://yourorg.atlassian.net/browse/PROJ-101" \
  --pr "https://github.com/owner/repo/pull/42"

# With raw Jira JSON (paste from examples/sample_tickets.json)
python -m src.main \
  --jira '{"key":"PROJ-101","fields":{"summary":"...","description":"..."}}' \
  --pr "https://github.com/owner/repo/pull/42" \
  --output verdict.json

# JSON output only
python -m src.main --jira ... --pr ... --json
```

### 4. Run the Web UI

```bash
python -m src.web_ui
# Open http://localhost:5050
```

## Output Format

```json
{
  "overall": "pass | partial | fail",
  "confidence": 0.87,
  "summary": "The PR implements JWT auth but is missing bcrypt hashing.",
  "requirements": [
    {
      "id": "AC-1",
      "text": "/api/login returns a signed JWT",
      "status": "pass",
      "evidence": ["src/auth/routes.py:45", "tests/test_auth.py:22"],
      "reasoning": "POST /api/login is implemented and returns a JWT token."
    }
  ],
  "test_results": [
    {"test_name": "test_login_returns_jwt", "status": "pass", "output": "PASSED"}
  ],
  "missing_coverage": ["Password hashing with bcrypt not found in diff"]
}
```

## Supported Ticket Types

| Type | How criteria are extracted |
|------|---------------------------|
| Feature / Story | Acceptance criteria from description |
| Bug | Steps-to-reproduce → expected behaviour as criteria |
| Refactor / Task | Code-quality goals (lint, coverage, bundle size) |

## Project Structure

```
jira-ticket-evaluator/
├── src/
│   ├── agents/
│   │   ├── orchestrator.py   # Multi-step agentic loop
│   │   ├── parser_agent.py   # Jira ticket → structured requirements
│   │   ├── retrieval_agent.py # GitHub PR → diff + metadata
│   │   └── testgen_agent.py  # Generates + executes tests
│   ├── main.py               # CLI entry point
│   └── web_ui.py             # Flask web dashboard
├── examples/
│   └── sample_tickets.json   # Sample tickets for 3 ticket types
├── requirements.txt
├── .env.example
└── README.md
```

## Evaluation Criteria Coverage

| Criterion | How we address it |
|-----------|-------------------|
| **Accuracy (30%)** | Orchestrator verifies each AC individually with evidence |
| **Agent Design (25%)** | 3-agent pipeline: parser → retrieval → test-gen → orchestrator synthesis |
| **MCP Integration (20%)** | GitHub MCP for PR data, Jira MCP for ticket fetch, Filesystem MCP for test execution |
| **Test Generation (15%)** | Language-aware test generation (pytest/jest) with per-criterion mapping |
| **Presentation (10%)** | Web UI + CLI + structured JSON output |

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | ✅ | Claude API key |
| `GITHUB_TOKEN` | Recommended | GitHub PAT for API access |
| `JIRA_BASE_URL` | Optional | Your Jira instance base URL |
| `JIRA_EMAIL` | Optional | Jira login email |
| `JIRA_API_TOKEN` | Optional | Jira API token |
| `TEST_TIMEOUT_SECONDS` | Optional | Max test run time (default: 30) |
