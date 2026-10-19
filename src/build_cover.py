"""Render the LinkedIn / GitHub cover images from real (synthetic) data points.  Run: python -m src.build_cover"""
import asyncio, json
import numpy as np
import pandas as pd
from .config import ROOT, SCORED, REPORTS, SEGMENTS

COL = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#22a822"]


def svg(d, w, h):
    s = d.sample(1400, random_state=7)
    pts = []
    for r in s.itertuples():
        x = 20 + r.rei / 100 * (w - 40)
        y = h - 20 - (np.log10(max(r.est_annual_revenue, 5)) - np.log10(5)) / (np.log10(40000) - np.log10(5)) * (h - 40)
        pts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.4" fill="{COL[SEGMENTS.index(r.segment)]}" fill-opacity=".85"/>')
    lines = "".join(f'<line x1="{x}" x2="{x}" y1="10" y2="{h-10}" stroke="#ffffff" stroke-opacity=".25" stroke-dasharray="4 5"/>'
                    for x in (20 + 0.5 * (w - 40), 20 + 0.7 * (w - 40)))
    return f'<svg viewBox="0 0 {w} {h}" width="{w}" height="{h}">{lines}{"".join(pts)}</svg>'


def html(W, H, S, d):
    m = S["model"]
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>
body{{margin:0;width:{W}px;height:{H}px;overflow:hidden;font-family:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
background:radial-gradient(1200px 600px at 85% 30%,#174e72 0%,#0f3b57 45%,#0b2b40 100%);color:#fff}}
.l{{position:absolute;left:64px;top:64px;width:{int(W*0.5)}px}}
.k{{font-size:15px;letter-spacing:.16em;font-weight:700;color:#9ec5f4}}
h1{{font-size:{int(W/22)}px;line-height:1.08;margin:18px 0 18px;letter-spacing:-.5px}}
p{{font-size:20px;line-height:1.4;color:#dce7f3;margin:0 0 26px}}
.chips span{{display:inline-block;font-size:15px;font-weight:600;padding:7px 13px;border-radius:999px;background:rgba(255,255,255,.12);margin:0 8px 10px 0}}
.f{{position:absolute;left:64px;bottom:48px;font-size:16px;color:#c9d7e6}} .f b{{color:#fff}}
.badge{{position:absolute;right:56px;top:56px;font-size:13px;font-weight:700;letter-spacing:.08em;border:1px solid rgba(255,255,255,.4);padding:6px 12px;border-radius:999px}}
.r{{position:absolute;right:48px;top:110px}}
</style></head><body>
<div class="l"><div class="k">PORTFOLIO PROJECT · FINANCIAL SERVICES</div>
<h1>Customer Segmentation &amp; Retention Analytics</h1>
<p>{S['customers']:,} synthetic customers · 6 value × engagement segments · attrition model AUC {m['auc_test']:.2f}</p>
<div class="chips"><span>Python</span><span>pandas</span><span>scikit-learn</span><span>Excel</span><span>Interactive dashboard</span></div></div>
<div class="badge">SYNTHETIC DATA</div>
<div class="r">{svg(d, int(W*0.40), int(H*0.62))}</div>
<div class="f"><b>Ahsan Anas</b> · data &amp; business analytics</div>
</body></html>"""


async def render():
    from playwright.async_api import async_playwright
    d = pd.read_csv(SCORED); S = json.load(open(REPORTS / "summary.json"))
    async with async_playwright() as p:
        b = await p.chromium.launch()
        for name, W, H in [("cover_linkedin_1200x627.png", 1200, 627), ("github_social_1280x640.png", 1280, 640)]:
            pg = await b.new_page(viewport={"width": W, "height": H}, device_scale_factor=2)
            await pg.set_content(html(W, H, S, d)); await pg.wait_for_timeout(200)
            await pg.screenshot(path=str(ROOT / "assets" / name)); await pg.close()
        await b.close()


if __name__ == "__main__":
    asyncio.run(render()); print("covers rendered")
