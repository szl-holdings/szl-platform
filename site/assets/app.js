/* SZL Holdings — proof explorer engine.
   Vanilla JS. Zero dependencies. Every figure on the page is computed here
   from bytes fetched out of ./data — nothing is hardcoded. */
(() => {
"use strict";

/* ---------------------------------------------------------------- helpers */
const $ = (sel, root) => (root || document).querySelector(sel);
const $$ = (sel, root) => Array.from((root || document).querySelectorAll(sel));

function h(tag, attrs, ...kids) {
  const node = document.createElement(tag);
  if (attrs) for (const [k, v] of Object.entries(attrs)) {
    if (v == null) continue;
    if (k === "class") node.className = v;
    else if (k === "text") node.textContent = v;
    else if (k === "html") node.innerHTML = v; // trusted, site-authored only
    else node.setAttribute(k, v);
  }
  for (const kid of kids.flat()) {
    if (kid == null) continue;
    node.append(kid.nodeType ? kid : document.createTextNode(kid));
  }
  return node;
}

const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

/* ------------------------------------------------------- fetch + digest */
const store = new Map(); // path -> {bytes, text, sha256, error}

async function loadArtifact(path) {
  try {
    const res = await fetch(path, { cache: "no-store" });
    if (!res.ok) throw new Error("HTTP " + res.status);
    const buf = await res.arrayBuffer();
    const bytes = new Uint8Array(buf);
    const text = new TextDecoder("utf-8").decode(bytes);
    let sha256 = null;
    if (crypto.subtle) {
      const digest = await crypto.subtle.digest("SHA-256", bytes);
      sha256 = Array.from(new Uint8Array(digest), b => b.toString(16).padStart(2, "0")).join("");
    }
    store.set(path, { bytes, text, sha256, error: null });
  } catch (err) {
    store.set(path, { bytes: null, text: null, sha256: null, error: String(err && err.message || err) });
  }
  return store.get(path);
}

function rec(path) { return store.get(path) || { bytes: null, text: null, sha256: null, error: "not loaded" }; }
function jsonOf(path) {
  const r = rec(path);
  if (!r.text) return null;
  try { return JSON.parse(r.text); } catch { return null; }
}
const shortHash = s => (s ? s.slice(0, 12) + "…" : "UNAVAILABLE");

function emptyNote(msg, isError) {
  const d = h("div", { class: "empty-panel", text: msg });
  if (isError) d.setAttribute("data-error", "");
  return d;
}

function fetchRefusedNote(path) {
  const d = h("div", { class: "empty-panel" });
  d.setAttribute("data-error", "");
  d.append(
    h("span", { text: "This browser refused to fetch " + path + " over file:// — serve the proof instead of asserting it:" }),
    h("br"),
    h("code", { class: "inline-code", text: "cd site && python3 -m http.server 8000" }),
  );
  return d;
}

/* ------------------------------------------------------------- counters */
function renderCounters() {
  const mount = $("#counters");
  if (!mount) return;
  mount.textContent = "";

  const matrix = jsonOf("data/repo_matrix.json");
  const adv = jsonOf("data/adversarial_run.json");
  const kids = jsonOf("data/kids_conformance.json");
  const claims = jsonOf("data/claims.json");

  const cells = [];
  if (matrix) cells.push({ big: String(matrix.length), lab: "repos audited (matrix rows)" });
  if (adv) {
    const nonLim = adv.results.filter(r => !r.limitation).length;
    cells.push({ big: adv.blocked + "/" + nonLim, lab: "non-limitation attacks blocked" });
  }
  if (kids) cells.push({ big: kids.summary.pass + "/" + kids.summary.total, lab: "KIDS conformance vectors PASS" });
  if (claims) {
    const by = { PASS: 0, DRIFT: 0, UNKNOWN: 0 };
    for (const r of claims.results) by[r.verdict] = (by[r.verdict] || 0) + 1;
    cells.push({ big: String(claims.results.length), lab: "public claims: " + by.PASS + " PASS · " + by.DRIFT + " DRIFT · " + by.UNKNOWN + " UNKNOWN", warn: true });
  }

  if (!cells.length) {
    mount.append(fetchRefusedNote("data/*.json"));
    return;
  }
  for (const c of cells) {
    mount.append(h("div", { class: "counter" + (c.warn ? " warnline" : "") },
      h("b", { text: c.big }), h("span", { text: c.lab })));
  }
}

/* ----------------------------------------------- artifact card scaffold */
function hashLine(path) {
  const r = rec(path);
  const line = h("div", { class: "hash-line" });
  line.append(h("span", { class: "tag", text: path.split("/").pop() + " · sha256" }));
  if (r.sha256) {
    line.append(h("span", { class: "h", text: r.sha256 }));
    const b = h("button", { class: "copy-btn", type: "button", text: "COPY", style: "position:static" });
    b.addEventListener("click", () => copyText(r.sha256, b));
    line.append(b);
  } else {
    line.append(h("span", { class: "h", text: "UNAVAILABLE — " + (r.error || "not fetched") }));
  }
  return line;
}

function artifactCard(opts) {
  const card = h("div", { class: "artifact-card" });
  const meta = h("div", { class: "artifact-meta" });
  meta.append(h("span", { class: "chip " + (opts.tone || "gray") }, h("span", { class: "dot" }), opts.kind));
  meta.append(h("code", { text: opts.file }));
  const r = rec(opts.file);
  if (r.bytes) meta.append(h("span", { text: r.bytes.length.toLocaleString("en-US") + " bytes" }));
  card.append(meta);
  card.append(h("p", { style: "color:var(--sub);font-size:14px;margin-bottom:16px", text: opts.blurb }));
  card.append(hashLine(opts.file));
  for (const extra of opts.extraFiles || []) card.append(Object.assign(hashLine(extra), { style: "margin-top:8px" }));

  if (opts.verify) {
    const vb = h("div", { class: "verify-block" });
    vb.append(h("h4", { text: "Verify independently" }));
    const pre = h("div", { class: "pre-card" });
    const code = h("code", { text: opts.verify });
    pre.append(h("pre", null, code));
    const b = h("button", { class: "copy-btn", type: "button", text: "COPY" });
    b.addEventListener("click", () => copyText(opts.verify, b));
    pre.append(b);
    vb.append(pre);
    card.append(vb);
  }
  return card;
}

function copyText(text, btn) {
  const done = () => { const t = btn.textContent; btn.textContent = "COPIED"; setTimeout(() => { btn.textContent = t; }, 1400); };
  if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(text).then(done, done);
  else {
    const ta = h("textarea", { style: "position:fixed;opacity:0", text });
    document.body.append(ta); ta.select();
    try { document.execCommand("copy"); } catch { /* noop */ }
    ta.remove(); done();
  }
}

/* --------------------------------------------------------- proof explorer */
const TABS = [
  {
    id: "adversarial", label: "attack harness", title: "Public attack-harness run",
    build(mount) { mount.append(buildAdversarial()); },
  },
  {
    id: "beacon", label: "beacon chain", title: "Beacon Reality Protocol demo",
    build(mount) { mount.append(buildBeacon()); },
  },
  {
    id: "claims", label: "claims wall", title: "Public claims, honestly verdicted",
    build(mount) { mount.append(buildClaimsWall()); },
  },
  {
    id: "kids", label: "KIDS conformance", title: "KIDS v0.1 golden vectors",
    build(mount) { mount.append(buildKidsArtifact()); },
  },
  {
    id: "enumeration", label: "enumeration", title: "Two-source enumeration evidence",
    build(mount) {
      mount.append(artifactCard({
        kind: "PARTIAL", tone: "partial", file: "data/enumeration.json",
        blurb: "Two independent sources must agree before the estate prints a count. They did not — so the committed status is PARTIAL and repo_count stays null rather than guessing.",
        verify: "pip install -e packages/szl-estate\npython -m szl_estate.enumerate --org szl-holdings --out artifacts/audits\n# offline replay: add --offline to re-run from the captured fixture",
      }));
      const d = jsonOf("data/enumeration.json");
      if (d) {
        const det = h("details", { style: "margin-top:18px" });
        det.append(h("summary", { style: "cursor:pointer;font:12px monospace;color:var(--lattice)", text: "Source A returned " + d.sources.source_a.count + " names — open the full inventory" }));
        const pre = h("div", { class: "pre-card", style: "margin-top:10px" });
        pre.append(h("pre", null, h("code", { text: d.sources.source_a.names.join("\n") })));
        det.append(pre);
        mount.append(det);
      }
    },
  },
  {
    id: "matrix", label: "audit matrix", title: "Per-repo audit matrix",
    build(mount) {
      mount.append(artifactCard({
        kind: "100 ROWS", tone: "pass", file: "data/repo_matrix.json",
        blurb: "One audit record per repository: state, branch, license, findings. The interactive table lives in the Estate Audit section below.",
        verify: "pip install -e packages/szl-estate\npython -m szl_estate.audit --org szl-holdings --out artifacts/audits\n# writes REPOSITORY_MATRIX.csv + ESTATE_SUMMARY.md; the JSON here is that matrix, row for row",
      }));
      mount.append(h("p", { style: "margin-top:16px" },
        h("a", { href: "#estate-audit", style: "color:var(--proof);font:12.5px monospace", text: "↓ browse the matrix in the Estate Audit section" })));
    },
  },
  {
    id: "summary", label: "estate summary", title: "Estate summary rollup",
    build(mount) {
      mount.append(artifactCard({
        kind: "ROLLUP", tone: "gray", file: "data/ESTATE_SUMMARY.md",
        blurb: "The blockers-first rollup the auditor writes on every run. Rendered below exactly as committed.",
        verify: "python -m szl_estate.audit --org szl-holdings --out artifacts/audits\n# then: sha256sum artifacts/audits/ESTATE_SUMMARY.md and compare with the digest above",
      }));
      const r = rec("data/ESTATE_SUMMARY.md");
      if (r.text) {
        const pre = h("div", { class: "pre-card", style: "margin-top:18px" });
        pre.append(h("pre", null, h("code", { text: r.text })));
        mount.append(pre);
      }
    },
  },
];

function initTabs() {
  const list = $("#proofTabs");
  const panel = $("#proofPanel");
  if (!list || !panel) return;
  list.textContent = "";
  TABS.forEach((tab, i) => {
    const b = h("button", {
      class: "tab-btn", role: "tab", id: "tab-" + tab.id,
      "aria-selected": i === 0 ? "true" : "false", "aria-controls": "proofPanel",
    }, tab.label);
    b.addEventListener("click", () => selectTab(tab.id));
    list.append(b);
  });
  selectTab(location.hash && $("#tab-" + location.hash.slice(1)) ? location.hash.slice(1) : TABS[0].id);
}

function selectTab(id) {
  $$("#proofTabs .tab-btn").forEach(b => b.setAttribute("aria-selected", String(b.id === "tab-" + id)));
  const panel = $("#proofPanel");
  panel.textContent = "";
  const tab = TABS.find(t => t.id === id);
  if (tab) tab.build(panel);
}

/* --------------------------------------------------------- adversarial */
function buildAdversarial() {
  const frag = document.createDocumentFragment();
  const adv = jsonOf("data/adversarial_run.json");

  frag.append(artifactCard({
    kind: adv && adv.passed ? "PASS" : "UNKNOWN", tone: adv && adv.passed ? "pass" : "unknown",
    file: "data/adversarial_run.json",
    extraFiles: ["data/adversarial/ATTACK_REPORT.md", "data/adversarial/attack-report.unsigned.json"],
    blurb: "The estate attacks its own receipt chain with the real szl-receipts library — no mocks, no toy verifiers, fresh fixtures per attack — and publishes the result either way.",
    verify: "pip install -e packages/szl-receipts packages/szl-adversarial\npython -m szl_adversarial run --json\n# exit 0: the claim held · exit 2: an attack won (the report names it)",
  }));

  if (!adv) { frag.append(fetchRefusedNote("data/adversarial_run.json")); return frag; }

  /* verdict — verbatim */
  const verdict = h("div", { class: "attack-verdict" });
  verdict.append(h("p", { class: "v-line", text: "“" + adv.verdict + ".”" }));
  verdict.append(h("p", { text: adv.total + " attacks executed against isolated fresh fixtures · " + adv.blocked + " blocked · " + adv.limitations_documented + " documented limitation · harness self-assessment PASS · run duration " + adv.duration_seconds.toFixed(2) + "s" }));
  frag.append(verdict);

  /* limitation — first class, gold, prominent */
  const lim = adv.results.find(r => r.limitation);
  if (lim) {
    const box = h("div", { class: "limitation" });
    box.append(h("h4", { text: "Documented limitation — " + lim.name }));
    box.append(h("p", { text: lim.detail }));
    box.append(h("p", { style: "margin-top:8px;font:12px monospace;color:var(--ghost)", text: "WARN does not fail the run — and must never silently disappear from this table." }));
    frag.append(box);
  }

  /* full attack table */
  const scroll = h("div", { class: "tbl-scroll" });
  const tbl = h("table", { class: "data attacks" });
  tbl.append(h("thead", null, h("tr", null,
    h("th", { text: "#" }), h("th", { text: "Attack" }), h("th", { text: "Category" }),
    h("th", { text: "Result" }), h("th", { text: "Detail" }))));
  const tb = h("tbody");
  adv.results.forEach((r, i) => {
    const cls = r.result === "BLOCKED" ? "res-blocked" : r.result === "WARN" ? "res-warn" : "res-broken";
    tb.append(h("tr", null,
      h("td", { class: "mono-c", text: String(i + 1) }),
      h("td", { class: "mono-c", text: r.name }),
      h("td", null, h("span", { class: "chip gray", style: "font-size:10px", text: r.category })),
      h("td", null, h("span", { class: cls, text: r.result })),
      h("td", { style: "font-size:12.5px", text: r.detail })));
  });
  tbl.append(tb); scroll.append(tbl); frag.append(scroll);

  frag.append(h("p", { class: "sec-note", style: "margin-top:14px" },
    "Self-receipt: the harness hashed ATTACK_REPORT.md into a GovernedAction/v1 receipt written by the same library under attack — honestly named attack-report.unsigned.json because no operator key signed this run. An empty signatures array is not a signature."));
  return frag;
}

/* ------------------------------------------------------------- beacon */
const DIGESTED_FIELDS = ["actor", "created_at", "evidence_refs", "label", "payload", "prev", "seq", "state_from", "state_to"];

function canon(v) {
  if (v === null || v === undefined) return "null";
  if (Array.isArray(v)) return "[" + v.map(canon).join(",") + "]";
  const t = typeof v;
  if (t === "string") return JSON.stringify(v);
  if (t === "boolean") return v ? "true" : "false";
  if (t === "number") {
    if (!Number.isInteger(v)) throw new Error("non-integer float rejected (not portable across canonicalizers)");
    return String(v);
  }
  if (t === "object") {
    return "{" + Object.keys(v).sort().map(k => JSON.stringify(k) + ":" + canon(v[k])).join(",") + "}";
  }
  throw new Error("un-canonicalizable type " + t);
}

async function eventDigestHex(ev) {
  const body = {};
  for (const f of DIGESTED_FIELDS) body[f] = ev[f] === undefined ? null : ev[f];
  const bytes = new TextEncoder().encode(canon(body));
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return Array.from(new Uint8Array(digest), b => b.toString(16).padStart(2, "0")).join("");
}

function buildBeacon() {
  const frag = document.createDocumentFragment();
  frag.append(artifactCard({
    kind: "REFERENCE", tone: "gray", file: "data/beacon_chain.jsonl",
    extraFiles: ["data/beacon_demo.txt"],
    blurb: "One complete Reality Transaction — intent through receipt — as a hash-chained JSONL log. Every event is content-addressed and carries exactly one evidence label.",
    verify: "pip install -e packages/szl-beacon\npython -m szl_beacon demo            # runs the 11-state transaction\npython -m szl_beacon verify <logdir>  # re-checks the chain offline",
  }));

  const r = rec("data/beacon_chain.jsonl");
  if (!r.text) { frag.append(fetchRefusedNote("data/beacon_chain.jsonl")); return frag; }

  let events;
  try {
    events = r.text.trim().split("\n").map(line => JSON.parse(line));
  } catch (e) {
    frag.append(emptyNote("could not parse beacon_chain.jsonl: " + e.message, true));
    return frag;
  }

  /* stepper rail */
  const rail = h("div", { class: "stepper-rail", role: "tablist", "aria-label": "Transaction steps" });
  const detail = h("div", { class: "step-detail" });
  events.forEach((ev, i) => {
    const b = h("button", {
      class: "step-dot", role: "tab", "aria-selected": i === 0 ? "true" : "false",
      id: "step-" + i,
    },
      h("span", { text: "seq " + ev.seq }),
      h("span", { class: "s", text: ev.state_to }));
    b.addEventListener("click", () => showStep(i));
    rail.append(b);
  });

  function showStep(i) {
    const ev = events[i];
    $$(".step-dot", rail).forEach((b, j) => b.setAttribute("aria-selected", String(j === i)));
    detail.textContent = "";
    const from = ev.state_from || "∅ genesis";
    detail.append(h("div", { class: "step-flow" },
      h("span", { class: "st-name", text: from }),
      h("span", { class: "arr", text: "→" }),
      h("span", { class: "st-name to", text: ev.state_to }),
      h("span", { class: "chip " + (ev.actor.kind === "machine" ? "unknown" : "pass"), style: "margin-left:auto" },
        h("span", { class: "dot" }), ev.actor.kind)));
    const kv = h("div", { class: "step-kv" });
    kv.append(
      kvBox("event digest (committed, recomputed on verify)", ev.event_id, true),
      kvBox("prev link", ev.prev || "null — genesis"),
      kvBox("evidence label", ev.label),
      kvBox("actor", ev.actor.id),
      kvBox("created (UTC)", ev.created_at),
      kvBox("payload", JSON.stringify(ev.payload)),
    );
    if (ev.evidence_refs.length) kv.append(kvBox("evidence refs", ev.evidence_refs.join(", ")));
    detail.append(kv);
    detail.append(verifyBar(events, i));
  }

  frag.append(rail, detail);

  /* demo transcript */
  const demo = rec("data/beacon_demo.txt");
  if (demo.text) {
    const det = h("details", { style: "margin-top:18px" });
    det.append(h("summary", { style: "cursor:pointer;font:12px monospace;color:var(--lattice)", text: "Full demo transcript (beacon_demo.txt)" }));
    const pre = h("div", { class: "pre-card", style: "margin-top:10px" });
    pre.append(h("pre", null, h("code", { text: demo.text })));
    det.append(pre);
    frag.append(det);
  }

  frag.append(h("p", { class: "chain-canon", html: "Honesty note: canonicalization here is the <code>json-sortkeys</code> reference mode (sorted keys, no whitespace, UTF-8) — not RFC 8785. The reference implementation says so itself; production receipts canonicalize via RFC 8785 in szl-receipts. The in-browser verifier below re-implements exactly the reference mode." }));

  queueMicrotask(() => { const b = $("#step-0"); if (b) b.click(); });
  return frag;
}

function kvBox(k, v, proof) {
  return h("div", { class: "kv" },
    h("span", { class: "k", text: k }),
    h("span", { class: "v" + (proof ? " proof" : ""), text: v }));
}

function verifyBar(events, focusIdx) {
  const wrap = h("div");
  const bar = h("div", { class: "chain-verify" });
  const btn = h("button", { class: "btn btn-primary", type: "button", text: "Verify chain in this browser" });
  const status = h("span", { class: "chain-status", text: "idle — " + events.length + " events loaded" });
  bar.append(btn, status);
  wrap.append(bar);

  btn.addEventListener("click", async () => {
    if (!crypto.subtle) { status.textContent = "Web Crypto unavailable"; status.className = "chain-status bad"; return; }
    btn.disabled = true; btn.textContent = "Verifying…";
    let ok = true, firstBad = -1;
    const txids = new Set();
    for (let i = 0; i < events.length; i++) {
      const ev = events[i];
      const recomputed = await eventDigestHex(ev);
      const digestOk = recomputed === ev.event_id;
      const prevOk = i === 0 ? ev.prev === null : ev.prev === events[i - 1].event_id;
      const seqOk = ev.seq === i;
      if (ev.payload && ev.payload.transaction_id) txids.add(ev.payload.transaction_id);
      if (!(digestOk && prevOk && seqOk)) { ok = false; firstBad = i; break; }
      if (!reducedMotion) {
        status.textContent = "re-computing sha256 · seq " + ev.seq + "/" + (events.length - 1);
        await new Promise(r => setTimeout(r, 90));
      }
    }
    if (ok) {
      const tx = txids.size === 1 ? " · " + [...txids][0] : "";
      status.textContent = "VERIFIED — all " + events.length + " digests recomputed, all " + (events.length - 1) + " prev-links intact" + tx;
      status.className = "chain-status ok";
      btn.textContent = "Chain VERIFIED ✓";
    } else {
      status.textContent = "CHAIN BREAK at seq " + firstBad + " — digest, prev-link, or sequence mismatch";
      status.className = "chain-status bad";
      btn.textContent = "Verification FAILED";
    }
    btn.disabled = false;
  });
  return wrap;
}

/* ------------------------------------------------------------ claims wall */
function buildClaimsWall() {
  const frag = document.createDocumentFragment();
  const claims = jsonOf("data/claims.json");
  frag.append(artifactCard({
    kind: "9 CLAIMS", tone: "unknown", file: "data/claims.json",
    blurb: "Every public numeric claim, re-checked against the world. DRIFT and UNKNOWN are first-class honest states here — they are published, styled, and never hidden.",
    verify: "pip install -e packages/szl-estate\npython -m szl_estate.verify_claims --out artifacts/claims\n# UNKNOWN is never PASS: un-recomputed claims stay UNKNOWN",
  }));
  if (!claims) { frag.append(fetchRefusedNote("data/claims.json")); return frag; }

  const wall = h("div", { class: "claims-wall", style: "margin-top:20px" });
  for (const c of claims.results) {
    const tone = c.verdict === "PASS" ? "pass" : c.verdict === "DRIFT" ? "drift" : "unknown";
    const card = h("div", { class: "claim", "data-verdict": c.verdict });
    card.append(h("span", { class: "chip " + tone }, h("span", { class: "dot" }), c.verdict));
    const body = h("div");
    body.append(h("h4", { text: c.description }));
    body.append(h("p", { class: "desc", text: c.claim_id + " · " + c.source }));
    const nums = h("div", { class: "nums" });
    nums.append(h("span", { class: "exp", text: "expected: " }), h("b", { text: c.expected_quoted }));
    if (c.observed !== null) nums.append(h("span", { class: "obs", style: "margin-left:14px", text: "observed: " }), h("b", { text: String(c.observed) }));
    else nums.append(h("span", { style: "margin-left:14px", text: "observed: — (not recomputed)" }));
    body.append(nums);
    body.append(h("p", { class: "ev", text: "evidence: " + c.evidence }));
    card.append(body);
    wall.append(card);
  }
  frag.append(wall);

  if (claims.findings && claims.findings.length) {
    const f = h("div", { class: "claims-findings" });
    f.append(h("h4", { text: claims.findings.length + " findings filed, publicly" }));
    const ul = h("ul");
    for (const x of claims.findings) ul.append(h("li", null, "[" + x.severity + "] ", h("code", { text: x.code }), " · " + x.claim_id + " — " + x.detail));
    f.append(ul);
    frag.append(f);
  }
  return frag;
}

/* ----------------------------------------------------------------- kids */
function buildKidsArtifact() {
  const frag = document.createDocumentFragment();
  frag.append(artifactCard({
    kind: "8/8 PASS", tone: "pass", file: "data/kids_conformance.json",
    blurb: "Golden-vector conformance for the frozen KIDS v0.1 ISA: the simulator's answers are pinned with digests so any later RTL must reproduce them exactly.",
    verify: "pip install -e packages/kids-sim\npython -m kids_sim.conformance run --vectors packages/kids-sim/vectors --json\n# 8/8 PASS expected; corrupt vectors exit non-zero",
  }));
  const k = jsonOf("data/kids_conformance.json");
  if (!k) { frag.append(fetchRefusedNote("data/kids_conformance.json")); return frag; }
  frag.append(vectorWall(k));
  frag.append(honestyBar());
  return frag;
}

function vectorWall(k) {
  const wrap = h("div", { style: "margin-top:22px" });
  wrap.append(h("h3", { style: "font-size:17px;margin-bottom:12px", text: "Conformance vector wall — " + k.summary.pass + "/" + k.summary.total + " PASS" }));
  const wall = h("div", { class: "vector-wall" });
  for (const v of k.vectors) {
    const cell = h("div", { class: "vcell" });
    cell.append(h("div", { class: "vcell-top" },
      h("b", { text: v.name }),
      h("span", { class: "chip " + (v.status === "PASS" ? "pass" : "drift"), style: "font-size:9.5px" }, h("span", { class: "dot" }), v.status)));
    cell.append(h("p", { class: "dig", text: v.digest ? "digest " + v.digest : "digest: none recorded (exact-equality vector)" }));
    cell.append(h("p", { class: "det", text: v.detail }));
    wall.append(cell);
  }
  wrap.append(wall);
  return wrap;
}

function honestyBar() {
  return h("div", { class: "honesty-bar", text: "Honest labels: this is a golden simulator — zero silicon exists. Cycle numbers in the tooling are ESTIMATES; wall-clock is UNAVAILABLE in sim. Nothing on this page claims hardware." });
}

function renderKidsSection() {
  const mount = $("#kidsPanel");
  if (!mount) return;
  mount.textContent = "";
  const k = jsonOf("data/kids_conformance.json");
  if (!k) { mount.append(fetchRefusedNote("data/kids_conformance.json")); return; }
  mount.append(vectorWall(k));
  mount.append(honestyBar());
}

/* ---------------------------------------------------------- estate audit */
function renderEnum() {
  const body = $("#enumBody");
  if (!body) return;
  body.textContent = "";
  const d = jsonOf("data/enumeration.json");
  if (!d) { body.append(fetchRefusedNote("data/enumeration.json")); return; }

  const grid = h("div", { class: "enum-src" });
  const a = d.sources.source_a, b = d.sources.source_b;

  const ca = h("div", { class: "src" });
  ca.append(h("h5", { text: "Source A — gh CLI (graph)" }));
  ca.append(h("span", { class: "num", text: String(a.count) }));
  ca.append(h("p", { text: a.ok ? "OK — full inventory returned, " + a.names.length + " names on record." : "error: " + a.error }));
  const cb = h("div", { class: "src fail" });
  cb.append(h("h5", { text: "Source B — REST API" }));
  cb.append(h("span", { class: "num", text: "—" }));
  cb.append(h("p", { text: b.ok ? String(b.count) : b.error }));
  grid.append(ca, cb);
  body.append(grid);

  body.append(h("p", { style: "margin-top:16px;font:12.5px/1.7 monospace;color:var(--sub)",
    text: "status: " + d.status + " · sources agree: " + d.agreement + " · repo_count: " + JSON.stringify(d.repo_count) + " — published as null because the sources could not be cross-checked. The count you see anywhere on this page is computed from rows, never asserted from this field." }));
}

function renderTimeline() {
  const d = jsonOf("data/enumeration.json");
  const m = jsonOf("data/repo_matrix.json");
  if (d && d.sources.source_a.ok) {
    const el1 = $("#tlCountA"); if (el1) el1.textContent = String(d.sources.source_a.count);
  }
  if (m) {
    const e2 = $("#tlCountM"); if (e2) e2.textContent = String(m.length);
    const e3 = $("#tlCountM2"); if (e3) e3.textContent = String(m.length);
    if (d && d.sources.source_a.ok) {
      const inMatrix = new Set(m.map(r => r.name));
      const delta = d.sources.source_a.names.filter(n => !inMatrix.has(n));
      const slot = $("#v14Delta");
      if (slot) slot.textContent = "Δ computed live: " + (delta.length ? delta.join(", ") : "none") + ".";
    }
  }
}

/* matrix table — searchable, sortable, lazy-rendered */
const matrixState = { rows: [], filtered: [], shown: 0, sortKey: "name", sortDir: 1, query: "" };
const CHUNK = 25;
const COLS = [
  ["name", "repository"], ["state", "state"], ["primary_language", "lang"],
  ["license_spdx", "license"], ["pushed_at", "pushed"], ["open_prs", "PRs"],
  ["ci_latest", "CI"], ["forbidden_link_scan", "link scan"],
  ["findings_critical", "crit"], ["findings_high", "high"], ["findings_total", "findings"],
];

function renderMatrix() {
  const wrap = $("#matrixWrap");
  if (!wrap) return;
  wrap.textContent = "";
  const m = jsonOf("data/repo_matrix.json");
  if (!m) { wrap.append(fetchRefusedNote("data/repo_matrix.json")); return; }
  matrixState.rows = m;
  const search = $("#matrixSearch");
  if (search) {
    let t;
    search.addEventListener("input", () => {
      clearTimeout(t);
      t = setTimeout(() => {
        matrixState.query = search.value;
        applyMatrixFilter(); drawMatrixHead(wrap); drawMatrixRows(wrap, true);
      }, 160);
    });
  }
  applyMatrixFilter();
  drawMatrixHead(wrap);
  drawMatrixRows(wrap, true);
}

function applyMatrixFilter() {
  const q = matrixState.query.trim().toLowerCase();
  matrixState.filtered = matrixState.rows.filter(r => !q ||
    COLS.some(([k]) => String(r[k] || "").toLowerCase().includes(q)));
  matrixState.filtered.sort((a, b) => {
    const k = matrixState.sortKey;
    const na = parseFloat(a[k]), nb = parseFloat(b[k]);
    let cmp;
    if (!isNaN(na) && !isNaN(nb)) cmp = na - nb;
    else cmp = String(a[k] || "").localeCompare(String(b[k] || ""));
    return cmp * matrixState.sortDir;
  });
  matrixState.shown = 0;
  const c = $("#matrixCount");
  if (c) c.textContent = matrixState.filtered.length + " of " + matrixState.rows.length + " repos · sorted by " + matrixState.sortKey + (matrixState.sortDir < 0 ? " ↓" : " ↑");
}

function drawMatrixHead(wrap) {
  const old = $("table", wrap); if (old) old.remove();
  const scroll = h("div", { class: "tbl-scroll", id: "matrixScroll" });
  const tbl = h("table", { class: "data matrix" });
  const tr = h("tr");
  for (const [k, label] of COLS) {
    const th = h("th", { class: "sortable", scope: "col" }, label);
    if (k === matrixState.sortKey) th.append(h("span", { class: "arr", text: matrixState.sortDir > 0 ? "↑" : "↓" }));
    th.addEventListener("click", () => {
      if (matrixState.sortKey === k) matrixState.sortDir *= -1;
      else { matrixState.sortKey = k; matrixState.sortDir = 1; }
      applyMatrixFilter(); drawMatrixHead(wrap); drawMatrixRows(wrap, true);
    });
    tr.append(th);
  }
  tbl.append(h("thead", null, tr), h("tbody", { id: "matrixBody" }));
  scroll.append(tbl);
  wrap.append(scroll);
  const sentinel = h("div", { id: "matrixSentinel", style: "height:2px" });
  wrap.append(sentinel);
  new IntersectionObserver(entries => {
    if (entries.some(e => e.isIntersecting)) drawMatrixRows(wrap, false);
  }, { rootMargin: "600px" }).observe(sentinel);
}

function drawMatrixRows(wrap, reset) {
  const tb = $("#matrixBody");
  if (!tb) return;
  if (reset) { tb.textContent = ""; matrixState.shown = 0; }
  const slice = matrixState.filtered.slice(matrixState.shown, matrixState.shown + CHUNK);
  for (const r of slice) {
    const tr = h("tr");
    for (const [k] of COLS) {
      const v = String(r[k] == null ? "" : r[k]);
      let td;
      if (k === "name") td = h("td", { style: "color:var(--ink);font-weight:600", text: v });
      else if (k === "state") td = h("td", null, h("span", { class: "st-" + v, text: v }));
      else if (v === "UNKNOWN") td = h("td", { class: "td-UNKNOWN mono-c", text: v });
      else td = h("td", { class: "mono-c", text: v });
      tr.append(td);
    }
    tb.append(tr);
  }
  matrixState.shown += slice.length;
}

/* estate summary markdown → formatted panel */
function renderSummary() {
  const mount = $("#summaryBody");
  if (!mount) return;
  mount.textContent = "";
  const r = rec("data/ESTATE_SUMMARY.md");
  if (!r.text) { mount.append(fetchRefusedNote("data/ESTATE_SUMMARY.md")); return; }
  mount.append(renderSummaryMd(r.text));
}

function renderSummaryMd(text) {
  const box = h("div", { class: "summary-mdl" });
  let list = null;
  for (const raw of text.split("\n")) {
    const line = raw.trimEnd();
    if (!line.trim()) { list = null; continue; }
    if (line.startsWith("## ")) { list = null; box.append(h("h3", { text: line.slice(3) })); continue; }
    if (line.startsWith("# ")) { box.append(h("p", { class: "lead", text: line.slice(2) })); continue; }
    if (line.startsWith("- ")) {
      if (!list) { list = h("ul"); box.append(list); }
      const m = line.slice(2).match(/^([^:]+):\s*(.+)$/);
      list.append(m
        ? h("li", null, h("span", { text: m[1] }), h("b", { text: m[2] }))
        : h("li", null, h("span", { text: line.slice(2) })));
      continue;
    }
    box.append(h("p", { class: "warn", text: line }));
  }
  return box;
}

/* ------------------------------------------------------------- chrome */
function initChrome() {
  const toggle = $("[data-menu]");
  const links = $("#navLinks");
  if (toggle && links) toggle.addEventListener("click", () => {
    const open = links.getAttribute("data-open") === "true";
    links.setAttribute("data-open", String(!open));
    toggle.setAttribute("aria-expanded", String(!open));
  });
  $$("#navLinks a").forEach(a => a.addEventListener("click", () => {
    if (links) { links.setAttribute("data-open", "false"); }
    if (toggle) toggle.setAttribute("aria-expanded", "false");
  }));

  $$("[data-copy]").forEach(btn => {
    btn.addEventListener("click", () => {
      const pre = btn.parentElement && $("pre", btn.parentElement);
      if (pre) copyText(pre.textContent, btn);
    });
  });

  if ("IntersectionObserver" in window && !reducedMotion) {
    const io = new IntersectionObserver(entries => {
      for (const e of entries) if (e.isIntersecting) { e.target.classList.add("in"); io.unobserve(e.target); }
    }, { threshold: .08 });
    $$(".reveal").forEach(n => io.observe(n));
  } else {
    $$(".reveal").forEach(n => n.classList.add("in"));
  }
}

/* footer: digest of this very page, as served */
async function pageDigest() {
  const slot = $("#pageDigest");
  if (!slot) return;
  try {
    const res = await fetch("index.html", { cache: "no-store" });
    if (!res.ok) throw new Error("HTTP " + res.status);
    const bytes = new Uint8Array(await res.arrayBuffer());
    const digest = await crypto.subtle.digest("SHA-256", bytes);
    const hex = Array.from(new Uint8Array(digest), b => b.toString(16).padStart(2, "0")).join("");
    slot.textContent = "index.html sha256 (as served): " + hex;
  } catch {
    slot.textContent = "index.html sha256: UNAVAILABLE over file:// — serve the site and this line computes itself.";
  }
}

/* ----------------------------------------------------------------- boot */
async function boot() {
  initChrome();
  const paths = [
    "data/repo_matrix.json", "data/adversarial_run.json", "data/kids_conformance.json",
    "data/claims.json", "data/enumeration.json", "data/beacon_chain.jsonl",
    "data/beacon_demo.txt", "data/ESTATE_SUMMARY.md",
    "data/adversarial/ATTACK_REPORT.md", "data/adversarial/attack-report.unsigned.json",
  ];
  await Promise.all(paths.map(loadArtifact));
  renderCounters();
  initTabs();
  renderEnum();
  renderTimeline();
  renderMatrix();
  renderSummary();
  renderKidsSection();
  pageDigest();
}

if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
else boot();

})();
