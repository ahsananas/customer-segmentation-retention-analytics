// Builds the 8-slide case-study deck from reports/summary.json (run from the repo root):
//   node presentation/build_deck.js
// Requires: npm install pptxgenjs   (theme helper optional)
const pptxgen = require("pptxgenjs");
const fs = require("fs");
const path = require("path");
const ROOT = path.resolve(__dirname, "..");
const S = JSON.parse(fs.readFileSync(path.join(ROOT, "reports/summary.json")));
const V = fs.readFileSync(path.join(ROOT, "reports/validation_checks.csv"), "utf8").trim().split("\n").slice(1);
const DQ = Object.fromEntries(fs.readFileSync(path.join(ROOT, "reports/data_quality_log.csv"), "utf8").trim().split("\n").slice(1)
  .map(l => { const m = l.match(/^\d+,("?)(.*?)\1,(?:".*?"|[^,]*),(\d+),/); return m ? [m[2], +m[3]] : null; }).filter(Boolean));
const dqn = (...k) => String(k.reduce((a, x) => { if (!(x in DQ)) throw new Error("missing DQ row " + x); return a + DQ[x]; }, 0));
const vPass = V.filter(l => l.includes(",PASS,")).length, vAll = V.length;
const OUT = path.join(ROOT, "presentation/case_study.pptx");
let applyTheme = null;
// Optional: set PPTX_THEME_HELPER to a module exporting applyTheme(file, theme) to write the colour theme into the .pptx
try { if (process.env.PPTX_THEME_HELPER) ({ applyTheme } = require(process.env.PPTX_THEME_HELPER)); } catch (e) { /* optional */ }

const SEGS = S.segments.map(s => s.segment);
const SEGC = ["2A78D6", "EB6834", "1BAF7A", "EDA100", "E87BA4", "008300"];
const seg = n => S.segments.find(s => s.segment === n);
const C = { brand: "0F3B57", ink: "0F1B2A", ink2: "4B5563", muted: "7B8494", tint: "F1F3F6", line: "D7DBE1", white: "FFFFFF",
            syn: ["E8F1FB", "1C4F95"], asm: ["EFE9FB", "4B3A9A"], hyp: ["FFF4D6", "7A5200"], red: "D03B3B" };
const r1 = (n, d = 0) => Math.round(Number(n) * 10 ** d + 1e-9) / 10 ** d;   // round half up, consistently everywhere
const fmt = (n, d = 0) => r1(n, d).toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d });
const usd = n => n >= 1e6 ? `$${fmt(n / 1e6, 2)}m` : n >= 1e3 ? `$${fmt(n / 1e3, 0)}k` : `$${fmt(n, 0)}`;
const pct = (n, d = 0) => `${fmt(n, d)}%`;
const range = (a, d = 0) => `${fmt(Math.min(...a), d)}–${fmt(Math.max(...a), d)}%`;

const THEME = { name: "Portfolio", headFontFace: "Arial", bodyFontFace: "Calibri",
  colors: { dk1: "0F1B2A", lt1: "FFFFFF", dk2: "0F3B57", lt2: "F1F3F6", accent1: "2A78D6", accent2: "EB6834", accent3: "1BAF7A",
            accent4: "EDA100", accent5: "E87BA4", accent6: "008300", hlink: "2A78D6", folHlink: "4B3A9A" } };
const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; pres.theme = { headFontFace: "Arial", bodyFontFace: "Calibri" };
pres.author = "Ahsan Anas"; pres.title = "Customer Segmentation & Retention Analytics – case study (synthetic data)";
const SC = pres.SchemeColor;

pres.defineSlideMaster({ title: "COVER", background: { color: C.brand }, objects: [
  { placeholder: { options: { name: "title", type: "title", x: 0.7, y: 2.1, w: 11.9, h: 1.7, fontSize: 40, bold: true, color: SC.background1, align: "left", valign: "bottom", margin: 0 }, text: "" } }] });
pres.defineSlideMaster({ title: "CONTENT", background: { color: "FFFFFF" }, objects: [
  { placeholder: { options: { name: "kicker", type: "body", x: 0.6, y: 0.32, w: 9, h: 0.28, fontSize: 11, bold: true, color: SC.accent1, margin: 0, charSpacing: 1 }, text: "" } },
  { placeholder: { options: { name: "title", type: "title", x: 0.6, y: 0.62, w: 12.1, h: 0.85, fontSize: 26, bold: true, color: SC.text2, align: "left", valign: "top", margin: 0 }, text: "" } },
  { text: { text: "Customer Segmentation & Retention Analytics · Ahsan Anas · SYNTHETIC DATA – fictional customers and results", options: { x: 0.6, y: 7.05, w: 10, h: 0.25, fontSize: 9, color: "7B8494", margin: 0 } } }],
  slideNumber: { x: 12.3, y: 7.05, w: 0.5, h: 0.25, fontSize: 9, color: "7B8494", align: "right" } });

const T = (s, text, o) => s.addText(text, { isTextBox: true, margin: 0, fontFace: "Calibri", color: C.ink, fontSize: 14, valign: "top", ...o });
const box = (s, x, y, w, h, fill = C.tint) => s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, fill: { color: fill }, line: { color: fill }, rectRadius: 0.08 });
function tag(s, kind, x, y) {
  const t = { syn: "SYNTHETIC OBSERVATION", asm: "MODEL ASSUMPTION", hyp: "HYPOTHETICAL" }[kind]; const [bg, fg] = C[kind]; const w = 0.2 + t.length * 0.072;
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h: 0.26, fill: { color: bg }, line: { color: bg }, rectRadius: 0.12 });
  T(s, t, { x, y, w, h: 0.26, fontSize: 8.5, bold: true, color: fg, align: "center", valign: "middle", charSpacing: 0.5 });
  return w;
}
function slide(kicker, title) { const s = pres.addSlide({ masterName: "CONTENT" }); s.addText(kicker.toUpperCase(), { placeholder: "kicker" }); s.addText(title, { placeholder: "title" }); return s; }
const dot = (s, x, y, c, d = 0.16) => s.addShape(pres.shapes.OVAL, { x, y, w: d, h: d, fill: { color: c }, line: { color: c } });
const chartBase = { catAxisLabelColor: "4B5563", valAxisLabelColor: "7B8494", catAxisLabelFontFace: "+mn-lt", valAxisLabelFontFace: "+mn-lt", dataLabelFontFace: "+mn-lt",
  legendFontFace: "+mn-lt", titleFontFace: "+mn-lt", catAxisLabelFontSize: 11, valAxisLabelFontSize: 10, dataLabelFontSize: 10.5, dataLabelColor: "0F1B2A",
  valGridLine: { color: "E5E7EB", size: 0.5 }, catGridLine: { style: "none" }, catAxisLineColor: "C7CCD4", valAxisLineShow: false, showTitle: true, titleFontSize: 12.5, titleColor: "0F1B2A" };

