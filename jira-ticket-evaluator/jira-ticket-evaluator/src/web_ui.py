"""
Web UI — Flask app providing a browser-based interface for the evaluator.
Run with: python -m src.web_ui
"""
import json
from flask import Flask, request, jsonify, render_template_string
from src.agents.orchestrator import OrchestratorAgent

app = Flask(__name__)

HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Jira Ticket Evaluator</title>
<style>
  :root { --green: #1D9E75; --red: #D85A30; --amber: #BA7517; --gray: #888780; }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: system-ui, sans-serif; background: #f5f4ef; color: #2c2c2a; min-height: 100vh; }
  .header { background: #fff; border-bottom: 1px solid #d3d1c7; padding: 16px 32px; display: flex; align-items: center; gap: 12px; }
  .header h1 { font-size: 18px; font-weight: 600; }
  .badge { background: #e1f5ee; color: #0F6E56; font-size: 11px; padding: 3px 8px; border-radius: 4px; font-weight: 600; }
  .container { max-width: 900px; margin: 40px auto; padding: 0 24px; }
  .card { background: #fff; border: 1px solid #d3d1c7; border-radius: 12px; padding: 28px; margin-bottom: 24px; }
  label { display: block; font-size: 13px; font-weight: 600; color: var(--gray); margin-bottom: 6px; text-transform: uppercase; letter-spacing: 0.05em; }
  input, textarea { width: 100%; border: 1px solid #d3d1c7; border-radius: 8px; padding: 10px 14px; font-size: 14px; font-family: inherit; outline: none; transition: border-color 0.15s; }
  input:focus, textarea:focus { border-color: var(--green); }
  textarea { min-height: 100px; resize: vertical; }
  .form-row { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 16px; }
  button { background: #2c2c2a; color: #fff; border: none; border-radius: 8px; padding: 12px 28px; font-size: 14px; font-weight: 600; cursor: pointer; transition: opacity 0.15s; }
  button:hover { opacity: 0.85; }
  button:disabled { opacity: 0.5; cursor: not-allowed; }
  .spinner { display: none; width: 20px; height: 20px; border: 2px solid #fff; border-top-color: transparent; border-radius: 50%; animation: spin 0.7s linear infinite; vertical-align: middle; margin-left: 8px; }
  @keyframes spin { to { transform: rotate(360deg); } }
  #result { display: none; }
  .verdict-badge { display: inline-flex; align-items: center; gap: 8px; font-size: 22px; font-weight: 700; padding: 10px 20px; border-radius: 10px; margin-bottom: 16px; }
  .verdict-pass { background: #e1f5ee; color: #0F6E56; }
  .verdict-partial { background: #faeeda; color: #854F0B; }
  .verdict-fail { background: #faece7; color: #993C1D; }
  .req-list { list-style: none; }
  .req-item { border-left: 3px solid #d3d1c7; padding: 12px 16px; margin-bottom: 10px; border-radius: 0 8px 8px 0; background: #f5f4ef; }
  .req-pass { border-color: var(--green); }
  .req-partial { border-color: var(--amber); }
  .req-fail { border-color: var(--red); }
  .req-id { font-size: 11px; font-weight: 700; text-transform: uppercase; color: var(--gray); }
  .req-text { font-size: 14px; font-weight: 600; margin: 4px 0; }
  .req-reason { font-size: 13px; color: #5F5E5A; }
  .evidence { font-size: 12px; color: var(--green); font-family: monospace; margin-top: 4px; }
  .tests-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 8px; }
  .test-item { background: #f5f4ef; border-radius: 8px; padding: 10px 14px; font-size: 13px; display: flex; align-items: center; gap: 8px; }
  .missing { color: var(--amber); font-size: 13px; padding: 6px 0; border-bottom: 1px solid #f1efe8; }
  .confidence-bar { background: #f1efe8; border-radius: 20px; height: 8px; margin-top: 8px; }
  .confidence-fill { height: 8px; border-radius: 20px; background: var(--green); transition: width 0.5s; }
  .error-box { background: #faece7; border: 1px solid #f0997b; border-radius: 8px; padding: 14px 18px; color: #993C1D; font-size: 14px; }
</style>
</head>
<body>
<div class="header">
  <h1>Jira Ticket Evaluator</h1>
  <span class="badge">AI-Powered</span>
</div>
<div class="container">
  <div class="card">
    <div class="form-row">
      <div>
        <label>Jira Ticket</label>
        <input type="text" id="jira" placeholder="https://org.atlassian.net/browse/PROJ-123 or paste JSON" />
      </div>
      <div>
        <label>GitHub PR URL</label>
        <input type="text" id="pr" placeholder="https://github.com/owner/repo/pull/42" />
      </div>
    </div>
    <button id="evalBtn" onclick="evaluate()">
      Evaluate PR
      <span class="spinner" id="spinner"></span>
    </button>
  </div>

  <div id="result"></div>
</div>

<script>
async function evaluate() {
  const jira = document.getElementById('jira').value.trim();
  const pr = document.getElementById('pr').value.trim();
  if (!jira || !pr) { alert('Please fill in both fields.'); return; }

  const btn = document.getElementById('evalBtn');
  const spinner = document.getElementById('spinner');
  btn.disabled = true;
  spinner.style.display = 'inline-block';

  document.getElementById('result').style.display = 'none';

  try {
    const resp = await fetch('/evaluate', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({jira, pr})
    });
    const data = await resp.json();
    renderVerdict(data);
  } catch (e) {
    document.getElementById('result').innerHTML = `<div class="error-box">Request failed: ${e.message}</div>`;
    document.getElementById('result').style.display = 'block';
  } finally {
    btn.disabled = false;
    spinner.style.display = 'none';
  }
}

function renderVerdict(v) {
  if (v.error) {
    document.getElementById('result').innerHTML = `<div class="error-box">Error: ${v.error}</div>`;
    document.getElementById('result').style.display = 'block';
    return;
  }

  const overall = (v.overall || 'unknown').toLowerCase();
  const icons = {pass: '✅', partial: '⚠️', fail: '❌'};
  const conf = Math.round((v.confidence || 0) * 100);

  let reqs = (v.requirements || []).map(r => `
    <li class="req-item req-${r.status}">
      <div class="req-id">${r.id} · ${r.status?.toUpperCase()}</div>
      <div class="req-text">${r.text}</div>
      <div class="req-reason">${r.reasoning}</div>
      ${(r.evidence||[]).map(e => `<div class="evidence">→ ${e}</div>`).join('')}
    </li>`).join('');

  let tests = (v.test_results || []).map(t => {
    const icon = t.status === 'pass' ? '✅' : t.status === 'fail' ? '❌' : '⏭';
    return `<div class="test-item">${icon} ${t.test_name}</div>`;
  }).join('');

  let missing = (v.missing_coverage || []).map(m => `<div class="missing">⚠️ ${m}</div>`).join('');

  document.getElementById('result').innerHTML = `
    <div class="card">
      <div class="verdict-badge verdict-${overall}">${icons[overall] || '❓'} ${overall.toUpperCase()}</div>
      <p style="font-size:15px; color:#5F5E5A; margin-bottom: 12px;">${v.summary || ''}</p>
      <div style="font-size:13px; color:#888780; margin-bottom:4px;">Confidence: ${conf}%</div>
      <div class="confidence-bar"><div class="confidence-fill" style="width:${conf}%"></div></div>
    </div>
    ${reqs ? `<div class="card"><h3 style="margin-bottom:14px;font-size:15px;">Requirements</h3><ul class="req-list">${reqs}</ul></div>` : ''}
    ${tests ? `<div class="card"><h3 style="margin-bottom:14px;font-size:15px;">Test Results</h3><div class="tests-grid">${tests}</div></div>` : ''}
    ${missing ? `<div class="card"><h3 style="margin-bottom:10px;font-size:15px;">Missing Coverage</h3>${missing}</div>` : ''}
  `;
  document.getElementById('result').style.display = 'block';
  document.getElementById('result').scrollIntoView({behavior: 'smooth'});
}
</script>
</body>
</html>
"""


@app.route("/")
def index():
    return render_template_string(HTML)


@app.route("/evaluate", methods=["POST"])
def evaluate():
    data = request.get_json()
    jira = data.get("jira", "").strip()
    pr = data.get("pr", "").strip()
    if not jira or not pr:
        return jsonify({"error": "jira and pr fields are required"}), 400

    agent = OrchestratorAgent()
    verdict = agent.evaluate(jira, pr)
    return jsonify(verdict)


if __name__ == "__main__":
    app.run(debug=True, port=5050)
