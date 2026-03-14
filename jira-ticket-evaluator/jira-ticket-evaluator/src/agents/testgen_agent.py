"""
Test-Gen Agent — writes and executes targeted tests from acceptance criteria + diff.
Supports Python (pytest) and JavaScript (jest) projects. Falls back to static analysis.
"""
import json
import os
import re
import subprocess
import tempfile
from anthropic import Anthropic

client = Anthropic()

TESTGEN_SYSTEM = """You are a senior test engineer. Given acceptance criteria and a code diff,
write targeted tests that DIRECTLY validate each criterion.

Rules:
- Detect language from the diff (look for .py, .js, .ts extensions and syntax).
- For Python: write pytest tests. For JS/TS: write Jest tests.
- Each test must map to exactly one acceptance criterion.
- Tests must be self-contained and runnable.
- Add a comment above each test linking it to its criterion.
- Return ONLY a JSON object:
{
  "language": "python" | "javascript" | "unknown",
  "test_file_content": "<full test file as a string>",
  "test_file_name": "test_pr_eval.py" or "pr_eval.test.js",
  "setup_commands": ["pip install pytest ..."],
  "run_command": "pytest test_pr_eval.py -v --tb=short"
}
"""


class TestGenAgent:
    def __init__(self):
        self.max_exec_time = int(os.getenv("TEST_TIMEOUT_SECONDS", "30"))

    def _detect_language(self, diff: str) -> str:
        if re.search(r"\.(py|pyx)\b", diff):
            return "python"
        if re.search(r"\.(js|jsx|ts|tsx)\b", diff):
            return "javascript"
        return "unknown"

    def _generate_tests(self, criteria: list[str], diff: str) -> dict:
        lang_hint = self._detect_language(diff)
        prompt = (
            f"Language hint: {lang_hint}\n\n"
            f"Acceptance criteria:\n" + "\n".join(f"- {c}" for c in criteria) +
            f"\n\nCode diff:\n```\n{diff[:6000]}\n```\n\n"
            "Write tests for each criterion."
        )
        response = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=2048,
            system=TESTGEN_SYSTEM,
            messages=[{"role": "user", "content": prompt}]
        )
        text = response.content[0].text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {"error": "Could not parse test generation output", "raw": text}

    def _run_tests(self, test_plan: dict) -> list[dict]:
        if "error" in test_plan or test_plan.get("language") == "unknown":
            return [{"test_name": "static_analysis", "status": "skipped",
                     "output": "Language not detected; skipped execution."}]

        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, test_plan.get("test_file_name", "test_eval.py"))
            with open(test_file, "w") as f:
                f.write(test_plan.get("test_file_content", ""))

            # Run setup commands (best-effort, ignore failures)
            for cmd in test_plan.get("setup_commands", []):
                try:
                    subprocess.run(cmd, shell=True, cwd=tmpdir, timeout=60,
                                   capture_output=True)
                except Exception:
                    pass

            run_cmd = test_plan.get("run_command", "pytest -v --tb=short")
            run_cmd = run_cmd.replace(test_plan.get("test_file_name", ""), test_file)

            try:
                result = subprocess.run(
                    run_cmd, shell=True, cwd=tmpdir,
                    capture_output=True, text=True,
                    timeout=self.max_exec_time
                )
                output = (result.stdout + result.stderr)[:3000]
                # Parse individual test results from pytest/jest output
                return self._parse_test_output(output, test_plan["language"])
            except subprocess.TimeoutExpired:
                return [{"test_name": "execution", "status": "error",
                         "output": f"Test run timed out after {self.max_exec_time}s"}]
            except Exception as e:
                return [{"test_name": "execution", "status": "error", "output": str(e)}]

    def _parse_test_output(self, output: str, language: str) -> list[dict]:
        results = []
        if language == "python":
            for line in output.split("\n"):
                m = re.match(r"(test_\w+)\s+(PASSED|FAILED|ERROR)", line)
                if m:
                    results.append({
                        "test_name": m.group(1),
                        "status": m.group(2).lower(),
                        "output": line.strip()
                    })
        elif language == "javascript":
            for line in output.split("\n"):
                if "✓" in line or "✗" in line or "PASS" in line or "FAIL" in line:
                    status = "pass" if ("✓" in line or "PASS" in line) else "fail"
                    results.append({"test_name": line.strip(), "status": status, "output": line.strip()})

        if not results:
            results = [{"test_name": "all_tests", "status": "unknown", "output": output[:500]}]
        return results

    def generate_and_run(self, criteria: list[str], diff: str, repo_path: str = "") -> dict:
        test_plan = self._generate_tests(criteria, diff)
        test_results = self._run_tests(test_plan)
        return {
            "generated_test_file": test_plan.get("test_file_content", ""),
            "test_file_name": test_plan.get("test_file_name", ""),
            "results": test_results,
            "language": test_plan.get("language", "unknown")
        }