// ------------------------------------------------ 1 COVER
{
  const s = pres.addSlide({ masterName: "COVER" });
  T(s, "PORTFOLIO CASE STUDY · FINANCIAL SERVICES", { x: 0.7, y: 1.55, w: 10, h: 0.35, fontSize: 13, bold: true, color: "9EC5F4", charSpacing: 2 });
  s.addText("Customer Segmentation & Retention Analytics", { placeholder: "title" });
  T(s, `Segmenting ${fmt(S.customers)} fictional retail-banking customers by relationship value and engagement, and finding the early signs that they are about to leave`,
    { x: 0.7, y: 4.0, w: 10.8, h: 0.9, fontSize: 18, color: "DCE7F3" });
  SEGC.forEach((c, i) => dot(s, 0.7 + i * 0.42, 5.25, c, 0.26));
  T(s, "Ahsan Anas · October 2026", { x: 0.7, y: 6.05, w: 6, h: 0.35, fontSize: 14, bold: true, color: "FFFFFF" });
  T(s, "All customers, data and results are synthetic. Built with AI assistance (Claude) under the author's direction – see README.", { x: 0.7, y: 6.45, w: 11.5, h: 0.35, fontSize: 11.5, color: "9EB4C8" });
  s.addNotes("Portfolio case study. The dataset is generated from a seeded simulation – no real customer data is used anywhere.");
}

