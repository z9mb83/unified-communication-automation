import markdown, re, asyncio
from playwright.async_api import async_playwright
parts=[open(f).read() for f in ["01_intro.md","02_cloud_gmail.md","03_script_sender.md","04_ai_reports_wa.md","05_ops.md","06_prompt.md"]]
md=markdown.Markdown(extensions=["tables","fenced_code","md_in_html","sane_lists"])
body=md.convert("\n\n".join(parts))
css="""
@page { size: A4; margin: 18mm 16mm 18mm 16mm; }
body { font-family: 'DejaVu Sans', sans-serif; font-size: 9.6pt; line-height: 1.5; color: #1b1b1a; }
h1 { font-size: 20pt; color: #0b0b0b; margin: 0 0 10px; border-bottom: 3px solid #2a78d6; padding-bottom: 6px; }
h2 { font-size: 14.5pt; color: #104281; margin: 18px 0 6px; page-break-after: avoid; }
h3 { font-size: 11.2pt; color: #1c5cab; margin: 14px 0 4px; page-break-after: avoid; }
p { margin: 5px 0 7px; }
code { font-family: 'DejaVu Sans Mono', monospace; font-size: 8.4pt; background: #f1f1ee; padding: 0 3px; border-radius: 3px; }
pre { background: #f6f6f3; border: 1px solid #e1e0d9; border-left: 3px solid #2a78d6; padding: 8px 10px; border-radius: 4px; white-space: pre-wrap; word-break: break-word; page-break-inside: avoid; }
pre code { background: none; padding: 0; font-size: 8pt; }
table { border-collapse: collapse; width: 100%; margin: 8px 0 12px; font-size: 8.6pt; page-break-inside: auto; }
tr { page-break-inside: avoid; }
th { background: #e8f1fd; color: #0f3a70; text-align: left; padding: 5px 6px; border: 1px solid #cfdcee; }
td { padding: 4px 6px; border: 1px solid #e1e0d9; vertical-align: top; }
blockquote { margin: 8px 0; padding: 6px 12px; background: #fafaf8; border-left: 3px solid #1baf7a; color: #333; }
ul, ol { margin: 4px 0 8px; padding-left: 20px; } li { margin: 2px 0; }
.pb { page-break-after: always; }
.cover { height: 250mm; display: flex; flex-direction: column; justify-content: center; }
.kicker { color: #2a78d6; font-weight: bold; letter-spacing: .06em; text-transform: uppercase; font-size: 9pt; }
.title { font-size: 34pt; border: none; margin: 10px 0; line-height: 1.1; }
.subtitle { font-size: 13pt; color: #52514e; max-width: 150mm; }
.cover-meta { margin-top: 30px; padding: 14px 16px; background: #f4f7fb; border-left: 4px solid #2a78d6; font-size: 10pt; }
.toc { font-size: 11pt; line-height: 1.9; columns: 1; }
.toc ol { padding-left: 22px; }
.flow { display: flex; align-items: stretch; gap: 4px; margin: 10px 0; }
.flow .step { flex: 1; background: #f4f7fb; border: 1px solid #cfdcee; border-radius: 6px; padding: 6px; font-size: 8.4pt; }
.flow .arrow { align-self: center; color: #2a78d6; font-weight: bold; }
.figure { margin: 8px 0 14px; page-break-inside: avoid; }
.figure svg { width: 100%; height: auto; }
.caption { font-size: 8.4pt; color: #666; text-align: center; margin-top: 4px; }
.prompt { background: #fbfbf9; border: 1px solid #e1e0d9; border-radius: 6px; padding: 10px 14px; font-size: 9.1pt; }
.prompt table { font-size: 8.2pt; }
.ptag { font-family: 'DejaVu Sans Mono', monospace; color: #8a4b00; font-size: 8.8pt; margin: 10px 0 4px; font-weight: bold; }
"""
html=f"<!doctype html><html><head><meta charset='utf-8'><title>Multi-Brand Outreach Automation: Build Guide</title><style>{css}</style></head><body>{body}</body></html>"
open("guide.html","w").write(html)
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(executable_path="/opt/pw-browsers/chromium-1194/chrome-linux/chrome")
        pg=await b.new_page(); await pg.goto("file://" + __import__("os").path.abspath("guide.html") + ""); await pg.wait_for_timeout(500)
        await pg.pdf(path="../Outreach_Automation_Build_Guide.pdf", format="A4", print_background=True,
          display_header_footer=True, header_template="<div></div>",
          footer_template="<div style='font-size:7.5pt;color:#888;width:100%;padding:0 16mm;display:flex;justify-content:space-between;font-family:DejaVu Sans'><span>Multi-Brand Outreach Automation · Build guide</span><span><span class=pageNumber></span> / <span class=totalPages></span></span></div>",
          margin={"top":"16mm","bottom":"18mm","left":"16mm","right":"16mm"})
        await b.close()
asyncio.run(main())
