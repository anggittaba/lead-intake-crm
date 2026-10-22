/* Browser port of leadcrm/normalize.py, scoring.py (rules only), dedupe.py, notify.py and the built-in demo pipeline.
 * Same rules, same thresholds, same 24 synthetic leads. Verified against the Python engine by tests/test_web_demo.py. */
(function (root) {
  "use strict";
  // ---- normalize.py
  const EMAIL_RE = /[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/;
  const COMPANY_SUFFIX = /\b(pt|cv|tbk|inc|llc|ltd|limited|gmbh|co|corp|corporation|company|pte|sdn bhd|bv)\b\.?/gi;
  const SIZE_BUCKETS = ["1-10", "11-50", "51-200", "201-1000", "1000+"];
  const clean = s => (s === null || s === undefined) ? "" : String(s).normalize("NFKC").replace(/\s+/g, " ").trim();
  const normEmail = s => { const m = clean(s).toLowerCase().match(EMAIL_RE); return m ? m[0] : ""; };
  function normPhone(s, cc = "62") {
    let d = clean(s).replace(/\D/g, "");
    if (!d) return "";
    if (d.startsWith("00")) d = d.slice(2); else if (d.startsWith("0")) d = cc + d.slice(1);
    return d.length >= 8 && d.length <= 15 ? d : "";
  }
  const isUpper = w => /[A-Za-z]/.test(w) && w === w.toUpperCase();
  function normName(s) {
    s = clean(s).replace(/[^\w\s.'-]/g, "");
    return s.split(/\s+/).filter(Boolean)
      .map(w => (!isUpper(w) || w.length > 3) ? w.slice(0, 1).toUpperCase() + w.slice(1).toLowerCase() : w).join(" ");
  }
  function companyKey(s) {
    s = clean(s).toLowerCase().replace(COMPANY_SUFFIX, " ").replace(/[^a-z0-9 ]/g, " ");
    return s.replace(/\s+/g, " ").trim();
  }
  function normSize(s) {
    s = clean(s).toLowerCase().replace(/ /g, "").replace(/employees/g, "").replace(/people/g, "");
    if (SIZE_BUCKETS.includes(s)) return s;
    const nums = (s.replace(/,/g, "").match(/\d+/g) || []).map(Number);
    if (!nums.length) return "";
    const n = Math.max(...nums);
    for (const [lim, b] of [[10, "1-10"], [50, "11-50"], [200, "51-200"], [1000, "201-1000"]]) if (n <= lim) return b;
    return "1000+";
  }
  function fromForm(p) {
    return { name: normName(p.name || p.full_name), email: normEmail(p.email), phone: normPhone(p.phone),
      company: clean(p.company), role: clean(p.role || p.job_title), company_size: normSize(p.company_size),
      budget: clean(p.budget), timeline: clean(p.timeline), message: clean(p.message), source: "web_form" };
  }
  function fromWhatsapp(p) {
    const text = clean(p.text);
    const m = text.match(/\b(?:from|at|dari|di)\s+([A-Z][\w&.-]*(?:\s+[A-Z][\w&.-]*){0,3})/);
    return { name: normName(p.profile_name), email: normEmail(text), phone: normPhone(p.from),
      company: m ? clean(m[1].split(/[.,!?]\s/)[0].replace(/[.,]+$/, "")) : "", role: "", company_size: "",
      budget: "", timeline: "", message: text, source: "whatsapp" };
  }
  const normalize = (p, src) => src === "whatsapp" ? fromWhatsapp(p) : fromForm(p);

  // ---- scoring.py (rule scorer; the optional LLM scorer needs a server-side key and is not in the browser)
  const HOT_AT = 7, WARM_AT = 3, REVIEW_BELOW = 0.6, IDR_PER_USD = 16000;
  const FREE_MAIL = new Set(["gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "ymail.com", "icloud.com", "proton.me", "mail.com"]);
  const DECISION = /\b(founder|co-?founder|ceo|cto|coo|cfo|owner|director|head|vp|vice president|chief|partner|general manager|gm|manager|lead|pemilik|direktur|kepala)\b/i;
  const JUNIOR = /\b(student|intern|mahasiswa|trainee|fresh ?graduate)\b/i;
  const SPAM = /\b(seo services?|backlinks?|guest post|crypto|forex|casino|loan offer|rank (your|on) google|followers|web traffic|outsourc\w* (our|my) team)\b/i;
  const JOBSEEK = /\b(internship|looking for (a )?(job|work)|my cv|my resume|lowongan|hiring me|job opening|apply(ing)? for)\b/i;
  const INTENT = /\b(demo|pricing|price|quote|quotation|proposal|contract|integrat\w*|automat\w*|crm|onboard\w*|pilot|penawaran|harga|rollout|go live|implement\w*)\b/gi;
  const URGENT = /\b(asap|urgent|this week|next week|this month|within (a|one|1|2|two) (week|month)s?|(1|2|3|two|three) weeks?|minggu ini|bulan ini|segera|before the end of the month|immediately)\b/i;
  const SOON = /\b(next month|next quarter|1-3 months|(1|2|3|one|two|three)(-| to )?(3 )?months?|q[1-4]|bulan depan|this quarter)\b/i;
  const LATER = /\b(next year|just (browsing|exploring|looking|curious)|no rush|someday|maybe later|tahun depan|not sure when|research(ing)? only|for a (school|class|university) project)\b/i;
  const MONEY = /(?:(usd|\$|rp\.?|idr|sgd|s\$|eur|€)\s*)?(\d[\d.,]*)\s*(k|rb|ribu|jt|juta|m|mn|million)?\s*(usd|idr|sgd|eur)?/gi;
  const INTEREST = /\b(interested|tertarik|we need|need to|we want|looking at|looking to|mau|butuh|ingin)\b/i;
  const MULT = { k: 1e3, rb: 1e3, ribu: 1e3, jt: 1e6, juta: 1e6, m: 1e6, mn: 1e6, million: 1e6 };
  const pyFloat = s => /^\d*\.?\d*$/.test(s) && /\d/.test(s) ? Number(s) : NaN;

  function budgetUsd(text) {
    let best = 0;
    for (const m of (text || "").matchAll(MONEY)) {
      const num = m[2]; const cur = (m[1] || m[4] || "").toLowerCase(); const mult = (m[3] || "").toLowerCase();
      if (!cur && !mult) continue;
      const dots = num.split(".").length - 1;
      let v = (dots <= 1 && !num.slice(-3, -2).includes(",")) ? pyFloat(num.replace(/,/g, "")) : pyFloat(num.replace(/[.,]/g, ""));
      if (Number.isNaN(v)) continue;
      if (["rp", "rp.", "idr"].includes(cur) && /^\d{1,3}(\.\d{3})+$/.test(num)) v = Number(num.replace(/\./g, ""));
      v *= MULT[mult] || 1;
      if (["rp", "rp.", "idr"].includes(cur) || ["jt", "juta", "rb", "ribu"].includes(mult)) v /= IDR_PER_USD;
      else if (cur === "sgd" || cur === "s$") v *= 0.75;
      else if (cur === "eur" || cur === "€") v *= 1.08;
      best = Math.max(best, v);
    }
    return best;
  }
  const tierOf = p => p >= HOT_AT ? "hot" : p >= WARM_AT ? "warm" : "cold";
  const usd = b => "$" + Math.round(b).toLocaleString("en-US");   // f"{b:,.0f}" (budgets here are not .5 ties)
  const round2 = x => Number(x.toFixed(2));

  function scoreRules(lead) {
    const sig = []; const msg = lead.message || "";
    const blob = ["message", "timeline", "budget"].map(k => lead[k] || "").join(" ");
    if (SPAM.test(msg)) return { tier: "cold", points: -5, confidence: 0.95, reason: "Looks like a vendor pitch / spam", signals: [["spam pattern", -5]] };
    if (JOBSEEK.test(msg)) return { tier: "cold", points: -4, confidence: 0.9, reason: "Job seeker, not a buyer", signals: [["job-seeking language", -4]] };
    const b = budgetUsd((lead.budget || "") + " " + msg);
    if (b >= 10000) sig.push([`budget ~${usd(b)}`, 3]); else if (b >= 3000) sig.push([`budget ~${usd(b)}`, 2]);
    else if (b > 0) sig.push([`small budget ~${usd(b)}`, 1]);
    if (URGENT.test(blob)) sig.push(["needs it within weeks", 3]); else if (SOON.test(blob)) sig.push(["timeline 1-3 months", 1]);
    else if (LATER.test(blob)) sig.push(["no near-term timeline", -2]);
    const role = lead.role || "";
    if (JUNIOR.test(role) || JUNIOR.test(msg)) sig.push(["student / intern", -2]); else if (DECISION.test(role)) sig.push(["decision-maker role", 2]);
    const size = lead.company_size || "";
    if (["51-200", "201-1000", "1000+"].includes(size)) sig.push([`company ${size}`, 2]); else if (size === "11-50") sig.push(["company 11-50", 1]);
    const intents = [...new Set([...msg.matchAll(INTENT)].map(m => m[1].toLowerCase()))].sort();
    if (intents.length) sig.push([`buying intent (${intents.slice(0, 3).join(", ")})`, Math.min(2, intents.length)]);
    if (INTEREST.test(msg)) sig.push(["states a need", 1]);
    const email = lead.email || ""; const dom = email.slice(email.lastIndexOf("@") + 1);
    if (FREE_MAIL.has(dom) && !lead.company) sig.push(["free email, no company", -1]);
    if ([...msg].length < 15) sig.push(["almost no message", -1]);
    let pts = sig.reduce((a, s) => a + s[1], 0);
    if (pts >= HOT_AT && !(URGENT.test(blob) || b >= 3000)) {
      sig.push(["no budget >= $3k and no urgent timeline: capped at warm", HOT_AT - 1 - pts]); pts = HOT_AT - 1;
    }
    const tier = tierOf(pts);
    const margin = Math.min(Math.abs(pts - (HOT_AT - 0.5)), Math.abs(pts - (WARM_AT - 0.5)));
    const known = ["company", "role", "company_size", "budget", "timeline"].filter(k => lead[k]).length;
    const conf = Math.min(0.95, 0.35 + 0.2 * margin) - ((known <= 1 && !URGENT.test(blob) && b === 0) ? 0.15 : 0);
    const confidence = round2(Math.max(0.05, conf));
    const pos = [...sig].sort((x, y) => y[1] - x[1]).filter(s => s[1] > 0).slice(0, 2).map(s => s[0]);
    const neg = sig.filter(s => s[1] < 0).slice(0, 1).map(s => s[0]);
    const reason = [...pos, ...neg].join("; ") || "no buying signals";
    return { tier, points: pts, confidence, reason: reason[0].toUpperCase() + reason.slice(1), signals: sig.map(s => [...s]) };
  }
  function decide(rules) {
    const why = [];
    if (rules.confidence < REVIEW_BELOW) why.push(`low rule confidence (${rules.confidence.toFixed(2)})`);
    return { tier: rules.tier, needs_review: why.length > 0, review_reason: why.join("; ") };
  }

  // ---- dedupe.py, with a port of difflib.SequenceMatcher.ratio() (no junk; autojunk only matters for >= 200 chars)
  function seqRatio(a, b) {
    if (!a || !b) return 0;
    const b2j = new Map(); [...b].forEach((c, j) => { if (!b2j.has(c)) b2j.set(c, []); b2j.get(c).push(j); });
    if (b.length >= 200) { const ntest = Math.floor(b.length / 100) + 1; for (const [c, idx] of [...b2j]) if (idx.length > ntest) b2j.delete(c); }
    function longest(alo, ahi, blo, bhi) {
      let bi = alo, bj = blo, bs = 0, j2len = new Map();
      for (let i = alo; i < ahi; i++) {
        const nj = new Map();
        for (const j of (b2j.get(a[i]) || [])) {
          if (j < blo) continue; if (j >= bhi) break;
          const k = (j2len.get(j - 1) || 0) + 1; nj.set(j, k);
          if (k > bs) { bi = i - k + 1; bj = j - k + 1; bs = k; }
        }
        j2len = nj;
      }
      while (bi > alo && bj > blo && !b2j.has(b[bj - 1]) && a[bi - 1] === b[bj - 1]) { bi--; bj--; bs++; }
      while (bi + bs < ahi && bj + bs < bhi && !b2j.has(b[bj + bs]) && a[bi + bs] === b[bj + bs]) bs++;
      return [bi, bj, bs];
    }
    let matched = 0; const queue = [[0, a.length, 0, b.length]];
    while (queue.length) {
      const [alo, ahi, blo, bhi] = queue.pop(); const [i, j, k] = longest(alo, ahi, blo, bhi);
      if (k) { matched += k; if (alo < i && blo < j) queue.push([alo, i, blo, j]); if (i + k < ahi && j + k < bhi) queue.push([i + k, ahi, j + k, bhi]); }
    }
    return 2 * matched / (a.length + b.length);
  }
  function findDuplicate(lead, existing) {
    const name = (lead.name || "").toLowerCase(); const ck = companyKey(lead.company || "");
    let best = null, bestS = 0;
    for (const e of existing) {
      if (lead.email && lead.email === e.email) return [e, "same email"];
      if (lead.phone && lead.phone === e.phone) return [e, "same phone"];
      if (name && ck) {
        const ns = seqRatio(name, (e.name || "").toLowerCase()); const cs = seqRatio(ck, companyKey(e.company || ""));
        if (ns >= 0.85 && cs >= 0.80 && ns + cs > bestS) { best = e; bestS = ns + cs; }
      }
    }
    return best ? [best, `similar name + company (${(bestS / 2).toFixed(2)})`] : [null, ""];
  }

  // ---- notify.py (always simulated here) + pipeline.py + app.run_demo
  const TIER_MARK = { hot: "[HOT]", warm: "[WARM]", cold: "[COLD]" };
  function messageFor(l) {
    const who = l.name || "Unknown";
    const at = l.role && l.company ? ` (${l.role}, ${l.company})` : l.company ? ` (${l.company})` : "";
    if (l.status === "review") return `[REVIEW] ${who}${at}: ${l.review_reason}. Rules: ${l.tier}. Open lead #${l.id}.`;
    return `${TIER_MARK[l.tier] || ""} ${who}${at} via ${l.source}: ${l.reason}. Lead #${l.id}.`;
  }
  const sgn = n => (n >= 0 ? "+" : "") + n;

  function runDemo(batch, opts = {}) {
    const now = opts.now || (() => new Date().toISOString());
    const runId = opts.runId || "demo-" + Math.random().toString(16).slice(2, 8);
    const leads = [], notes = [], log = [];
    const L = (step, detail, lead_id = null, level = "info") => log.push({ at: now(), run_id: runId, lead_id, step, level, detail });
    L("demo.start", `engine=browser (same rules as built-in), ${batch.length} synthetic leads`);
    batch.forEach((row, i) => {
      const payload = Object.fromEntries(Object.entries(row).filter(([k]) => !["label", "dup", "source"].includes(k)));
      const src = row.source;
      const lead = normalize(payload, src);
      L("normalize", `${src}: ${lead.name || "?"} <${lead.email || lead.phone || "no contact"}>`);
      const [dup, why] = findDuplicate(lead, leads.filter(x => x.duplicate_of === null));
      if (dup) L("dedupe", `duplicate of #${dup.id} (${why})`);
      const rules = scoreRules(lead);
      if (!dup) L("score.rules", `${rules.tier} ${sgn(rules.points)} pts, conf ${rules.confidence.toFixed(2)}: ${rules.reason}`);
      const rec = { ...lead, id: leads.length + 1, created_at: now(), run_id: runId, raw: payload, tier: rules.tier, points: rules.points,
        confidence: rules.confidence, reason: rules.reason, signals: rules.signals, expected_tier: row.label,
        status: null, review_reason: null, duplicate_of: null, duplicate_reason: null };
      let route;
      if (dup) { Object.assign(rec, { status: "duplicate", duplicate_of: dup.id, duplicate_reason: why }); route = "duplicate"; }
      else { const d = decide(rules); route = d.needs_review ? "review" : rules.tier; Object.assign(rec, { status: d.needs_review ? "review" : "auto", review_reason: d.review_reason }); }
      leads.push(rec);
      L("crm.store", `lead #${rec.id} stored, route=${route}` + (route === "review" ? ` (${rec.review_reason})` : ""), rec.id);
      rec.route = route;
      if (route === "hot" || route === "review") {
        const failFirst = i === 3 ? 2 : 0; let attempts = 0;
        for (let n = 1; n <= 3; n++) { attempts = n; if (n <= failFirst) { L("notify.retry", `attempt ${n} failed: ConnectionError: simulated 503 from notification API`, rec.id, "warn"); continue; } break; }
        const text = messageFor(rec);
        notes.push({ at: now(), run_id: runId, lead_id: rec.id, channel: "slack", mode: "simulated", status: "sent", attempts, text, error: "" });
        L("notify", `slack (simulated) sent after ${attempts} attempt(s)`, rec.id);
      }
    });
    L("demo.done", `${leads.length} rows in CRM`);
    const orig = leads.filter(x => x.status !== "duplicate");
    const tiers = { hot: 0, warm: 0, cold: 0 }; orig.filter(x => x.status !== "review").forEach(x => tiers[x.tier]++);
    return { run_id: runId, leads, orig, tiers, review: leads.filter(x => x.status === "review"),
      dups: leads.filter(x => x.status === "duplicate"), notes, log,
      retries: log.filter(r => r.step === "notify.retry").length, errors: log.filter(r => r.level === "error").length };
  }
  const api = { normalize, scoreRules, budgetUsd, findDuplicate, seqRatio, companyKey, messageFor, runDemo };
  if (typeof module !== "undefined" && module.exports) module.exports = api; else root.LeadEngine = api;
})(typeof window !== "undefined" ? window : globalThis);