// ------------------------------------------------ 2 PROBLEM & APPROACH
{
  const s = slide("The business problem", "Which customers create value, which are drifting away, and what should we do about it?");
  T(s, [{ text: "A retail bank's customer book is rarely one market. ", options: { bold: true } },
        { text: "High-value customers can be quietly disengaging, while highly engaged customers may hold only one product. Treating them all the same wastes retention budget and misses growth." }],
    { x: 0.6, y: 1.75, w: 5.6, h: 1.4, fontSize: 15, color: C.ink });
  T(s, "Questions this project answers", { x: 0.6, y: 3.3, w: 5.6, h: 0.35, fontSize: 14, bold: true, color: C.brand });
  T(s, ["Who are our customer segments, and how much value does each hold?", "Which behaviours separate engaged from drifting customers?",
        "Which warning signals predict attrition – and how much revenue is at risk?", "Which interventions are worth testing, and how would we test them?"]
    .map((t, i, a) => ({ text: t, options: { bullet: true, breakLine: i < a.length - 1 } })), { x: 0.6, y: 3.7, w: 5.6, h: 2.0, fontSize: 13.5, paraSpaceAfter: 6 });
  const steps = [["1", "Generate", `Seeded simulation of ${fmt(S.customers)} fictional customers with linked behaviours, plus realistic data errors`],
                 ["2", "Clean & validate", `${S.dq_steps} logged checks; nothing imputed; ${vPass}/${vAll} automated checks pass`],
                 ["3", "Segment", "Revenue proxy × Relationship Engagement Index → six actionable segments, stress-tested"],
                 ["4", "Retain & grow", "Warning signals, an attrition model, sized hypothetical interventions and a pilot design"]];
  steps.forEach(([n, h, b], i) => {
    const y = 1.75 + i * 1.18; box(s, 6.8, y, 5.9, 1.02);
    s.addShape(pres.shapes.OVAL, { x: 7.0, y: y + 0.22, w: 0.58, h: 0.58, fill: { color: C.brand }, line: { color: C.brand } });
    T(s, n, { x: 7.0, y: y + 0.22, w: 0.58, h: 0.58, fontSize: 16, bold: true, color: "FFFFFF", align: "center", valign: "middle" });
    T(s, [{ text: h, options: { bold: true, breakLine: true, color: C.ink } }, { text: b, options: { color: C.ink2 } }], { x: 7.8, y: y + 0.12, w: 4.75, h: 0.85, fontSize: 13, valign: "middle" });
  });
  T(s, "Labels used throughout:", { x: 0.6, y: 6.25, w: 2.2, h: 0.3, fontSize: 11.5, bold: true, color: C.ink2, valign: "middle" });
  let x = 2.75; ["syn", "asm", "hyp"].forEach(k => { x += tag(s, k, x, 6.27) + 0.15; });
  s.addNotes("Synthetic observation = what the fictional data shows. Model assumption = a modelling choice that could reasonably differ. Hypothetical = an intervention scenario, not a result.");
}

