// node tests/web_dump.js data/demo_batch.jsonl -> JSON of the browser engine's demo run (used by test_web_demo.py)
const fs = require("fs"); const E = require("../web/engine.js");
const batch = fs.readFileSync(process.argv[2], "utf8").split("\n").filter(s => s.trim()).map(JSON.parse);
const r = E.runDemo(batch, { runId: "x", now: () => "t" });
process.stdout.write(JSON.stringify({ leads: r.leads, notes: r.notes, log: r.log, tiers: r.tiers }));
