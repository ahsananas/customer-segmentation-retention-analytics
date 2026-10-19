# Cover image concept

**Files:** `assets/cover_linkedin_1200x627.png` (LinkedIn link / post image) · `assets/github_social_1280x640.png` (GitHub social preview: Settings → Social preview)

**Concept: "the segment map".** A deep navy background (#0F3B57) with the project title set large in white on the left. On the right, about 1,400 real points from the synthetic dataset are plotted as engagement (x) against revenue (y, log scale) and coloured by the six segments. The dashed lines at engagement 50 and 70 hint at the segmentation rules. The image is generated from the project's own data, so it is a genuine preview of the analysis rather than stock art.

**Elements**
- Kicker: PORTFOLIO PROJECT · FINANCIAL SERVICES
- Title: Customer Segmentation & Retention Analytics
- Proof line: 4,000 synthetic customers · 6 value × engagement segments · attrition model AUC 0.81
- Skill chips: Python · pandas · scikit-learn · Excel · Interactive dashboard
- "SYNTHETIC DATA" badge, top right (keeps the project honest at a glance)
- Footer: Ahsan Anas · data & business analytics

**Palette:** segment colours are a colour-blind-checked categorical palette (blue #2A78D6, orange #EB6834, aqua #1BAF7A, amber #EDA100, pink #E87BA4, green); the background is navy #0F3B57 → #0B2B40.
**Regenerate:** `python -m src.build_cover`