// ------------------------------------------------ 3 DATA & CLEANING
{
  const s = slide("Dataset and data cleaning", `${fmt(S.rows_raw)} raw rows became ${fmt(S.customers)} clean customer records – and no value was invented`);
  const stats = [[fmt(S.customers), "fictional customers, 39 fields: demographics, balances, products, transactions, digital, service"],
                 [String(S.dq_steps), `logged cleaning checks catching every injected issue type (${fmt(S.injected_issues)} injected problems)`],
                 ["0", "values imputed – blanks stay blank and scores use only the fields available"],
                 [`${vPass}/${vAll}`, "automated validation checks pass (reproducibility, integrity, calculations, Excel = Python)"]];
  stats.forEach(([b, l], i) => {
    const y = 1.75 + i * 1.22;
    T(s, b, { x: 0.6, y, w: 2.0, h: 0.6, fontSize: 30, bold: true, color: C.brand, fontFace: "Arial", valign: "middle" });
    T(s, l, { x: 2.65, y: y + 0.02, w: 3.3, h: 0.95, fontSize: 12.5, color: C.ink2 });
  });
  const rows = [["Issue found", "Rows", "Action"],
    ["Exact duplicates + re-ingested older snapshots", dqn("Exact duplicate rows", "Re-ingested older snapshots"), "Removed duplicates; kept each customer's newest record"],
    ["Region / employment coding variants", dqn("Region coding variants", "Employment text case / whitespace"), "Standardised ('METRO', 'Metropolitan' → Metro)"],
    ["Mixed date formats (DD/MM/YYYY vs ISO)", dqn("Mixed date formats (last_login_date)"), "Parsed each format explicitly – no guessing"],
    ["Income recorded in thousands (e.g. 54.3)", dqn("Income recorded in thousands"), "×1,000 unit fix, flagged"],
    ["Impossible ages, sentinel tenure (−1), future dates", dqn("Impossible age", "Sentinel tenure", "Transaction dated after the snapshot"), "Set to missing and flagged"],
    ["Missing income · card limit", dqn("Income missing", "Card holder without a limit"), "Left missing – not imputed"],
    ["Negative savings, stale product counts, 900% card use", dqn("Negative savings balance", "Stale product count", "Impossible card utilisation"), "0 if no product else missing; recount from flags; set missing"]];
  s.addTable(rows.map((r, i) => r.map((c, j) => ({ text: c, options: { bold: i === 0, color: i === 0 ? "FFFFFF" : C.ink, fill: { color: i === 0 ? C.brand : (i % 2 ? "FFFFFF" : C.tint) },
    fontSize: i === 0 ? 12 : 11.5, align: j === 1 ? "center" : "left", valign: "middle" } }))),
    { x: 6.3, y: 1.75, w: 6.4, colW: [2.75, 0.6, 3.05], rowH: 0.5, border: { type: "solid", pt: 0.5, color: C.line }, fontFace: "Calibri", margin: [3, 6, 3, 6] });
  T(s, "Every rule is in reports/data_quality_log.csv and is checked against the generator's list of injected issues.", { x: 6.3, y: 6.15, w: 6.4, h: 0.5, fontSize: 11, italic: true, color: C.muted });
  s.addNotes("The generator records every injected problem in a manifest, so cleaning can be tested against ground truth. The income check finds 36 of 38 injected unit errors because two of those rows were later blanked by the missing-income injection.");
}

