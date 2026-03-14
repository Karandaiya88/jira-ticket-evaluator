"""
Orchestrator Agent — coordinates parser, retrieval, and test-gen agents,
then synthesises the final Pass / Partial / Fail verdict.
"""
import json
from anthropic import Anthropic
from .parser_agent import ParserAgent
from .retrieval_agent import RetrievalAgent
from .testgen_agent import TestGenAgent

client = Anthropic()

SYSTEM_PROMPT = """You are an expert code-review orchestrator. Your job is to:
1. Coordinate sub-agents to gather all information about a Jira ticket and its linked PR.
2. Evaluate whether the PR satisfies each acceptance criterion from the ticket.
3. Produce a structured JSON verdict with overall status and per-requirement breakdown.

Always reason step-by-step. Use the tools available to you. After gathering evidence, emit ONLY valid JSON conforming to the verdict schema.

Verdict schema:
{
  "overall": "pass" | "partial" | "fail",
  "confidence": 0.0–1.0,
  "summary": "<1-2 sentence overall assessment>",
  "requirements": [
    {
      "id": "<req-id>",
      "text": "<requirement text>",
      "status": "pass" | "partial" | "fail",
      "evidence": ["<file:line or description>"],
      "reasoning": "<why this status>"
    }
  ],
  "test_results": [
    {
      "test_name": "<name>",
      "status": "pass" | "fail" | "error",
      "output": "<stdout/stderr snippet>"
    }
  ],
  "missing_coverage": ["<area not covered by the PR>"]
}
"""

TOOLS = [
    {
        "name": "parse_jira_ticket",
        "description": "Parse a Jira ticket (JSON or URL) to extract title, description, acceptance criteria, and ticket type.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticket_input": {"type": "string", "description": "Jira ticket URL or raw JSON string"}
            },
            "required": ["ticket_input"]
        }
    },
    {
        "name": "fetch_pr_data",
        "description": "Fetch a GitHub PR's diff, file changes, commit messages, and PR description.",
        "input_schema": {
            "type": "object",
            "properties": {
                "pr_url": {"type": "string", "description": "Full GitHub PR URL"}
            },
            "required": ["pr_url"]
        }
    },
    {
        "name": "generate_and_run_tests",
        "description": "Given acceptance criteria and code diff, generate targeted tests and execute them.",
        "input_schema": {
            "type": "object",
            "properties": {
                "criteria": {"type": "array", "items": {"type": "string"}},
                "diff": {"type": "string"},
                "repo_path": {"type": "string", "description": "Local path if repo is cloned, else empty"}
            },
            "required": ["criteria", "diff"]
        }
    }
]


class OrchestratorAgent:
    def __init__(self):
        self.parser = ParserAgent()
        self.retrieval = RetrievalAgent()
        self.testgen = TestGenAgent()
        self.history = []

    def _handle_tool(self, tool_name: str, tool_input: dict) -> str:
        if tool_name == "parse_jira_ticket":
            result = self.parser.parse(tool_input["ticket_input"])
        elif tool_name == "fetch_pr_data":
            result = self.retrieval.fetch(tool_input["pr_url"])
        elif tool_name == "generate_and_run_tests":
            result = self.testgen.generate_and_run(
                tool_input["criteria"],
                tool_input["diff"],
                tool_input.get("repo_path", "")
            )
        else:
            result = {"error": f"Unknown tool: {tool_name}"}
        return json.dumps(result, indent=2)

    def evaluate(self, jira_input: str, pr_url: str) -> dict:
        """Run the full agentic evaluation loop."""
        user_message = (
            f"Evaluate whether this GitHub PR satisfies the Jira ticket requirements.\n\n"
            f"Jira ticket: {jira_input}\n"
            f"GitHub PR: {pr_url}\n\n"
            f"Steps:\n"
            f"1. Parse the Jira ticket to extract all requirements and acceptance criteria.\n"
            f"2. Fetch the PR diff, file changes, and metadata.\n"
            f"3. Generate and run tests for key acceptance criteria.\n"
            f"4. Synthesise a structured verdict JSON."
        )

        self.history = [{"role": "user", "content": user_message}]

        while True:
            response = client.messages.create(
                model="claude-opus-4-5",
                max_tokens=4096,
                system=SYSTEM_PROMPT,
                tools=TOOLS,
                messages=self.history
            )

            # Append assistant turn
            self.history.append({"role": "assistant", "content": response.content})

            if response.stop_reason == "end_turn":
                # Extract JSON verdict from final text block
                for block in response.content:
                    if block.type == "text":
                        text = block.text.strip()
                        # Strip markdown fences if present
                        if text.startswith("```"):
                            text = text.split("```")[1]
                            if text.startswith("json"):
                                text = text[4:]
                        try:
                            return json.loads(text)
                        except json.JSONDecodeError:
                            return {"error": "Could not parse verdict JSON", "raw": block.text}
                break

            if response.stop_reason == "tool_use":
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        result = self._handle_tool(block.name, block.input)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result
                        })
                self.history.append({"role": "user", "content": tool_results})

        return {"error": "Agent loop exited without a verdict"}
