// node tests/web_score.js file.jsonl -> per-row normalize + rule score from the browser engine
const fs = require("fs"); const E = require("../web/engine.js");
const rows = fs.readFileSync(process.argv[2], "utf8").split("\n").filter(s => s.trim()).map(JSON.parse);
process.stdout.write(JSON.stringify(rows.map(r => { const l = E.normalize(r, r.source || "web_form"); return { lead: l, rules: E.scoreRules(l) }; })));
