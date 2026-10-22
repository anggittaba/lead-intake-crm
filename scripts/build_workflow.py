"""Generate the importable n8n workflow JSON files in workflows/. Run: python scripts/build_workflow.py"""
import json
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "workflows"
CRM = "={{ $env.CRM_BASE_URL || 'http://127.0.0.1:8830' }}"
MAIN_ID, ERR_ID = "LeadIntakeCRM01", "LeadIntakeErr01"


def http(name, pos, path, body, retry=True, **extra):
    n = {"parameters": {"method": "POST", "url": CRM + path, "sendBody": True, "specifyBody": "json",
                        "jsonBody": body, "options": {"timeout": 20000}},
         "name": name, "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2, "position": pos}
    if retry:
        n.update(retryOnFail=True, maxTries=3, waitBetweenTries=1000)
    n.update(extra)
    return n


def code(name, pos, js):
    return {"parameters": {"jsCode": js}, "name": name, "type": "n8n-nodes-base.code", "typeVersion": 2, "position": pos}


def webhook(name, pos, path, wid):
    return {"parameters": {"httpMethod": "POST", "path": path, "responseMode": "responseNode", "options": {}},
            "name": name, "type": "n8n-nodes-base.webhook", "typeVersion": 2, "position": pos, "webhookId": wid}


def if_node(name, pos, left, op):
    return {"parameters": {"conditions": {"options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose"},
                                          "conditions": [{"id": name.replace(" ", "-").lower(), "leftValue": left,
                                                          "rightValue": "", "operator": op}], "combinator": "and"},
                           "options": {}},
            "name": name, "type": "n8n-nodes-base.if", "typeVersion": 2, "position": pos}


TAG = """// Shape both intake channels into one envelope for the CRM step API.
const b = $json.body || {};
const { run_id, expected_tier, fail_first, ...payload } = b;
return [{ json: { source: '%s', run_id: run_id || ('n8n-' + $execution.id), expected_tier: expected_tier || null,
                  fail_first: Number(fail_first || 0), payload } }];"""

BUILD_STORE = """// Join the rule result with the optional LLM verdict. If the LLM branch did not run or failed, llm stays null
// and the deterministic rules decide alone.
const prep = $('Prepare: normalise + dedupe + rule score').first().json;
let llm = null;
const j = $input.first().json;
if (j && j.choices) {
  try { const t = j.choices[0].message.content; llm = JSON.parse(t.slice(t.indexOf('{'), t.lastIndexOf('}') + 1)); }
  catch (e) { llm = null; }
}
return [{ json: { prep, llm, run_id: prep.run_id, expected_tier: prep.expected_tier } }];"""

LLM_BODY = ("={{ JSON.stringify({ model: $env.LLM_MODEL || 'gpt-4o-mini', temperature: 0, messages: [{ role: 'user', "
            "content: $json.llm_prompt + JSON.stringify({ role: $json.lead.role, company: $json.lead.company, "
            "company_size: $json.lead.company_size, budget: $json.lead.budget, timeline: $json.lead.timeline, "
            "message: $json.lead.message }) }] }) }}")