// ------------------------------------------------ 4 MODEL
{
  const s = slide("Segmentation model", "Two axes – what a customer is worth and how engaged they are – give six segments with a clear action each");
  tag(s, "asm", 0.6, 1.62);
  T(s, [{ text: "Value axis: estimated annual revenue", options: { bold: true, color: C.brand, breakLine: true } },
        { text: "Balances × illustrative margins (current account 2.5%, savings 1.2%, mortgage 1.1%, loans 4.5%, investments 0.75% fee) + card interchange. Bands: High ≥ $1,500 · Mid ≥ $400." }],
    { x: 0.6, y: 2.0, w: 5.5, h: 1.25, fontSize: 12.5, color: C.ink });
  T(s, [{ text: "Engagement axis: Relationship Engagement Index (0–100)", options: { bold: true, color: C.brand, breakLine: true } },
        { text: "Recency 30 (halves every 30 days) · frequency 20 · digital 15 · product adoption 20 · loyalty 15. Bands: High ≥ 70 · Mid ≥ 50." }],
    { x: 0.6, y: 3.3, w: 5.5, h: 1.0, fontSize: 12.5, color: C.ink });
  const sw = S.sensitivity.filter(x => x.test === "REI weights").map(x => x.same_segment_pct);
  const vb = S.sensitivity.filter(x => x.scenario.startsWith("Value")).map(x => x.same_segment_pct);
  const eb = S.sensitivity.filter(x => x.scenario.startsWith("Engagement")).map(x => x.same_segment_pct);
  const sil = Object.values(S.kmeans.silhouette_by_k);
  T(s, [{ text: "Stress-tested", options: { bold: true, color: C.brand, breakLine: true } },
        { text: `Five alternative weightings keep ${range(sw)} of customers in the same segment; value cut-offs ±20%: ${range(vb)}; engagement cut-offs ±5 points: ${range(eb)} – the engagement cut-off is the most sensitive choice. ` },
        { text: `k-means finds little natural structure (silhouette ${fmt(Math.min(...sil), 2)}–${fmt(Math.max(...sil), 2)}; agreement ARI ${fmt(S.kmeans.ari_rule_vs_kmeans6, 2)}), so transparent rules were kept: each segment maps to an action.` }],
    { x: 0.6, y: 4.4, w: 5.5, h: 2.3, fontSize: 12.5, color: C.ink });
  // 3x3 grid
  const gx = 7.35, gy = 1.95, cw = 1.75, ch = 1.38;
  const cell = { "High|Low": "Affluent Drifters", "High|Mid": "Established Core", "High|High": "Premier Advocates",
                 "Mid|Low": "Light Touch", "Mid|Mid": "Established Core", "Mid|High": "Engaged Builders",
                 "Low|Low": "Dormant & Low Value", "Low|Mid": "Light Touch", "Low|High": "Engaged Builders" };
  ["High", "Mid", "Low"].forEach((v, r) => ["Low", "Mid", "High"].forEach((e, c) => {
    const nm = cell[`${v}|${e}`], col = SEGC[SEGS.indexOf(nm)];
    s.addShape(pres.shapes.RECTANGLE, { x: gx + c * cw, y: gy + r * ch, w: cw - 0.06, h: ch - 0.06, fill: { color: col, transparency: 12 }, line: { color: "FFFFFF", width: 0 } });
    T(s, nm, { x: gx + c * cw + 0.08, y: gy + r * ch + 0.08, w: cw - 0.22, h: ch - 0.22, fontSize: 12.5, bold: true, color: "FFFFFF", align: "center", valign: "middle" });
  }));
  ["High value", "Mid value", "Low value"].forEach((t, r) => T(s, t, { x: 6.0, y: gy + r * ch + 0.45, w: 1.25, h: 0.45, fontSize: 11.5, bold: true, color: C.ink2, align: "right", valign: "middle" }));
  ["Low engagement", "Mid", "High engagement"].forEach((t, c) => T(s, t, { x: gx + c * cw, y: gy + 3 * ch + 0.02, w: cw - 0.06, h: 0.3, fontSize: 11.5, bold: true, color: C.ink2, align: "center" }));
  T(s, "Rule table in src/config.py; rebuilt with live formulas in the Excel workings.", { x: 7.35, y: 6.55, w: 5.3, h: 0.3, fontSize: 10.5, italic: true, color: C.muted });
  s.addNotes("Fixed cut-offs (not percentiles) mean a customer only changes segment when their own behaviour changes. Bands sit near the 70th and 30th percentile of this synthetic book.");
}

