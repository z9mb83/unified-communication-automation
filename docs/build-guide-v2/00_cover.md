<div class="cover" markdown="1">
<div class="kicker">Build guide · Version 2 · 30 September 2026</div>
<h1 class="title">Multi-Brand Outreach Automation</h1>
<div class="subtitle">How to build, run and fix an email and WhatsApp outreach system for several brands from scratch: Google Sheets and Apps Script as the control panel, Cloud Run for sending, AI-written drafts, Meta's WhatsApp Cloud API with reply tracking, and a live dashboard. Includes every problem met in the real build and how it was fixed, plus a complete build prompt for Claude.</div>
<div class="cover-meta" markdown="1">
**Part A (chapters 1–22):** the guide: architecture, setup, every component in detail, operations, security, troubleshooting and the fix log.<br>
**Part B (chapters 23–25):** the Claude build prompt, ready to paste.<br>
Brands in the reference build: Shaadi Bells, 99 Marketing Services, 99 Staffing Services, Property Experts Group, Skyline Capital.<br>
No passwords, tokens or keys appear in this document; placeholders like `<YOUR_KEY>` stand in for them.
</div>
</div>
<div class="pb"></div>

# Contents

<div class="toc" markdown="1">

**Part A: Build guide**

1. What you are building <span class="pg">3</span>
2. Architecture <span class="pg">6</span>
3. Before you start: costs and decisions <span class="pg">9</span>
4. Phase 1: Google Cloud project <span class="pg">12</span>
5. Phase 2: Gmail senders and OAuth <span class="pg">16</span>
6. Phase 3: The control sheet <span class="pg">20</span>
7. Phase 4: Apps Script (the sheet's brain) <span class="pg">26</span>
8. Phase 5: The mail sender (Cloud Run) <span class="pg">35</span>
9. Phase 6: AI email drafting <span class="pg">45</span>
10. Phase 7: Replies, bounces and daily reports <span class="pg">52</span>
11. Phase 8: WhatsApp (Meta Cloud API) <span class="pg">55</span>
12. Phase 9: Live dashboard <span class="pg">60</span>
13. Phase 10: SMS (India) <span class="pg">64</span>
14. Deliverability playbook <span class="pg">65</span>
15. Consent, compliance and law <span class="pg">67</span>
16. Security rules <span class="pg">69</span>
17. Testing and go-live <span class="pg">72</span>
18. Operations runbook <span class="pg">75</span>
19. Troubleshooting: symptom → cause → fix <span class="pg">77</span>
20. Fix log: every problem met in the real build <span class="pg">80</span>
21. Lessons learned <span class="pg">86</span>
22. Timeline and effort <span class="pg">86</span>

**Part B: The Claude build prompt**

23. How to use the prompt <span class="pg">87</span>
24. The prompt (full text), part 1 <span class="pg">89</span>
25. The prompt (full text), part 2 <span class="pg">105</span>

</div>
<div class="pb"></div>
