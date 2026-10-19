"""Build the self-contained interactive dashboard (dashboard/index.html) and export it to PDF.

Run:  python -m src.build_dashboard        (PDF export needs:  pip install playwright && playwright install chromium)
"""
import json, sys
import numpy as np
import pandas as pd
from .config import SCORED, REPORTS, ROOT, SEGMENTS

SHORT_ACTION = {
    "Exact duplicate rows": "Removed", "Re-ingested older snapshots": "Kept newest snapshot",
    "Region coding variants": "Standardised", "Employment text case / whitespace": "Trimmed, re-cased",
    "Mixed date formats (last_login_date)": "Parsed each format", "Transaction dated after the snapshot": "Set unknown, flagged",
    "Impossible age": "Set missing", "Sentinel tenure": "Set missing", "Income recorded in thousands": "×1,000 unit fix",
    "Income missing": "Left missing (not imputed)", "Impossible card utilisation": "Set missing",
    "Card holder without a limit": "Left missing, flagged", "Stale product count": "Recalculated from flags",
    "Negative savings balance": "0 if no product, else missing",
}


def build(out_html=ROOT / "dashboard" / "index.html"):
    d = pd.read_csv(SCORED)
    S = json.load(open(REPORTS / "summary.json"))
    dq = pd.read_csv(REPORTS / "data_quality_log.csv")
    dq = dq[dq.check != "Row count reconciliation"]
    ab = pd.cut(d.age, [17, 29, 44, 59, 200], labels=["18–29", "30–44", "45–59", "60+"]).astype(str).replace("nan", "Unknown")
    nn = lambda v, k=2: None if pd.isna(v) else round(float(v), k)
    rows = [{"id": r.customer_id, "seg": r.segment, "reg": r.region, "ab": a, "mb": r.main_bank_flag,
             "rev": nn(r.est_annual_revenue, 0), "rei": nn(r.rei, 1), "rr": nn(r.rei_recency, 1), "rf": nn(r.rei_frequency, 1),
             "rd": nn(r.rei_digital, 1), "ra": nn(r.rei_adoption, 1), "rl": nn(r.rei_loyalty, 1),
             "dt": None if pd.isna(r.days_since_txn) else int(r.days_since_txn), "np": int(r.num_products), "att": int(r.attrited_next_6m),
             "p": nn(r.attrition_risk_model, 3), "rar": nn(r.expected_revenue_at_risk, 0),
             "sav": int(r.has_savings), "td": int(r.has_term_deposit), "cc": int(r.has_credit_card), "pl": int(r.has_personal_loan),
             "mo": int(r.has_mortgage), "inv": int(r.has_investments), "ins": int(r.has_insurance)}
            for r, a in zip(d.itertuples(), ab)]
    sil = S["kmeans"]["silhouette_by_k"].values()
    data = {"segments": SEGMENTS, "rows": rows, "signals": S["signals"], "deciles": S["deciles"], "scenarios": S["scenarios"],
            "pilot": S["pilot"], "sensitivity": S["sensitivity"],
            "kmeans": {"sil_range": f"{min(sil):.2f}–{max(sil):.2f}", "ari": f"{S['kmeans']['ari_rule_vs_kmeans6']:.2f}"},
            "dq": [{"check": x.check, "rows_affected": int(x.rows_affected), "action": SHORT_ACTION.get(x.check, x.action)} for x in dq.itertuples()],
            "totals": {"revenue": S["total_revenue"], "rows_raw": S["rows_raw"], "customers": S["customers"]}}
    t = open(ROOT / "src" / "dashboard_template.html").read()
    t = (t.replace("__N__", f"{S['customers']:,}").replace("__SNAP__", pd.Timestamp(S["snapshot_date"]).strftime("%d %b %Y"))
         .replace("__BASE__", f"{S['model']['base_rate_pct']}").replace("__AUC__", f"{S['model']['auc_test']:.2f}")
         .replace("__LIFT__", f"{S['model']['top_decile_lift']:.1f}").replace("__DATA__", json.dumps(data, separators=(",", ":"))))
    assert "__" not in t.replace("__proto__", ""), "unfilled placeholder"
    out_html.parent.mkdir(exist_ok=True)
    open(out_html, "w").write(t)
    return out_html


def export_pdf(html, pdf, png_dir=None):
    import asyncio
    from playwright.async_api import async_playwright
    from pypdf import PdfWriter, PdfReader

    async def run():
        async with async_playwright() as p:
            b = await p.chromium.launch(); pg = await b.new_page(viewport={"width": 1440, "height": 1000}, device_scale_factor=2)
            errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
            await pg.goto(html.resolve().as_uri()); await pg.wait_for_timeout(600)
            assert not errs, errs
            hs = []
            for i in (1, 2):
                box = await pg.locator(f"#p{i}").bounding_box(); hs.append(box["height"])
                if png_dir:
                    await pg.locator(f"#p{i}").screenshot(path=str(png_dir / f"dashboard_page{i}.png"))
            await pg.emulate_media(media="print"); parts = []
            for i in (1, 2):
                await pg.evaluate(f"document.getElementById('p{3-i}').style.display='none';document.getElementById('p{i}').style.display='block'")
                f = pdf.parent / f"_part{i}.pdf"
                await pg.pdf(path=str(f), width="1440px", height=f"{int(hs[i-1]) + 40}px", print_background=True,
                             margin={"top": "20px", "bottom": "0", "left": "0", "right": "0"})
                parts.append(f)
            w = PdfWriter()
            for f in parts:
                for x in PdfReader(str(f)).pages: w.add_page(x)
                f.unlink()
            w.add_metadata({"/Title": "Customer Segmentation & Retention Analytics – Dashboard (synthetic data)", "/Author": "Ahsan Anas"})
            w.write(str(pdf)); await b.close()
    asyncio.run(run())


if __name__ == "__main__":
    h = build()
    if "--no-pdf" not in sys.argv:
        export_pdf(h, ROOT / "dashboard" / "dashboard.pdf", ROOT / "assets")
    print("built", h)