// ------------------------------------------------ 5 FINDINGS
{
  const s = slide("Key findings", "Value is concentrated, and the costliest risk sits with wealthy customers who have gone quiet");
  tag(s, "syn", 0.6, 1.62);
  s.addChart(pres.charts.BAR, [{ name: "% of customers", labels: SEGS, values: S.segments.map(x => r1(x.customer_share_pct, 1)) },
                               { name: "% of est. revenue", labels: SEGS, values: S.segments.map(x => r1(x.revenue_share_pct, 1)) }],
    { x: 0.5, y: 2.0, w: 6.6, h: 4.8, barDir: "bar", barGrouping: "clustered", catAxisOrientation: "maxMin", chartColors: ["C7CCD4", "0F3B57"],
      barGapWidthPct: 45, showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: '0.0"%"', valAxisHidden: true, valAxisMaxVal: 50,
      showLegend: true, legendPos: "b", legendFontSize: 11, title: "Share of customers vs share of estimated revenue", ...chartBase, valGridLine: { style: "none" } });
  const pa = seg("Premier Advocates"), ad = seg("Affluent Drifters"), lt = seg("Light Touch"), dm = seg("Dormant & Low Value"), eb = seg("Engaged Builders");
  const cards = [
    [SEGC[0], "Premier Advocates", `${pct(pa.customer_share_pct)} of customers hold ${pct(pa.revenue_share_pct)} of revenue; attrition only ${pct(pa.attrition_pct, 1)}. Protect and reward.`],
    [SEGC[2], "Affluent Drifters", `${pct(ad.customer_share_pct, 1)} of customers, ${pct(ad.revenue_share_pct)} of revenue – median ${fmt(ad.median_days_since_txn)} days since a transaction and ${pct(ad.attrition_pct)} attrition.`],
    [SEGC[3], "Engaged Builders", `Most engaged (REI ${fmt(eb.avg_rei)}; ${pct(eb.main_bank_pct)} main bank) but median revenue only ${usd(eb.median_revenue)} – the cross-sell pool.`],
    [SEGC[4], "Light Touch + Dormant", `${pct(lt.customer_share_pct + dm.customer_share_pct)} of customers but ${pct(lt.revenue_share_pct + dm.revenue_share_pct)} of revenue – low-cost digital servicing.`],
  ];
  cards.forEach(([c, h, b], i) => {
    const y = 1.62 + i * 1.3; box(s, 7.4, y, 5.3, 1.15); dot(s, 7.58, y + 0.2, c, 0.2);
    T(s, [{ text: h, options: { bold: true, breakLine: true } }, { text: b, options: { color: C.ink2 } }], { x: 7.92, y: y + 0.1, w: 4.65, h: 1.0, fontSize: 12.5 });
  });
  s.addNotes("All findings describe the synthetic book. Revenue is a proxy built from illustrative margin assumptions.");
}

