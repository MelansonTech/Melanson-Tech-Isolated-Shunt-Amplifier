"""Render a Markdown design guide - or a finished HTML page - to a printable PDF.

    python md_to_pdf.py IN.md   OUT.pdf [--project "Board name"]
    python md_to_pdf.py IN.html OUT.pdf --html

python-markdown builds the HTML; Microsoft Edge (headless, always present on
Windows) prints it. No LaTeX, no wkhtmltopdf. The header line carries the
project, the source file and the render date so a printed copy can be traced.
`--html` takes a page that is already complete - an artifact saved with the
Artifact tool's `read` - and only wraps it in a minimal document shell.

Edge is run with its own throwaway profile, prints to a temporary file, and the
result is verified and then moved into place. That matters: printing straight
onto the destination fails **silently** when the PDF is open in a reader (the
file is locked), leaving the previous render on disk while every command
reports success. This script raises instead, and names the file to close.
"""
import sys, os, re, subprocess, pathlib, datetime, tempfile, shutil, markdown

EDGE = [r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"]
CSS = """
@page { size: A4; margin: 16mm 16mm 18mm 16mm; }
body { font: 10.5pt/1.45 "Segoe UI", Calibri, Arial, sans-serif; color: #1a1a1a; max-width: 100%; }
.hdr { font: 8.5pt "Segoe UI", sans-serif; color: #666; border-bottom: 1px solid #bbb; padding-bottom: 4px; margin-bottom: 14px; display: flex; justify-content: space-between; }
h1 { font-size: 20pt; margin: 0 0 8px; line-height: 1.2; }
h2 { font-size: 14pt; margin: 20px 0 6px; border-bottom: 1px solid #ddd; padding-bottom: 2px; page-break-after: avoid; }
h3 { font-size: 11.5pt; margin: 14px 0 4px; page-break-after: avoid; }
p, li { orphans: 3; widows: 3; }
code { font: 9pt Consolas, "Courier New", monospace; background: #f3f3f3; padding: 0 3px; border-radius: 2px; }
pre { background: #f5f5f5; border: 1px solid #ddd; padding: 8px; font: 8.5pt Consolas, monospace; white-space: pre-wrap; page-break-inside: avoid; }
pre code { background: none; padding: 0; }
table { border-collapse: collapse; margin: 6px 0 10px; font-size: 9.5pt; page-break-inside: avoid; }
th, td { border: 1px solid #ccc; padding: 3px 7px; vertical-align: top; text-align: left; }
th { background: #eee; }
hr { border: 0; border-top: 1px solid #ccc; margin: 14px 0; }
/* Without this a figure wider than the text column is CLIPPED at the page
   edge, not scaled - and it looks like a correctly placed image until you
   notice a panel is missing. height:auto keeps the aspect ratio. */
img { max-width: 100%; height: auto; display: block; margin: 10px auto;
      page-break-inside: avoid; }
blockquote { border-left: 3px solid #ccc; margin: 8px 0; padding: 2px 10px; color: #444; }
strong { font-weight: 600; }
a { color: #1a1a1a; text-decoration: none; }
.mark { font-weight: 600; padding: 0 3px; border-radius: 2px; }
.decide { background: #fff2c6; } .verify { background: #dbeafe; }
li.task { list-style: none; margin-left: -1.2em; }
"""
SHELL_CSS = (':root{color-scheme:light}body{margin:0;font:14px -apple-system,BlinkMacSystemFont,'
             'sans-serif;background:#faf9f5;color:#141413}img{max-width:100%}')


def inline_images(html, base_dir):
    """Replace relative <img src> with data URIs, resolved against base_dir.

    The page is printed from a temp directory, so a relative path finds
    nothing and Edge renders a blank gap without complaining. Inlining makes
    the page self-contained and independent of where it is printed from.
    """
    import base64
    import mimetypes

    def sub(m):
        src = m.group(2)
        if src.startswith(("http://", "https://", "data:", "file:")):
            return m.group(0)
        p = os.path.normpath(os.path.join(base_dir, src.replace("/", os.sep)))
        if not os.path.exists(p):
            print(f"  WARNING: image not found, it will be blank: {src}")
            return m.group(0)
        mime = mimetypes.guess_type(p)[0] or "image/png"
        b64 = base64.b64encode(open(p, "rb").read()).decode("ascii")
        print(f"  inlined {src} ({os.path.getsize(p):,} B)")
        return f'{m.group(1)}data:{mime};base64,{b64}"'

    return re.sub(r'(<img[^>]*\ssrc=")([^"]+)"', sub, html)


def print_pdf(page_html, out_pdf):
    """Print an HTML string to out_pdf, failing loudly if the file cannot be written."""
    out_pdf = os.path.abspath(out_pdf)
    edge = next((p for p in EDGE if os.path.exists(p)), None)
    if edge is None:
        raise SystemExit("Microsoft Edge not found - install it or adapt EDGE[]")
    tmp = tempfile.mkdtemp(prefix="mdpdf-")
    try:
        src = pathlib.Path(tmp, "page.html")
        src.write_text(page_html, encoding="utf-8")
        dst = pathlib.Path(tmp, "out.pdf")
        r = subprocess.run([edge, "--headless=new", "--disable-gpu", "--no-first-run",
                            f"--user-data-dir={tmp}\\profile", "--no-pdf-header-footer",
                            "--virtual-time-budget=9000", f"--print-to-pdf={dst}",
                            src.resolve().as_uri()],
                           capture_output=True, text=True, timeout=180)
        if not dst.exists() or dst.stat().st_size < 1000 or dst.read_bytes()[:4] != b"%PDF":
            raise SystemExit(f"Edge produced no PDF for {out_pdf}\n{r.stderr[-800:]}")
        try:
            shutil.move(str(dst), out_pdf)
        except OSError as e:
            raise SystemExit(f"cannot write {out_pdf}: {e.strerror}. "
                             f"It is almost certainly open in a PDF reader - close it and re-run.")
        print(f"  {out_pdf}  ({os.path.getsize(out_pdf):,} B)")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def render_markdown(src_md, out_pdf, project=None):
    md = open(src_md, encoding="utf-8").read()
    md = re.sub(r"^(\s*)- \[ \] ", r"\1- &#9744; ", md, flags=re.M)
    md = re.sub(r"^(\s*)- \[x\] ", r"\1- &#9745; ", md, flags=re.M | re.I)
    html = markdown.markdown(md, extensions=["tables", "fenced_code", "sane_lists", "attr_list"])
    html = inline_images(html, os.path.dirname(os.path.abspath(src_md)))
    html = html.replace("<strong>[decide]</strong>", '<span class="mark decide">[decide]</span>') \
               .replace("<strong>[verify]</strong>", '<span class="mark verify">[verify]</span>') \
               .replace("[decide]", '<span class="mark decide">[decide]</span>') \
               .replace("[verify]", '<span class="mark verify">[verify]</span>')
    html = html.replace('<span class="mark decide"><span class="mark decide">', '<span class="mark decide">') \
               .replace('<span class="mark verify"><span class="mark verify">', '<span class="mark verify">') \
               .replace("</span></span>", "</span>")
    title = re.search(r"<h1>(.*?)</h1>", html)
    title = re.sub("<.*?>", "", title.group(1)) if title else os.path.basename(src_md)
    hdr = (f'<div class="hdr"><span>{project + " &middot; " if project else ""}{title}</span>'
           f'<span>{os.path.basename(src_md)} &middot; rendered {datetime.date.today().isoformat()}</span></div>')
    print_pdf(f'<!doctype html><html><head><meta charset="utf-8"><title>{title}</title>'
              f'<style>{CSS}</style></head><body>{hdr}{html}</body></html>', out_pdf)


def render_html(src_html, out_pdf):
    body = open(src_html, encoding="utf-8").read()
    print_pdf('<!doctype html><html><head><meta charset="utf-8">'
              '<meta name="viewport" content="width=device-width, initial-scale=1">'
              f'<style>{SHELL_CSS}</style></head><body>{body}</body></html>', out_pdf)


if __name__ == "__main__":
    a = sys.argv[1:]
    if len(a) < 2 or "--help" in a:
        raise SystemExit(__doc__)
    if "--html" in a:
        render_html(a[0], a[1])
    else:
        render_markdown(a[0], a[1], a[a.index("--project") + 1] if "--project" in a else None)
