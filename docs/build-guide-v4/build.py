"""Build the two v3 PDFs: python3 build.py  (needs: markdown, playwright, pypdf)."""
import asyncio, os, re, markdown, pypdf
from playwright.async_api import async_playwright
CHROME = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"
CSS = open("../build-guide-v3/ref/v2_build.py").read().split('css="""')[1].split('"""')[0]
assert "pre {" in CSS
CSS += """
pre,code{white-space:pre-wrap;word-break:break-word;overflow-wrap:anywhere} td,th{overflow-wrap:anywhere}
body{font-size:9.2pt;line-height:1.42} pre code{font-size:7.7pt;line-height:1.33}
.toc li{border-bottom:1px dotted #ccc;list-style:none} .toc ul{padding-left:0} .toc .part{font-weight:bold;margin-top:8px}
.pg{float:right;color:#555} .toc{line-height:1.6;font-size:10pt}
"""
V3 = "../build-guide-v3/"
DOCS = {
  "Claude_Prompt_Kit_v4.pdf": dict(
    title="Claude Prompt Kit", sub="Rebuild the multi-brand outreach system, ML layer included",
    blurb="A master prompt Claude reads at the start of every session, plus eight modules handed over one phase at a time: M1 Sheet & Apps Script, M2 Cloud & mail sender, M3 AI drafting, M4 Replies, reports, WhatsApp & SMS, M5 Dashboard read views, M6 Lead intake, approvals, users & a private sheet, M7 the ML layer, M8 Testing, deploy, ops & pitfalls. Each module ends with a test checklist.",
    meta="<b>Part I:</b> master prompt · <b>Part II:</b> backend modules M1–M4, M8 and their version 4 updates · <b>Modules M5, M6, M7</b><br>Feed Claude the master prompt every session and only the module for the current phase.<br>No real passwords, tokens or keys appear; placeholders stand in for them.",
    files=["K00_master.md","K10_modules_note.md",V3+"P10_backend_a.md",V3+"P20_backend_b.md",V3+"P30_backend_c.md",V3+"P40_backend_d.md","K40_module_updates.md","K50_M5_dashboard.md","K60_M6_operations.md","K70_M7_ml.md"]),
  "Project_Documentation_v4.pdf": dict(
    title="Multi-Brand Outreach Automation", sub="Project documentation",
    blurb="What the system is and who it serves, every feature, daily workflows, status on 2 October 2026, known issues, the three-track roadmap (dashboard as the workplace, the ML layer, reliability), the full change history and an honest project assessment (Part 1), followed by the technical reference (Part 2).",
    meta="Brands: Shaadi Bells, 99 Marketing Services, 99 Staffing Services, Property Experts Group, Skyline Capital.<br>Status as of 2 October 2026. No passwords, tokens or keys appear in this document.",
    files=["D10_project_overview.md",V3+"ref/10_intro.md",V3+"ref/20_cloud_gmail_sheet.md",V3+"ref/30_script_sender.md",V3+"ref/40_ai_reports_wa_dash.md",V3+"ref/50_ops_fixes.md"]),
}
def read_md(f):
    t=open(f).read()
    if f.endswith("P10_backend_a.md"): t=t.replace("# Part I: Backend build prompt","## Version 3 backend text",1)
    return t
def heads(md_text):
    out=[]; fence=False
    for l in md_text.split("\n"):
        if l.startswith("```"): fence=not fence; continue
        if fence: continue
        if l.startswith("# "): out.append(("part", l[2:].strip()))
        elif re.match(r"^## (\d+|P\d+)\.", l): out.append(("ch", l[3:].strip()))
    return out
def html_for(d, pages):
    body_md="\n\n".join(read_md(f) for f in d["files"])
    toc=[]
    for kind,t in heads(body_md):
        p=pages.get(t,"")
        toc.append(f'<li class="{"part" if kind=="part" else ""}">{t} <span class="pg">{p}</span></li>')
    cover=f'''<div class="cover"><div class="kicker">Version 4 · 2 October 2026</div><h1 class="title">{d["title"]}</h1>
<div class="subtitle"><b>{d["sub"]}</b><br><br>{d["blurb"]}</div><div class="cover-meta">{d["meta"]}</div></div><div class="pb"></div>
<h1>Contents</h1><div class="toc"><ul>{"".join(toc)}</ul></div><div class="pb"></div>'''
    body=markdown.markdown(body_md, extensions=["tables","fenced_code","sane_lists"])
    body=re.sub(r"<h1>", '<h1 style="page-break-before:always">', body)
    return f"<!doctype html><html><head><meta charset='utf-8'><style>{CSS}</style></head><body>{cover}{body}</body></html>"
async def render(html, out, label):
    open("_tmp.html","w").write(html)
    async with async_playwright() as p:
        b=await p.chromium.launch(executable_path=CHROME); pg=await b.new_page()
        await pg.goto("file://"+os.path.abspath("_tmp.html")); await pg.wait_for_timeout(500)
        await pg.pdf(path=out, format="A4", print_background=True, display_header_footer=True, header_template="<div></div>",
          footer_template=f"<div style='font-size:7.5pt;color:#888;width:100%;padding:0 14mm;display:flex;justify-content:space-between;font-family:DejaVu Sans'><span>{label}</span><span><span class=pageNumber></span> / <span class=totalPages></span></span></div>",
          margin={"top":"13mm","bottom":"15mm","left":"14mm","right":"14mm"})
        await b.close()
def find_pages(pdf, titles):
    """Page of each heading, searching forward from the previous match (headings are in order)."""
    import re as _re
    norm=lambda x: _re.sub(r"ff|fi|fl","",_re.sub(r"[^a-z0-9]","",x.lower()))
    r=pypdf.PdfReader(pdf); txt=[norm(p.extract_text()) for p in r.pages]; found={}; start=2
    for t in titles:
        key=norm(t)[:28]
        for i in range(start,len(txt)):
            if key and key in txt[i]: found[t]=i+1; start=i; break
    return found, len(txt)
for out,d in DOCS.items():
    label=f'{d["title"]} · v4'
    asyncio.run(render(html_for(d,{}), "../"+out, label))
    titles=[t for _,t in heads("\n\n".join(read_md(f) for f in d["files"]))]
    pages,n=find_pages("../"+out, titles)
    asyncio.run(render(html_for(d,pages), "../"+out, label))
    pages,n=find_pages("../"+out, titles)
    print(out, n, "pages;", {t[:28]:p for t,p in list(pages.items())})
os.remove("_tmp.html")