// ------------------------------------------------ 6 RETENTION
{
  const s = slide("Retention warning signals", `${S.risk_bands.High} customers flagged as high risk; ${usd(S.revenue_at_risk_total)} of annual revenue is at risk (expected)`);
  tag(s, "syn", 0.6, 1.62);
  const sig = S.signals.slice().sort((a, b) => b.lift_vs_book - a.lift_vs_book);
  s.addChart(pres.charts.BAR, [{ name: "Lift vs book attrition rate", labels: sig.map(x => x.signal), values: sig.map(x => x.lift_vs_book) }],
    { x: 0.5, y: 1.95, w: 6.6, h: 4.3, barDir: "bar", catAxisOrientation: "maxMin", chartColors: ["0F3B57"], barGapWidthPct: 40,
      showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: '0.0"×"', valAxisHidden: true, valAxisMaxVal: 3.6, showLegend: false,
      title: `Attrition when the signal is present ÷ book rate (${S.model.base_rate_pct}%)`, ...chartBase, valGridLine: { style: "none" } });
  T(s, "High card utilisation flags only 5 customers and adds no risk here – not every intuitive signal earns its place.", { x: 0.6, y: 6.3, w: 6.4, h: 0.5, fontSize: 11, italic: true, color: C.muted });
  tag(s, "asm", 7.4, 1.62);
  const ad = seg("Affluent Drifters"), ec = seg("Established Core");
  const st = [[fmt(S.model.auc_test, 2), "test AUC – logistic regression on 9 engagement and value features, 30% held-out test set"],
              [`${fmt(S.model.top_decile_lift, 1)}×`, "attrition rate in the top 10% of risk scores vs the average"],
              [pct(ad.revenue_at_risk / S.revenue_at_risk_total * 100), `of revenue at risk sits with Affluent Drifters (${usd(ad.revenue_at_risk)}), ${pct(ec.revenue_at_risk / S.revenue_at_risk_total * 100)} with Established Core`]];
  st.forEach(([b, l], i) => {
    const y = 2.0 + i * 1.2;
    T(s, b, { x: 7.4, y, w: 1.7, h: 0.7, fontSize: 30, bold: true, color: C.brand, fontFace: "Arial", valign: "middle" });
    T(s, l, { x: 9.15, y: y + 0.05, w: 3.55, h: 1.0, fontSize: 12.5, color: C.ink2 });
  });
  box(s, 7.4, 5.65, 5.3, 1.15, "FBEDED");
  T(s, [{ text: "Read with care: ", options: { bold: true, color: C.red } },
        { text: "the outcome was simulated from the same hidden traits as the features, so this proves the method, not real-world accuracy." }],
    { x: 7.6, y: 5.75, w: 4.95, h: 0.95, fontSize: 12, color: C.ink, valign: "middle" });
  s.addNotes(`Strongest coefficients: frequency, product adoption, main-bank status and deposit trend (protective); complaints (risk). ${S.model.not_scored_missing_input} customers with a missing input are not scored rather than imputed.`);
}

// ------------------------------------------------ 7 OPPORTUNITIES
{
  const s = slide("Retention and growth opportunities", "Three interventions worth testing – sized on stated assumptions, then proven with a holdout pilot");
  tag(s, "hyp", 0.6, 1.62);
  S.scenarios.forEach((c, i) => {
    const x = 0.6 + i * 4.1, col = SEGC[SEGS.indexOf(c.segment)];
    box(s, x, 2.0, 3.9, 2.85); dot(s, x + 0.22, 2.22, col, 0.2);
    T(s, c.segment, { x: x + 0.52, y: 2.14, w: 3.2, h: 0.35, fontSize: 14, bold: true });
    T(s, c.intervention, { x: x + 0.22, y: 2.55, w: 3.5, h: 0.6, fontSize: 12, color: C.ink2 });
    T(s, c.metric.includes("USD") ? usd(c.value) : `≈${fmt(c.value)}`, { x: x + 0.22, y: 3.15, w: 3.5, h: 0.6, fontSize: 28, bold: true, color: C.brand, fontFace: "Arial" });
    T(s, c.metric, { x: x + 0.22, y: 3.75, w: 3.5, h: 0.3, fontSize: 11.5, color: C.ink2 });
    T(s, [{ text: "Assumption: ", options: { bold: true } }, { text: c.assumption }], { x: x + 0.22, y: 4.08, w: 3.5, h: 0.72, fontSize: 10.5, color: C.ink2 });
  });
  T(s, "Proposed pilot: random 50/50 treatment vs holdout", { x: 0.6, y: 5.05, w: 8, h: 0.35, fontSize: 14, bold: true, color: C.brand });
  const rows = [["Cell", "Treatment / holdout", "Baseline", "Smallest detectable change*"]].concat(S.pilot.map(p => [p.cell, `${p.treatment} / ${p.holdout}`, pct(p.baseline_rate_pct, 1), `±${fmt(p.min_detectable_change_pts, 1)} pts`]));
  s.addTable(rows.map((r, i) => r.map((c, j) => ({ text: c, options: { bold: i === 0, color: i === 0 ? "FFFFFF" : C.ink, fill: { color: i === 0 ? C.brand : (i % 2 ? "FFFFFF" : C.tint) },
    fontSize: 11.5, align: j === 0 ? "left" : "center", valign: "middle" } }))),
    { x: 0.6, y: 5.45, w: 8.3, colW: [3.5, 1.7, 1.2, 1.9], rowH: 0.32, border: { type: "solid", pt: 0.5, color: C.line }, fontFace: "Calibri", margin: [2, 6, 2, 6] });
  T(s, "* 95% confidence, 80% power; indicative. The Affluent Drifters cell is small, so only a large effect would show – pool cells or run longer.",
    { x: 9.2, y: 5.45, w: 3.5, h: 1.3, fontSize: 11, italic: true, color: C.muted });
  s.addNotes("Every number on this slide follows directly from its assumption. The pilot turns assumptions into measured effects before any budget is scaled.");
}