nodes = [
    webhook("Web form webhook", [0, 0], "lead-form", "6f1d2c1e-lead-form"),
    webhook("WhatsApp webhook (simulated)", [0, 220], "lead-whatsapp", "6f1d2c1e-lead-whatsapp"),
    code("Tag: web form", [220, 0], TAG % "web_form"),
    code("Tag: WhatsApp", [220, 220], TAG % "whatsapp"),
    http("Prepare: normalise + dedupe + rule score", [460, 100], "/api/steps/prepare", "={{ JSON.stringify($json) }}"),
    if_node("LLM key set and not a duplicate?", [700, 100], "={{ $json.llm_enabled && !$json.duplicate_of }}",
            {"type": "boolean", "operation": "true", "singleValue": True}),
    {"parameters": {"method": "POST", "url": "={{ ($env.LLM_BASE_URL || 'https://api.openai.com/v1') + '/chat/completions' }}",
                    "sendHeaders": True, "headerParameters": {"parameters": [
                        {"name": "Authorization", "value": "={{ 'Bearer ' + $env.LLM_API_KEY }}"}]},
                    "sendBody": True, "specifyBody": "json", "jsonBody": LLM_BODY, "options": {"timeout": 20000}},
     "name": "LLM score (optional)", "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2, "position": [940, 0],
     "retryOnFail": True, "maxTries": 2, "waitBetweenTries": 2000, "onError": "continueRegularOutput"},
    code("Join rules + LLM", [1160, 100], BUILD_STORE),
    http("Store in CRM (decide route)", [1380, 100], "/api/steps/store", "={{ JSON.stringify($json) }}"),
    {"parameters": {"operation": "append", "documentId": {"__rl": True, "mode": "id", "value": "={{ $env.SHEETS_DOC_ID }}"},
                    "sheetName": {"__rl": True, "mode": "name", "value": "Leads"},
                    "columns": {"mappingMode": "autoMapInputData", "value": {}}, "options": {}},
     "name": "Google Sheets mirror (optional)", "type": "n8n-nodes-base.googleSheets", "typeVersion": 4.5,
     "position": [1600, 300], "disabled": True,
     "notes": "Disabled by default. Add Google credentials + SHEETS_DOC_ID and enable to mirror every lead to a sheet."},
    if_node("Hot or needs review?", [1600, 100], "={{ ['hot','review'].includes($json.route) }}",
            {"type": "boolean", "operation": "true", "singleValue": True}),
    http("Notify sales (Slack/Telegram or simulated)", [1840, 0], "/api/steps/notify",
         "={{ JSON.stringify({ lead_id: $json.id, run_id: $json.run_id, "
         "fail_first: $('Prepare: normalise + dedupe + rule score').first().json.fail_first }) }}"),
    {"parameters": {"respondWith": "json", "responseBody": "={{ JSON.stringify($('Store in CRM (decide route)').first().json) }}",
                    "options": {}},
     "name": "Respond", "type": "n8n-nodes-base.respondToWebhook", "typeVersion": 1.1, "position": [2080, 100]},
]
for i, n in enumerate(nodes):
    n["id"] = f"a0000000-0000-4000-8000-{i:012d}"


def c(*targets):
    return [[{"node": t, "type": "main", "index": 0} for t in tg] for tg in targets]


connections = {
    "Web form webhook": {"main": c(["Tag: web form"])},
    "WhatsApp webhook (simulated)": {"main": c(["Tag: WhatsApp"])},
    "Tag: web form": {"main": c(["Prepare: normalise + dedupe + rule score"])},
    "Tag: WhatsApp": {"main": c(["Prepare: normalise + dedupe + rule score"])},
    "Prepare: normalise + dedupe + rule score": {"main": c(["LLM key set and not a duplicate?"])},
    "LLM key set and not a duplicate?": {"main": c(["LLM score (optional)"], ["Join rules + LLM"])},
    "LLM score (optional)": {"main": c(["Join rules + LLM"])},
    "Join rules + LLM": {"main": c(["Store in CRM (decide route)"])},
    "Store in CRM (decide route)": {"main": c(["Hot or needs review?", "Google Sheets mirror (optional)"])},
    "Hot or needs review?": {"main": c(["Notify sales (Slack/Telegram or simulated)"], ["Respond"])},
    "Notify sales (Slack/Telegram or simulated)": {"main": c(["Respond"])},
}
main = {"id": MAIN_ID, "name": "Lead Intake to CRM", "active": False, "nodes": nodes, "connections": connections,
        "settings": {"executionOrder": "v1", "errorWorkflow": ERR_ID, "saveManualExecutions": True},
        "pinData": {}, "tags": []}

err_nodes = [
    {"parameters": {}, "name": "Error Trigger", "type": "n8n-nodes-base.errorTrigger", "typeVersion": 1, "position": [0, 0],
     "id": "b0000000-0000-4000-8000-000000000001"},
    {**http("Write error to run log", [240, 0], "/api/steps/log",
            "={{ JSON.stringify({ run_id: 'n8n-error', step: 'n8n.error', level: 'error', detail: "
            "($json.execution.lastNodeExecuted || '?') + ': ' + (($json.execution.error || {}).message || 'unknown error') "
            "+ ' (execution ' + $json.execution.id + ')' }) }}"), "id": "b0000000-0000-4000-8000-000000000002"},
]
err = {"id": ERR_ID, "name": "Lead Intake: error handler", "active": False, "nodes": err_nodes,
       "connections": {"Error Trigger": {"main": c(["Write error to run log"])}},
       "settings": {"executionOrder": "v1"}, "pinData": {}, "tags": []}

OUT.mkdir(exist_ok=True)
(OUT / "lead-intake-to-crm.json").write_text(json.dumps(main, indent=2) + "\n")
(OUT / "lead-intake-error-handler.json").write_text(json.dumps(err, indent=2) + "\n")
print("wrote", OUT)
