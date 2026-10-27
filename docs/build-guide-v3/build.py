"""Build the two v3 PDFs: python3 build.py  (needs: markdown, playwright, pypdf)."""
import asyncio, os, re, markdown, pypdf
from playwright.async_api import async_playwright
CHROME = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"
CSS = open("ref/v2_build.py").read().split('css="""')[1].split('"""')[0]
assert "pre {" in CSS
CSS += """
pre,code{white-space:pre-wrap;word-break:break-word;overflow-wrap:anywhere} td,th{overflow-wrap:anywhere}
body{font-size:9.2pt;line-height:1.42} pre code{font-size:7.7pt;line-height:1.33}
.toc li{border-bottom:1px dotted #ccc;list-style:none} .toc ul{padding-left:0} .toc .part{font-weight:bold;margin-top:8px}
.pg{float:right;color:#555} .toc{line-height:1.6;font-size:10pt}
"""
DOCS = {
  "Claude_Build_Prompt_v3.pdf": dict(
    title="Claude Build Prompt", sub="Rebuild the multi-brand email and WhatsApp outreach system from scratch",
    blurb="A complete, phase-by-phase prompt for Claude. Part I specifies the backend (Google Sheet data model, Apps Script, the Python sender on Cloud Run, AI drafting with guardrails, replies and reports, WhatsApp Cloud API, testing and go-live). Part II specifies the frontend (the password-protected dashboard on Vercel and the Google Sheet as a user interface). Every pitfall met in the real build is built in as a rule.",
    meta="<b>Part I: Backend</b> (sections 1–16) · <b>Part II: Frontend</b> (sections 17–24)<br>Paste section by section; the prompt tells Claude where to stop for the owner to deploy.<br>No real passwords, tokens or keys appear; placeholders like <code>&lt;YOUR_KEY&gt;</code> stand in for them.",
    files=["P10_backend_a.md","P20_backend_b.md","P30_backend_c.md","P40_backend_d.md","P50_frontend_a.md","P60_frontend_b.md"]),
  "Project_Documentation_v3.pdf": dict(
    title="Multi-Brand Outreach Automation", sub="Project documentation",
    blurb="What the system is, who it serves, every feature, how people use it day to day, its current status, known issues, roadmap and full change history (Part 1), followed by the complete technical reference: architecture, setup, every component, operations, security, troubleshooting and the fix log (Part 2).",
    meta="Brands: Shaadi Bells, 99 Marketing Services, 99 Staffing Services, Property Experts Group, Skyline Capital.<br>Status as of 1 October 2026. No passwords, tokens or keys appear in this document.",
    files=["D10_project_overview.md","ref/10_intro.md","ref/20_cloud_gmail_sheet.md","ref/30_script_sender.md","ref/40_ai_reports_wa_dash.md","ref/50_ops_fixes.md"]),
}
def heads(md_text):
    out=[]; fence=False
    for l in md_text.split("\n"):
        if l.startswith("```"): fence=not fence; continue
        if fence: continue
        if l.startswith("# "): out.append(("part", l[2:].strip()))
        elif re.match(r"^## (\d+|P\d+)\.", l): out.append(("ch", l[3:].strip()))
    return out
def html_for(d, pages):
    body_md="\n\n".join(open(f).read() for f in d["files"])
    toc=[]
    for kind,t in heads(body_md):
        p=pages.get(t,"")
        toc.append(f'<li class="{"part" if kind=="part" else ""}">{t} <span class="pg">{p}</span></li>')
    cover=f'''<div class="cover"><div class="kicker">Version 3 · 1 October 2026</div><h1 class="title">{d["title"]}</h1>
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
    r=pypdf.PdfReader(pdf); txt=[" ".join(p.extract_text().split()) for p in r.pages]; found={}
    for t in titles:
        key=" ".join(t.split())[:40]
        for i in range(2,len(txt)):
            if key in txt[i]: found[t]=i+1; break
    return found, len(txt)
for out,d in DOCS.items():
    label=f'{d["title"]} · v3'
    asyncio.run(render(html_for(d,{}), "../"+out, label))
    titles=[t for _,t in heads("\n\n".join(open(f).read() for f in d["files"]))]
    pages,n=find_pages("../"+out, titles)
    asyncio.run(render(html_for(d,pages), "../"+out, label))
    pages,n=find_pages("../"+out, titles)
    print(out, n, "pages;", {t[:28]:p for t,p in list(pages.items())})
os.remove("_tmp.html")