// ------------------------------------------------ 8 LIMITATIONS & NEXT STEPS
{
  const s = slide("Limitations and recommendations", "A reusable framework – to be validated on real, governed data before any decision");
  T(s, "Limitations", { x: 0.6, y: 1.7, w: 4, h: 0.35, fontSize: 15, bold: true, color: C.brand });
  T(s, ["Synthetic data: relationships exist because the generator created them", "Revenue proxy relies on illustrative margins, not real pricing",
        "Segment cut-offs are judgement calls (tested, but still choices)", "Attrition model is associative, not causal; untested on real customers",
        "Scenario values are assumption-driven, not forecasts"].map((t, i, a) => ({ text: t, options: { bullet: true, breakLine: i < a.length - 1 } })),
    { x: 0.6, y: 2.1, w: 4.0, h: 3.0, fontSize: 12.5, color: C.ink, paraSpaceAfter: 6 });
  T(s, "Recommendations", { x: 4.85, y: 1.7, w: 4, h: 0.35, fontSize: 15, bold: true, color: C.brand });
  T(s, ["Re-run the pipeline on governed real data; recalibrate margins with Finance", "Prioritise Affluent Drifters for relationship-manager outreach – via a holdout pilot",
        "Use Engaged Builders as the cross-sell test pool", "Monitor the four strongest warning signals monthly; re-fit the model on observed outcomes",
        "Add fairness and privacy review before any model drives customer treatment"].map((t, i, a) => ({ text: t, options: { bullet: true, breakLine: i < a.length - 1 } })),
    { x: 4.85, y: 2.1, w: 4.0, h: 3.4, fontSize: 12.5, color: C.ink, paraSpaceAfter: 6 });
  const img = path.join(ROOT, "assets/dashboard_page1.png");
  if (fs.existsSync(img)) {
    s.addImage({ path: img, altText: "Screenshot of the interactive dashboard: segment map, KPI tiles and segment profile tables (synthetic data)", x: 9.15, y: 1.75, w: 3.55, h: 3.55 * 2964 / 2768, sizing: { type: "contain", w: 3.55, h: 3.55 * 2964 / 2768 } });
  }
  T(s, "Interactive dashboard: dashboard/index.html (filters by region, age, main bank and segment)", { x: 9.15, y: 5.65, w: 3.55, h: 0.6, fontSize: 10.5, italic: true, color: C.muted });
  box(s, 0.6, 5.85, 8.3, 0.95, C.tint);
  T(s, [{ text: "About this project: ", options: { bold: true } },
        { text: "designed and directed by Ahsan Anas; code, synthetic data and documents generated with AI assistance (Claude) and reviewed by the author. Reproduce everything with python -m src.run_all." }],
    { x: 0.8, y: 5.92, w: 7.9, h: 0.82, fontSize: 11.5, color: C.ink2, valign: "middle" });
  s.addNotes("Limitations are stated up front so the framework is credible: it demonstrates method on synthetic data.");
}

(async () => {
  await pres.writeFile({ fileName: OUT });
  if (applyTheme) await applyTheme(OUT, THEME);
  console.log("wrote", OUT);
})();
