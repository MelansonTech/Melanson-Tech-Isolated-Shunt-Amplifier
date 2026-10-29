# -*- coding: utf-8 -*-
"""The review as a self-contained HTML page for the Artifact tool: the
generated markdown rendered with python-markdown, every figure embedded as a
data URI, severity cells turned into chips. Nothing is written here that is
not in the markdown.

    python make_page.py [--date 2026-10-29]
"""
import base64
import io
import os
import re
import sys

import markdown

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(os.path.dirname(HERE))
DOCS = os.path.join(PROJ, "docs", "design-review")
DATE = sys.argv[sys.argv.index("--date") + 1] if "--date" in sys.argv else "2026-10-29"

CSS = """
<title>Isolated Shunt Amplifier Review</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Serif:wght@500;600&family=Source+Sans+3:wght@400;600&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>
/* layout: one reading column for prose and captions, full-width scrolling tables, figures inline */
:root {
  --bg: #f4f6f8; --surface: #ffffff; --fg: #1c2530; --muted: #5b6b7a; --rule: #d3dae1;
  --accent: #1f6f6b; --sev1: #b3261e; --sev2: #b26b00; --sev3: #5b6b7a; --chipfg: #ffffff;
  --display: "IBM Plex Serif", Georgia, "Times New Roman", serif;
  --body: "Source Sans 3", "Segoe UI", system-ui, sans-serif;
  --mono: "IBM Plex Mono", Consolas, "Courier New", monospace;
}
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {
  --bg: #141a20; --surface: #1c242c; --fg: #e3e8ec; --muted: #9fb0bf; --rule: #35414d;
  --accent: #5fc0b8; --sev1: #ff6b61; --sev2: #e6a23c; --sev3: #9fb0bf; --chipfg: #141a20; color-scheme: dark } }
:root[data-theme="dark"] {
  --bg: #141a20; --surface: #1c242c; --fg: #e3e8ec; --muted: #9fb0bf; --rule: #35414d;
  --accent: #5fc0b8; --sev1: #ff6b61; --sev2: #e6a23c; --sev3: #9fb0bf; --chipfg: #141a20; color-scheme: dark }
body { background: var(--bg); color: var(--fg); font-family: var(--body); font-size: 16px; line-height: 1.5;
  padding-left: max(16px, env(safe-area-inset-left, 0px)); padding-right: max(16px, env(safe-area-inset-right, 0px)); padding-block: 24px 64px; }
main { max-width: 960px; margin: 0 auto; }
h1, h2, h3 { font-family: var(--display); font-weight: 600; text-wrap: balance; line-height: 1.2; }
h1 { font-size: 2rem; margin: 0 0 8px; }
h2 { font-size: 1.45rem; margin: 40px 0 10px; padding-top: 10px; border-top: 1px solid var(--rule); }
h3 { font-size: 1.1rem; margin: 20px 0 6px; }
p, li { max-width: 72ch; }
p { margin: 8px 0; }
a { color: var(--accent); }
code { font-family: var(--mono); font-size: 0.9em; }
.table-wrap { overflow-x: auto; margin: 10px 0 18px; border: 1px solid var(--rule); border-radius: 4px; background: var(--surface); }
table { border-collapse: collapse; font-size: 0.88rem; min-width: 100%; font-variant-numeric: tabular-nums; }
th, td { padding: 6px 9px; border-bottom: 1px solid var(--rule); vertical-align: top; text-align: left; }
th { font-weight: 600; color: var(--muted); font-size: 0.78rem; letter-spacing: 0.04em; text-transform: uppercase; white-space: nowrap; }
tbody tr:last-child td { border-bottom: 0; }
figure { margin: 18px 0; }
figure img { max-width: 100%; height: auto; display: block; border: 1px solid var(--rule); border-radius: 4px; background: #fff; }
figcaption { font-size: 0.86rem; color: var(--muted); margin-top: 6px; max-width: 72ch; }
.chip { display: inline-block; font-family: var(--mono); font-size: 0.72rem; font-weight: 500; padding: 1px 7px; border-radius: 3px; color: var(--chipfg); }
.s1 { background: var(--sev1); } .s2 { background: var(--sev2); } .s3 { background: var(--sev3); }
.verdict-PASS { color: var(--accent); font-weight: 600; } .verdict-FAIL { color: var(--sev1); font-weight: 600; }
.lede { color: var(--muted); font-size: 0.95rem; max-width: 72ch; }
.sev-key { display: flex; gap: 12px; flex-wrap: wrap; font-size: 0.85rem; color: var(--muted); margin: 6px 0 14px; }
@media (prefers-reduced-motion: reduce) { * { animation: none !important; transition: none !important; } }
</style>
"""


def embed(html):
    def rep(m):
        p = os.path.join(DOCS, m.group(1))
        if not os.path.exists(p):
            return m.group(0)
        b = base64.b64encode(open(p, "rb").read()).decode("ascii")
        return 'src="data:image/png;base64,%s"' % b
    return re.sub(r'src="(figures/[^"]+)"', rep, html)


if __name__ == "__main__":
    md = io.open(os.path.join(DOCS, "design-review-%s.md" % DATE), encoding="utf-8").read()
    html = markdown.markdown(md, extensions=["tables"])
    # figures: <p><img ...></p><p><em>caption</em></p> -> <figure>
    html = re.sub(r'<p>(<img[^>]+>)</p>\s*<p><em>(.*?)</em></p>', r'<figure>\1<figcaption>\2</figcaption></figure>', html, flags=re.S)
    html = embed(html)
    html = re.sub(r'<table>', '<div class="table-wrap"><table>', html)
    html = re.sub(r'</table>', '</table></div>', html)
    html = re.sub(r'<td>([123])</td>', lambda m: '<td><span class="chip s%s">S%s</span></td>' % (m.group(1), m.group(1)), html)
    html = re.sub(r'<td>(PASS\*?|FAIL)</td>', lambda m: '<td class="verdict-%s">%s</td>' % (m.group(1).rstrip("*"), m.group(1)), html)
    html = html.replace('<h2>Open findings, by severity</h2>', '<h2>Open findings, by severity</h2><div class="sev-key"><span><span class="chip s1">S1</span> blocks build or operation</span><span><span class="chip s2">S2</span> fix before release</span><span><span class="chip s3">S3</span> note</span></div>')
    page = CSS + "<main>" + html + "</main>"
    out = os.path.join(DOCS, "design-review-%s.html" % DATE)
    io.open(out, "w", encoding="utf-8", newline="\n").write(page)
    print("written", out, "%.1f MB" % (len(page.encode("utf-8")) / 1e6))
