## 21. Design system

This chapter and the three after it continue Part II (Frontend) of the build prompt. Chapters
17 to 20 told Claude what the dashboard is for, which stack to use, how it is secured, what the
sheet feed returns and how the page turns that feed into a view model (`view`). The chapters
below say how every pixel, word and menu should look and behave. They describe the reference
build (repository `automation-dashboard`, files `app/globals.css`, `app/page.js`,
`components/charts.js`, `lib/*.js`) closely enough that Claude can rebuild it from nothing, and
they mark clearly where the rebuild must do better than the reference.

Paste the fenced `text` blocks as they are. The short paragraphs outside the blocks are notes
for the owner.

### 21.1 Design principles

```text
You are building a small, calm, read-only operations dashboard for one owner and a few team
members. They are not analysts. They open it on a phone between meetings or on a laptop in the
morning, and they want three answers fast: "Is anything broken?", "How much went out?" and
"Did anyone reply?". Design for those three questions and nothing else.

Principles, in priority order:

1. Truth first. Every number on screen must come from the feed (chapters 19-20) through one
   named formula that this chapter or chapter 22 states. Never estimate, smooth, round up or
   invent. If a value is missing, show 0 or an en dash (–), never a guess.
2. One glance per card. Each card answers one question in its title ("Emails sent per day",
   "Not delivered"). The subtitle says the period, the source or the unit.
3. Plain English. Use the words the owner uses in the sheet: "Approve email", "Do Not
   Contact", "Limits tab", "test mode". No marketing words, no jargon such as "conversion",
   "funnel", "throughput", "SLA".
4. Quiet colour. Neutral greys for everything structural. Colour only carries data (one fixed
   colour per brand) or status (green ok, amber warning, red problem). Never decorate.
5. Tables are first-class. Every chart has a table twin one click away, because tables are
   easier to read aloud, to copy into WhatsApp and to check against the sheet.
6. No dependencies for looks. No UI kit, no chart library, no icon font, no web font. Plain
   CSS custom properties plus hand-written SVG. This keeps the bundle tiny, avoids licence and
   upgrade work, and keeps everything on free tiers.
7. Same system in light and dark. Every colour is a token with a light and a dark value.
8. Mobile is not an afterthought. Every view must work at 360 px wide with no horizontal page
   scroll. Wide tables scroll inside their own card.

Write all styles in one file, app/globals.css, ordered: tokens, dark tokens, base, layout,
components, charts, tables, login, utilities. Do not use CSS modules, Tailwind or styled-jsx
in components; class names are short, lower-case and descriptive (card, tile, seg, pill).

Done when: you can point to app/globals.css as the only place a colour, size or radius is
defined, and the page source (app/page.js, components/charts.js) contains no hex colour
except inside the SVG favicon.
```

### 21.2 Colour tokens: surfaces, text and lines

```text
Define these tokens on :root in app/globals.css. Values are the reference build's and have
been checked for contrast. Use them by name only (var(--text-secondary)), never by value.

Token            Light       Dark        Used for
--page           #f9f9f7     #0d0d0d     page background behind cards
--surface-1      #fcfcfb     #1a1a19     inputs (login password box)
--card           #ffffff     #1a1a19     cards, tiles, banners, tooltips, segmented controls
--text-primary   #0b0b0b     #ffffff     numbers, headings, table cells
--text-secondary #52514e     #c3c2b7     labels, legend text, inactive tab text, axis names
--text-muted     #6f6d68 *   #898781     notes under tiles, subtitles, timestamps, footers
--grid           #e1e0d9     #2c2c2a     chart grid lines, table row dividers
--axis           #c3c2b7     #383835     chart baseline, value axis line, input border
--border         rgba(11,11,11,.10)  rgba(255,255,255,.10)   card and control borders
--wash           rgba(11,11,11,.05)  rgba(255,255,255,.06)   pressed tab, hover band,
                                                            message bubble background

* The reference build used #898781 for --text-muted in light mode. That is only 3.59:1 on
  white and 3.41:1 on --page, which fails WCAG AA for 12 px text. Use #6f6d68 (5.17:1 on
  white) in light mode. Keep #898781 in dark mode (4.85:1 on #1a1a19, passes).

Contrast checks you must keep passing (WCAG 2.1 AA, 4.5:1 for text under 18.66 px bold or
24 px regular):
  text-primary on card:   19.7:1 light, 17.4:1 dark
  text-secondary on card:  7.9:1 light,  9.7:1 dark
  text-muted on card:      5.2:1 light,  4.9:1 dark
Lines (--grid, --axis, --border) are decoration and do not need 3:1, because no information
is carried by a line alone: every chart has its table twin.

Base rules:
  * { box-sizing: border-box }
  html, body { margin 0; background var(--page); color var(--text-primary);
               font-family var(--font); font-size 14px; line-height 1.45 }
  button, input, select { font: inherit; color: inherit }
Always give body an explicit background so dark mode never shows a white flash.

Done when: the token table above exists in globals.css with both light and dark values, a
quick script (or a browser contrast checker) confirms the three text pairs pass 4.5:1 in both
themes, and searching the CSS for "#898781" finds it only in the dark blocks.
```

### 21.3 Brand colours, stage ramp and status colours

```text
BRAND COLOURS (categorical series). Five brands, five fixed slots. The colour follows the
brand, never its rank, its size or its position in a filtered list. Put the brand list in
lib/brands.js and derive colours from it:

  export const BRANDS = [
    { code: 'SB',  name: 'Shaadi Bells',            slot: 1 },
    { code: '99M', name: '99 Marketing Services',   slot: 2 },
    { code: '99S', name: '99 Staffing Services',    slot: 3 },
    { code: 'PE',  name: 'Property Experts Group',  slot: 4 },
    { code: 'SC',  name: 'Skyline Capital',         slot: 5 },
  ];
  export const brandVar = (code) =>
    `var(--series-${(BRANDS.find((b) => b.code === code) || { slot: 1 }).slot})`;

Token       Light     Dark      Brand
--series-1  #2a78d6   #3987e5   SB  (blue)
--series-2  #eb6834   #d95926   99M (orange)
--series-3  #1baf7a   #199e70   99S (green)
--series-4  #eda100   #c98500   PE  (amber)
--series-5  #e87ba4   #d55181   SC  (pink)

These are chart colours, not the brands' logo colours; do not try to match logos. The order of
BRANDS is also the order of every legend, every table and every stacked bar, so the same brand
is always in the same place. If a sixth brand is added, add --series-6 to both themes and a
row to BRANDS; nothing else changes. Never reuse a colour for two brands.

Brand colour is never the only way to tell brands apart: legends sit next to charts, every
tooltip names the brand, and every table has a brand column with a small swatch plus the
name (component BrandCell) or the code.

STAGE RAMP (ordinal, one hue). Used for the lead pipeline and WhatsApp delivery stages, where
order matters more than identity:

Token      Light     Dark
--stage-1  #86b6ef   #184f95   first stage (lightest in light mode)
--stage-2  #5598e7   #1c5cab
--stage-3  #2a78d6   #256abf
--stage-4  #1c5cab   #3987e5
--stage-5  #104281   #86b6ef   last stage (strongest)

In dark mode the ramp is reversed in lightness so "further along" is always "more visible".
Mail pipeline: toDraft=stage-1, drafts=stage-2, approved=stage-3, sent-only=stage-4,
replied=stage-5. WhatsApp delivery: read=stage-5, delivered-not-read=stage-3, no report
yet=stage-1, not delivered=--critical (red breaks the ramp on purpose: it is a problem).

STATUS COLOURS:
--good        #0ca30c (both)       live dot only (a filled 8 px circle)
--good-text   #006300 / #0ca30c    "OK" and "Sent" pills (7.5:1 light, 5.2:1 dark)
--warning     #fab219 (both)       stale dot, banner left border, full meter fill
--critical    #d03b3b (both)       "Paused", "Needs reconnect", "Failed" pills, error banner
                                   border, not-delivered segment
--meter-track #cde2fb / #184f95    empty part of a mailbox meter
--meter-fill  #2a78d6 / #6da7ec    used part of a mailbox meter

Rules: --warning is never used for text (1.8:1 on white). --critical text is 4.8:1 on white
(passes) but only 3.6:1 on the dark card, so every red text also carries an icon and a word
("Failed", "Paused"); colour is never the only signal. A warning-state pill uses
--text-secondary plus the warning triangle icon, not amber text.

Done when: lib/brands.js holds the five brands with fixed slots, globals.css holds the series,
stage and status tokens in both themes, and filtering to a single brand (for example PE) still
draws PE in amber everywhere.
```

### 21.4 Typography

```text
Use the system font stack only, defined once:
  --font: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
No web fonts: they cost a network request, can flash, and add nothing for a numbers page.

Type scale (px / weight / where):
  48 / 600  hero tile value (the first KPI on Mail and WhatsApp), line-height 1.05
  28 / 600  Home choice-card values (22 below 560 px)
  26 / 600  ordinary KPI tile value
  20 / 650  page title "Automation Dashboard" (h1) and login h1
  18 / 600  Home choice-card title (h2 "Mail", "WhatsApp"); also the "Sending" tile value
  14 / 600  card title (h2) and base body text (14 / 400)
  13 / 400  table cells; ".tabs .back" link
  12.5/400  reply meta line (brand, name, phone, time)
  12 / 400  labels, notes, subtitles, legend, status line, table headers (600), pills,
            link buttons, tooltip text
  11 / 400  SVG chart text (axis ticks, day labels, value labels)

Rules:
- Numbers that line up in columns or change every minute use tabular figures
  (font-variant-numeric: tabular-nums): class "num", table cells with class "r", chart text,
  tooltip values, choice-card values. This stops digits jumping on refresh.
- Format every count with fmt(n) = (n || 0).toLocaleString('en-IN'), so 125000 shows as
  1,25,000 (Indian grouping the owner reads naturally). Percentages use one decimal
  (12.5%) except "x% of confirmed" on the Delivered tile, which is a whole number.
- Dates use dayLabel('2026-09-29') = "29 Sep" (no leading zero, no year: the page only ever
  shows the last 30 days). Times are "29 Sep, 16:19" via when(t). All times are India time and
  the footer says so once; do not repeat "IST" on every row.
- Sentence case everywhere ("Emails sent per day", not "Emails Sent Per Day"). The only
  all-caps word in the product is the sheet menu name AUTOMATION.
- Never use text smaller than 11 px. Never use font-weight below 400.

Done when: the scale above is the complete set of font sizes in globals.css plus the chart
text rule; fmt and dayLabel are exported from components/charts.js and used for every number
and date on the page.
```

### 21.5 Spacing, layout grid, radii and elevation

```text
Spacing uses a small fixed set. Do not invent new values.

  2   gap between stacked chart segments; subtitle top margin
  4   gap inside pills; tile note top margin; hero value top margin
  6   gap between swatch and text; legend row gap; segmented button inner gap
  8   gap in filter bar and card header; table cell vertical padding 7, horizontal 8
  10  gap in status line and choice stats; reply vertical padding
  12  card subtitle bottom margin; banner padding (10 x 12); tab bar gap
  14  grid gap between cards; header bottom margin; legend column gap; section margin-top
  16  card padding; page side gutter; filter bar bottom margin
  20  page top padding
  48  page bottom padding

Page container ".wrap": max-width 1240px, margin 0 auto, padding 20px 16px 48px. The 16 px side
gutter is the minimum on phones; never reduce it.

Grids:
  .grid  { display: grid; gap: 14px }
  .kpis  { grid-template-columns: 1.4fr repeat(5, 1fr) }   six tiles, the first one wider
  .two   { grid-template-columns: 1fr 1fr }
  .section { margin-top: 14px }
Cards and every grid child get min-width: 0 so long email addresses and tables cannot push a
grid column wider than the screen.

Radii: 12 px cards and tiles; 10 px message bubbles; 8 px segmented controls, banners,
tooltips, login inputs and button; 4 px meters and the rounded data end of bars; 2 px brand
swatches; 1 px tooltip key lines; 50% for the live dot.

Elevation: the design is flat. Cards have a 1 px --border and no shadow. Only two things lift:
the chart tooltip (box-shadow 0 4px 16px rgba(0,0,0,.12)) and a hovered or focused Home choice
card (box-shadow 0 2px 10px rgba(0,0,0,.06) plus border-color --series-1).

Done when: the CSS uses only the spacing values listed, .wrap/.grid/.kpis/.two/.section exist
exactly as above, and a 375 px wide screenshot shows a 16 px gutter on both sides.
```

### 21.6 Cards, KPI tiles and banners

```text
CARD (.card): background --card, 1px solid --border, radius 12, padding 16, min-width 0.
Inside: h2 (14/600, margin 0) then p.sub (12, --text-muted, margin 2px 0 12px), then content.
When a card has a header action (the "Show table" toggle), wrap title and subtitle in a div
inside .card-head (flex, space-between, align flex-start, gap 8).

Use <section className="card"> for cards with a heading so the page has a sensible outline:
h1 page title, h2 per card. Do not skip heading levels.

KPI TILE (.card.tile): three lines, always in this order:
  .label  12 px --text-secondary   what is counted ("Emails sent")
  .value  26 px 600                the number, already formatted with fmt()
  .note   12 px --text-muted       the period or the formula ("last 7 days",
                                   "replies ÷ emails sent")
The first tile of a view is the hero (.tile.hero): same structure, value 48 px. It holds the
one number that view exists for (Mail: "Emails sent today"; WhatsApp: "WhatsApp replies").
A tile never contains a chart, an icon or a button. A tile with a text value instead of a
number (WhatsApp "Sending": "Live" / "Test mode") sets the value to 18 px so it does not
shout.

BANNER (.banner): full-width strip above the content: background --card, 1px --border plus
a 4 px left border in --warning, padding 10 x 12, radius 8, margin-bottom 14. Variant
.banner.err uses --critical for the left border. Banners hold one sentence, may contain one
bold phrase, and never contain buttons. Three banners exist:
  sample   (warning)  sample data is shown because the feed is not connected
  error    (err)      the last refresh failed
  attention (warning) on Home only: things that need a person today
Order when several show: sample, error, then page content (attention sits inside Home).

STALE STATE (.stale): while a refresh is running, the current view gets opacity .55 with a
.2 s transition, so the old numbers stay readable but look provisional. Rebuild rule: apply
.stale only when data is already on screen (never during the very first load), and only if
the request has taken longer than 300 ms, so the page does not blink every minute.

Done when: every tile on Mail and WhatsApp follows label/value/note, the hero tile is first
in both views, the three banners use exactly two variants, and an automatic refresh that
answers within 300 ms causes no visible flicker.
```

### 21.7 Tables, pills, meters and brand cells

```text
TABLES. Plain HTML tables, never div grids, so screen readers and copy-paste work.
  table { width 100%; border-collapse collapse; font-size 13px }
  th, td { text-align left; padding 7px 8px; border-bottom 1px solid --grid;
           vertical-align top }
  th { font-weight 600; color --text-secondary; font-size 12px }
  td.r, th.r { text-align right; tabular-nums }   every numeric column
Wrap every table in <div className="tablewrap"> (overflow-x: auto) so a wide table scrolls
inside its card on a phone instead of widening the page. Secondary information inside a cell
(the email under a name, "from linkwithshaadi1" under a recipient, the mailbox warm-up stage,
the Meta error code) goes on its own line in a div.muted at 12 px. Empty cells show an en
dash "–", never "null", "undefined", "N/A" or blank.

Sort orders are fixed and not user-changeable: day tables newest day first; lists of
replies, sends and failures newest first (the feed already sorts by time, descending); brand
tables in BRANDS order.

Empty state for a table: replace the whole table with <p className="empty"> (muted, 16 px
vertical padding) holding one short sentence ending with a full stop ("No replies yet.").

PILLS (.pill): inline-flex, gap 4, 12 px, no background, no border; a 14 px icon followed by
one or two words. Variants:
  .pill.ok    --good-text   check icon    "OK", "Sent"
  .pill.warn  --text-secondary  triangle  "Off", "Limit reached today"
  .pill.bad   --critical    x-circle      "Needs reconnect", "Paused", "Failed",
                                          any other WhatsApp result word
A failed email pill carries the feed's error text in its title attribute, so hovering shows
the reason. Rebuild improvement: also render the error (first 80 characters) as a muted
second line under the pill, because phones have no hover.

METER (mailbox usage): a div.meter (height 8, radius 4, background --meter-track,
overflow hidden) holding an <i> whose width is min(100, sentToday / dailyLimit * 100)%,
background --meter-fill. When the mailbox has reached its limit (pct >= 100) add .full and
the fill becomes --warning. Above the meter print "sentToday / dailyLimit" at 12 px with
tabular numbers ("4 / 5"; "2 / –" when no limit is set). The meter element has role="meter",
aria-valuenow, aria-valuemax (and add aria-valuemin="0" in the rebuild) and
aria-label="sent today".

BRAND CELL (BrandCell component): inline-flex, gap 6, nowrap: a 10 x 10 swatch (radius 2,
background brandVar(code)) followed by the brand's full name, or the code if the code is
unknown. Use BrandCell in every table whose first column is a brand and in reply items.
Narrow tables (Latest emails, Not delivered, Latest messages sent) show the bare code
instead, to save width.

Done when: every table is inside .tablewrap, every numeric column is right-aligned with
tabular figures, the three pill variants exist with icons, and the mailbox meter turns amber
exactly when sentToday >= dailyLimit.
```

### 21.8 Segmented tabs, link buttons, choice cards and reply items

```text
SEGMENTED CONTROL (.seg). Used for the Mail/WhatsApp switch, the date range and the brand
filter. A row of <button> elements inside one bordered box:
  .seg { display inline-flex; border 1px solid --border; radius 8; background --card;
         overflow-x auto; max-width 100%; scrollbar-width none }
  .seg button { border 0; background none; padding 6px 12px; color --text-secondary;
                white-space nowrap; flex none; display inline-flex; gap 6 }
  .seg button + button { border-left 1px solid --border }
  .seg button[aria-pressed="true"] { background --wash; color --text-primary; weight 600 }
Selection state is expressed with aria-pressed="true|false" and styled from that attribute,
so the visual state and the accessible state cannot disagree. The brand buttons show a swatch
and the code (SB, 99M, ...) with the full name in the title attribute; the first button is
"All brands". Date range buttons read "Last 7 days", "Last 14 days", "Last 30 days".
On narrow screens the control scrolls sideways inside itself; it never wraps onto two lines
and never widens the page. Give each .seg an aria-label ("Date range", "Brand") and group
the filter row with role="toolbar" aria-label="Filters".

LINK BUTTON (.linkbtn): a real <button> that looks like a link: no background, no border,
--text-secondary, underlined, 12 px, padding 0, pointer cursor. Used for "Refresh now",
"Sign out", "Show table" / "Show chart" and "← Home" (13 px). Focus ring: 2 px solid
--series-1, offset -2 px (same ring as .seg buttons). Rebuild: give link buttons at least
24 x 24 px of hit area with padding plus negative margin, so they pass WCAG 2.2 target size.

CHOICE CARD (.card.choice, Home only). The whole card is one <button> that opens a view:
  text-align left; width 100%; display block; cursor pointer;
  transition border-color .15s, box-shadow .15s;
  :hover and :focus-visible -> border-color --series-1, box-shadow 0 2px 10px
  rgba(0,0,0,.06), outline none (the coloured border is the focus indicator).
Inside, top to bottom:
  .choice-head  flex, gap 10, margin-bottom 14: 26 px line icon in --series-1, h2 (18 px),
                and a right-aligned arrow "→" (.chev, --text-muted, 18 px, aria-hidden)
  .choice-stats three equal columns, gap 10: each a value (28 px, 600, tabular) over a
                label (12 px, --text-secondary)
  p.sub         one muted line saying what is inside the view
Rebuild accessibility fix: the reference put aria-label="Open Mail" on the button, which hides
the three numbers from screen readers. Instead leave the visible text as the accessible name
and add a visually hidden "Open" prefix inside the h2 ("Open Mail"), so the numbers are read.

REPLY ITEM (.reply). One customer WhatsApp message:
  .reply        padding 10px 0; border-bottom 1px solid --grid (none on the last item)
  .reply-meta   flex, wrap, gap 12, 12.5 px: BrandCell (or muted "Unknown number"), the
                name (or "No name"), the masked phone (muted, tabular) and the time
                (muted, tabular, "29 Sep, 16:14")
  blockquote.msg  margin 6px 0 0; padding 8px 12px; background --wash; radius 10;
                  border-left 3px solid --series-3; white-space pre-wrap;
                  word-break break-word
The bubble shows the message text exactly as received (line breaks kept, no HTML: React
escapes it). Non-text messages show the feed's placeholder text ("[image] caption",
"Reacted" plus the emoji) or, if empty, a muted "[type]". The green left border means "from the
customer"; there are no outgoing bubbles.

Done when: all three filter groups use .seg with aria-pressed, the Home cards are buttons that
announce their numbers, and a reply with a three-line message renders as three lines inside a
single bubble.
```

### 21.9 Charts: shared rules and the stacked daily columns

```text
Write the charts yourself in components/charts.js as small React components that draw SVG.
No chart library: the three chart types below are about 200 lines in total, render on the
client in under a few milliseconds for 30 days x 5 brands, and have no licence or upgrade
risk. The file starts with 'use client'.

SHARED RULES
- Width: a useWidth() hook puts a ResizeObserver on the chart's wrapper div and returns
  max(260, floor(contentRect.width)); default 600 before the first measurement. The SVG uses
  viewBox="0 0 width height", height=height, width 100%, display block, overflow visible.
- Text: 11 px, var(--font), fill --text-muted, tabular figures. Category labels on bar charts
  use --text-secondary; value labels use --text-primary (or --text-secondary 600 for the
  "today" total).
- Gridlines: horizontal only, 1 px --grid; the zero line is --axis. No vertical gridlines, no
  chart border, no background fill, no 3-D, no gradients, no animation.
- Axis ticks: niceTicks(maxValue) from lib/ticks.js:
    export function niceTicks(v) {
      v = Math.max(v, 1);
      const raw = v / 4, p = Math.pow(10, Math.floor(Math.log10(raw))), n = raw / p;
      const step = Math.max(1, (n <= 1 ? 1 : n <= 2 ? 2 : n <= 5 ? 5 : 10) * p);
      const max = Math.ceil(v / step) * step, ticks = [];
      for (let t = 0; t <= max + 1e-9; t += step) ticks.push(Math.round(t));
      return { max, ticks };
    }
  It gives about four whole-number ticks on a 1-2-5 ladder (37 -> 0,10,20,30,40; 2 -> 0,1,2;
  0 -> 0,1). Counts are whole, so never show 0.5.
- Bars always start at zero. Rounded ends (4 px) only at the data end of a bar; the baseline
  end stays square so the bar visibly grows from the axis.
- Between stacked segments leave a 2 px gap (the card colour shows through) instead of a
  stroke, so adjacent brand colours never blend.
- Interaction: an invisible hit area (class "hit", fill transparent) per day or per row,
  tabIndex 0, with an aria-label summary. Mouse move or keyboard focus shows the tooltip;
  mouse leave on the chart or blur hides it. Hover/focus paints the hit area --wash.
- Tooltip (.tip): absolutely positioned div, pointer-events none, --card background, 1 px
  border, radius 8, padding 8 x 10, shadow, 12 px, min-width 150, z-index 5. Content: a title
  line (--text-secondary), one row per non-zero series with a 12 x 2 px colour key, the label
  and the bold tabular value, then a "Total" row when a total exists. role="status" so screen
  readers announce it when it appears on focus.
- Legend (.legend): flex, wrap, gap 6 x 14, 12 px, --text-secondary; swatch + label per
  series, in BRANDS order, placed above the chart. Show the legend only when more than one
  series is drawn (with one brand selected the card title already names it).

STACKEDCOLUMNS({ days, series, height = 220, unit }) - one column per day, stacked by brand.
  days:   [{ date: 'yyyy-mm-dd', values: { SB: 3, '99M': 1 } }] oldest first
  series: [{ key, label, color }] in BRANDS order (bottom of the stack = first brand)
  margins: left 34 (tick labels), right 8, top 18 (room for the today label), bottom 26
  band = innerWidth / days; bar width = max(3, min(24, band * 0.62)), centred in its band
  y(v) = top + innerHeight - v / max * innerHeight
  Day labels: show every Nth day where N = ceil(days / max(2, floor(innerWidth / 56))), always
  show the last day, and hide a regular label that would sit closer than N/2 days to the last
  one (prevents two labels overlapping at the right edge).
  Today's total: if the last day's total > 0, print it above the last column (600,
  --text-secondary), so "how many today" is readable without hovering.
  Stacking: draw only series with a value > 0; non-top segments are plain rects; the top
  segment is a path with 4 px rounded top corners; every segment above the first is
  shortened by 2 px at its bottom to leave the gap.
  Tooltip title: "29 Sep · emails sent"; rows = brands with a value that day, or one row
  "None" 0; then Total. Position: right of the column; if that would overflow
  (centre + 190 > width) flip to the left of the column. y is fixed at 4.
  Accessible name of the SVG: role="img" aria-label="<unit> per day, stacked by brand".
  Hit areas: full band width x inner height, aria-label "29 Sep: 14 total".

Done when: a 30-day chart on a 360 px phone shows non-overlapping day labels, the last day is
labelled with its total above the column, tabbing through the chart walks day by day with a
tooltip on each, and no third-party chart package is in package.json.
```

### 21.10 Charts: horizontal bars, StageBars and the chart card

```text
HBARS({ rows, valueLabel }) - one horizontal bar per brand.
  rows: [{ key, label, value, color, note }]
  label column lw = width < 520 ? 44 : min(170, width * 0.36); on narrow screens the label is
  the brand code, otherwise the full name (right-aligned, 8 px before the axis).
  value column 64 px; bar height 16; row gap 14; height = rows * 30.
  A 1 px --axis line at x = lw is the baseline. Bar width = value / max * innerWidth, drawn
  as a path with the right end rounded (radius min(4, width)). Zero values draw no bar.
  After the bar print "1,234  (2.3%)": the value plus the optional note, --text-primary.
  Hit area: the whole row, aria-label "<label>: <value>"; tooltip = label + one row
  (valueLabel, colour, value), placed just right of the bar end, clamped to width - 170.

STAGEBARS({ rows, stages }) - one 100%-of-largest stacked horizontal bar per brand across
ordered stages.
  stages: [{ key, label, color }] in order; rows: [{ key, label, values: { stage: n } }]
  Same label column rule as HBars; right column 52 px holds the row total (right-aligned at
  width - 4). Bar height 16, gap 14.
  Scale: every row shares one scale, max = the largest row total, so bar lengths compare
  brands. Segments are drawn left to right in stage order, only for values > 0, each 2 px
  shorter than its share to leave a gap; the last segment gets a 4 px rounded right end when
  it is wider than 4 px.
  Tooltip: brand name, then EVERY stage (including zeros, so the reader sees the whole
  pipeline) with colour key, then Total.
  Accessible name: role="img" aria-label "Lead pipeline by brand" (rebuild: take the label
  from a prop so the WhatsApp delivery chart says "WhatsApp delivery by brand").
  Hit area aria-label "<brand>: <total> leads" (rebuild: "<total> messages" for WhatsApp).

CHARTCARD({ title, sub, legend, chart, table }) - the only way a chart appears on the page.
  <section className="card">
    .card-head: h2 title + p.sub, and on the right a link button "Show table" that toggles
    to "Show chart" (aria-pressed reflects the table state)
    then either the table (inside .tablewrap) or legend + chart
  </section>
The table twin is required, not optional: every ChartCard is given a table. The toggle is
per card and is not remembered between visits (a fresh load always shows charts).

Table twins used by the views:
  DayTable(days, series): columns Day, one per brand code (right), Total (right, bold);
    rows newest day first.
  BrandTable(view): Brand, Sent, Replies, Reply rate, Sent today.
  PipelineTable(brands): Brand, Leads, No draft, To review, Approved, Sent, Replied, Bounced.
  WhatsApp delivery table: Brand, Sent, Delivered, Read, Not delivered, Replied.

Done when: HBars and StageBars switch to brand codes below 520 px, every chart card has a
working "Show table" toggle whose table sums to the same totals as the chart, and the
WhatsApp delivery chart announces itself as delivery, not as the lead pipeline.
```

### 21.11 Icons and favicon

```text
Icons are inline SVG paths written in the page, stroke-based, using currentColor so they take
the colour of the surrounding text. Never use an icon font, emoji or image file for UI icons.
Every decorative icon has aria-hidden="true"; the meaning is always also in a word next to it.

Status icons (component Icon, viewBox 0 0 16 16, shown at 14 x 14 in pills):
  ok    a check:  path "M3 8.5l3 3 7-7", stroke 2, round caps and joins
  warn  a triangle with a bar and dot: "M8 2l6.5 12h-13zM8 6.5v3.5M8 12v.5", stroke 1.6
  bad   a circle (r 6.2) with an x inside: "M5.8 5.8l4.4 4.4M10.2 5.8l-4.4 4.4", stroke 1.8

Channel icons (viewBox 0 0 24 24, 26 x 26, colour --series-1, class choice-ic):
  MailIcon  an envelope: rect x3 y5 w18 h14 rx2, plus the flap "M4 7l8 6 8-6"; stroke 1.8
  ChatIcon  a speech bubble with a tail at bottom left and two text lines; stroke 1.8

Arrows are text characters, not icons: "→" in the choice card, "←" in "← Home".

Favicon: app/icon.svg (Next.js picks it up automatically), 32 x 32: a rounded square
(rx 7) in #2a78d6 with three white rounded bars of rising height, like a tiny bar chart:
  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
    <rect width="32" height="32" rx="7" fill="#2a78d6"/>
    <rect x="7" y="17" width="4" height="8" rx="1" fill="#fff"/>
    <rect x="14" y="11" width="4" height="14" rx="1" fill="#fff"/>
    <rect x="21" y="7" width="4" height="18" rx="1" fill="#fff"/>
  </svg>
Exclude icon.svg from the login middleware matcher so the browser tab shows it on the login
page too.

Done when: the page contains no <img> tags and no icon packages, every icon is aria-hidden
with a visible word beside it, and the browser tab shows the blue bar-chart icon on both the
login page and the dashboard.
```

### 21.12 Light and dark themes

```text
The dashboard follows the operating system's colour scheme. There is no theme toggle in the
UI (one less control to explain), but the CSS supports forcing a theme with a data-theme
attribute on <html>, which tests and screenshots use.

Structure in globals.css:
  :root { color-scheme: light; ...all light tokens... }
  @media (prefers-color-scheme: dark) {
    :root:where(:not([data-theme="light"])) { color-scheme: dark; ...dark tokens... }
  }
  :root[data-theme="dark"] { color-scheme: dark; ...the same dark tokens... }
:where() keeps the specificity of the media-query block equal to :root so the explicit
data-theme="dark" block wins cleanly. color-scheme makes native controls (scrollbars, the
password input) match.

Dark values differ in four ways, all already in the token tables: surfaces become near-black
(#0d0d0d page, #1a1a19 cards); series colours are slightly deeper so they do not glow; the
stage ramp is reversed so later stages are lighter; meters use a dark track (#184f95) and a
light fill (#6da7ec). --good, --warning and --critical stay the same.

Things that must look right in both themes and are easy to forget:
- the tooltip shadow (keep rgba(0,0,0,.12); it is invisible on dark, which is fine)
- the login button: background --text-primary, text --page (black on white in dark mode)
- the message bubble: --wash is a translucent white on dark
- table dividers use --grid, not --border, so they stay visible on dark cards

Done when: forcing <html data-theme="dark"> and data-theme="light" in the browser console each
gives a complete, readable page with no white boxes in dark mode and no invisible text in
either, and the OS-level setting is followed when no attribute is set.
```

### 21.13 Responsive breakpoints and mobile rules

```text
Two breakpoints, chosen from the content, not from device names:

  > 1000 px   KPI row: six tiles in one row (hero 1.4fr, five at 1fr). Paired cards side by
              side (.two = 2 columns).
  <= 1000 px  KPI row: three columns (two rows of three). Paired cards stack (.two = 1 col).
  <= 560 px   KPI row: two columns (three rows of two). Home choice-card values 22 px.

Inside charts the width (not a media query) decides: below 520 px of chart width HBars and
StageBars show brand codes instead of names; StackedColumns thins its day labels by the
56 px rule; useWidth never goes below 260 px (narrower containers scroll).

Mobile rules (check each at 360 x 740 and 390 x 844):
1. No horizontal page scroll, ever. document.scrollingElement.scrollWidth must equal the
   viewport width. Things that caused overflow in practice: long Gmail addresses (fixed by
   min-width: 0 on cards and wrapping), wide tables (fixed by .tablewrap), the brand filter
   (fixed by .seg overflow-x: auto with the scrollbar hidden).
2. The header wraps: title on one line, the status line (dot, "Updated 16:20 India time",
   "Refreshes every minute", "Refresh now", "Sign out") wraps as a flex row with gap 10.
3. The filter bar wraps: date range on one line, brand control on the next if needed.
4. Touch targets: segmented buttons are about 32 px tall in the reference; on screens
   <= 560 px raise their vertical padding to 9 px so each target is at least 40 px tall.
5. Tooltips are a mouse/keyboard nicety. On touch, tapping a day focuses its hit area and
   shows the tooltip; the table toggle is the dependable way to read exact values.
6. Long message text in reply bubbles wraps (word-break: break-word); URLs in messages must
   not overflow.
7. The hero value (48 px) must fit two-column tiles at 360 px: "1,25,000" is the widest
   realistic value; if it overflows, step the hero down to 36 px below 560 px.

Done when: screenshots at 360, 390, 768, 1024 and 1366 px wide of Home, Mail and WhatsApp
(sample data, both themes) show no horizontal scroll, no clipped numbers and no overlapping
chart labels.
```

### 21.14 Accessibility

```text
Target WCAG 2.1 AA for everything the page shows. The audience includes people reading on a
phone in sunlight, so contrast and size matter as much as screen readers.

Document and structure
- <html lang="en">, one h1 ("Automation Dashboard"), h2 per card, no skipped levels.
- metadata: title "Automation Dashboard", description "Live mail and WhatsApp activity for
  all brands", robots { index: false, follow: false } (private tool, keep it out of search).
- Regions: <header className="top">, <nav aria-label="Sections"> for ← Home / Mail /
  WhatsApp, role="toolbar" aria-label="Filters" for the filter row, <section> per card.

Live updates
- The status line has aria-live="polite" so "Updated 16:21 India time" is announced quietly
  after each refresh. Do not put aria-live on the numbers themselves: announcing 30 values
  every minute is noise.
- Error and sample banners: give the error banner role="alert" (rebuild addition); the sample
  banner stays plain text.

Keyboard
- Everything clickable is a <button> or a form button: choice cards, tabs, filters, table
  toggles, Refresh now, Sign out. No click handlers on divs.
- Focus is always visible: 2 px solid --series-1 ring on .seg and .linkbtn (offset -2 px),
  border colour + shadow on choice cards, --wash fill on chart hit areas.
- Tab order follows reading order: header controls, nav, filters, tiles (not focusable),
  charts (one stop per day/row), tables.
- Changing view moves the scroll to the top (window.scrollTo(0, 0)); in the rebuild also move
  focus to the view's first h2 (tabIndex -1) so screen reader users land in the new content.

Charts and alternatives
- Each chart SVG has role="img" and an aria-label naming what it shows; each day/row hit area
  has its own aria-label with the numbers; the tooltip has role="status".
- Every chart has a table twin via "Show table". This is the WCAG text alternative for all
  charts; never add a chart without one.
- Colour is never the only carrier: legends, tooltips and tables name brands; pills combine
  colour, icon and word; the stale state also changes the status dot colour.

Motion
- The only motion is two short transitions (choice card hover .15 s, stale opacity .2 s).
  Wrap them: @media (prefers-reduced-motion: reduce) { * { transition: none !important } }.
  Never animate chart bars or numbers.

Forms (login)
- <label htmlFor="password">Password</label>, input type="password",
  autoComplete="current-password", required, autoFocus; the error "Wrong password." has
  role="alert".

Done when: a keyboard-only pass can reach and operate every control with a visible focus ring;
a screen reader reads the Home cards with their numbers, announces the refresh time, and can
open every chart's table; axe (or Lighthouse accessibility) reports no contrast or name
errors on Home, Mail, WhatsApp and Login in both themes.
```

## 22. Pages and components

This chapter walks through every screen. Numbers come from the view model of chapter 20; this
chapter names the field each tile uses and the exact words around it. Where the reference
build has a weakness, the block says "Rebuild:" and gives the corrected behaviour.

### 22.1 File map and state model

```text
Keep the frontend small and flat. Files and their jobs:

  app/layout.js          root layout: imports globals.css, metadata, <html lang="en"><body>
  app/page.js            the whole dashboard: one client component (Dashboard) plus the view
                         components Home, MailView (inline in the reference), WhatsAppView,
                         ReplyItem, BrandCell, Icon, MailIcon, ChatIcon, and the table twins
                         DayTable, BrandTable, PipelineTable
  app/login/page.js      server component: the password form
  app/api/data/route.js  server route: reads the sheet feed (chapter 19), or sample data
  app/api/login/route.js, app/api/logout/route.js   cookie in / cookie out (chapter 18)
  middleware.js          session check for every path except /login and /api/login
  components/charts.js   StackedColumns, HBars, StageBars, ChartCard, Legend, Tip, fmt,
                         dayLabel
  lib/brands.js          BRANDS + brandVar
  lib/ticks.js           niceTicks
  lib/sample.js          sampleSnapshot(now): deterministic demo feed (chapter 20)
  lib/auth.js            COOKIE, sessionToken, safeEqual (chapter 18)
  app/icon.svg           favicon
  test/*.test.mjs        node:test unit tests (chapter 23)

Rebuild: when page.js passes about 450 lines, move MailView, WhatsAppView and Home into
components/views/*.js and the pure helpers (mailboxStatus, explainFailure, when, sum0, the
view-model builder) into lib/view.js so they can be unit-tested without React. Keep the same
names.

Client state inside Dashboard (React useState):
  data     the last good feed JSON, or null before the first success
  error    '' or the last refresh error message
  loading  true while a request is in flight
  range    7 | 14 | 30 (days), default 7
  brand    'ALL' | 'SB' | '99M' | '99S' | 'PE' | 'SC', default 'ALL'
  page     'home' | 'mail' | 'whatsapp', from the URL hash
Derived (useMemo on [data, range, brand]): view, the view model of chapter 20.
Derived (useMemo on [updated, loading]): ageMin, minutes since generatedAt.

Range and brand are shared by Mail and WhatsApp (switching tabs keeps the filter). They are
not stored in the URL or in localStorage in the reference. Rebuild: remember them per browser
in localStorage under "dash.range" and "dash.brand", wrapped in try/catch (private windows
throw), and fall back to the defaults when the stored value is not one of the allowed ones.

Done when: the files above exist with these responsibilities, Dashboard holds exactly the six
pieces of state listed, and no component other than Dashboard fetches data.
```

### 22.2 App shell and header

```text
Every authenticated view shares one shell, top to bottom:

  <div className="wrap">
    <header className="top">                       flex, align end, space-between, wrap
      <div>
        <h1>Automation Dashboard</h1>
        <div className="status-line" aria-live="polite">   12 px, muted, flex, gap 10, wrap
          <span><i className="dot-live" /> Updated 16:20 India time</span>
          <span>Refreshes every minute</span>
          <button className="linkbtn">Refresh now</button>
          <form method="post" action="/api/logout" style="display:inline">
            <button className="linkbtn" type="submit">Sign out</button>
          </form>
        </div>
      </div>
    </header>
    [sample banner] [error banner]
    [nav: ← Home + Mail/WhatsApp segmented]   (Mail and WhatsApp views only)
    [filters: date range + brand]             (Mail and WhatsApp views only)
    [the view: Home | Mail | WhatsApp]
    [footer line inside the view]
  </div>

Header details
- "Updated HH:MM India time": HH:MM is generatedAt.slice(11) from the feed (the sheet's own
  clock, Asia/Kolkata), not the browser's clock, so it tells you how fresh the SHEET data is.
  Before the first data arrives the span reads "Loading…" (with the Unicode ellipsis).
- The live dot (8 px circle) is --good when the data is fresh and gets .dot-stale (--warning)
  when there is an error or ageMin > 10. ageMin = round((now - Date.parse(generatedAt as
  "yyyy-MM-ddTHH:mm:00+05:30")) / 60000). Ten minutes allows the 30 s sheet cache plus a
  slow Apps Script response without crying wolf.
- "Refreshes every minute" is a fixed promise; keep REFRESH_MS = 60000 in one constant.
- "Refresh now" calls the same load() as the timer. While loading it stays enabled (a double
  click is harmless: the route is read-only and cached for 30 s by the sheet).
- "Sign out" is a real form POST to /api/logout, which clears the cookie and redirects (303)
  to /login. It works without JavaScript.

Sample banner (when data.sample is true), exact copy:
  Showing **sample data**: the sheet feed is not connected yet (set SHEET_API_URL and
  SHEET_API_KEY on Vercel).
Error banner (.banner.err, when error is not empty), exact copy:
  Could not refresh: <error message> Showing the last good data.
  (The second sentence appears only when data is not null.)

Footer line (inside each channel view, 12 px muted, margin-top 16):
  Mail:     Source: Automation Control Center sheet (read-only). Times are India time.
  WhatsApp: Source: Automation Control Center sheet (WhatsApp Log, WhatsApp Replies, brand
            tabs). Phone numbers are partly hidden. Times are India time.

Done when: the header shows the sheet's update time with a green dot on fresh data, turns the
dot amber when the feed is more than 10 minutes old or failing, and Sign out returns to the
login page even with JavaScript disabled.
```

### 22.3 Hash routing, navigation and filters

```text
There is one page (/) with three views chosen by the URL hash, so the browser's back button,
bookmarks and shared links work without a router or extra server routes:

  /            Home
  /#mail       Mail view
  /#whatsapp   WhatsApp view
  anything else (/#foo)  Home

Implementation:
  useEffect(() => {
    const read = () => { const h = window.location.hash.replace('#', '');
      setPage(h === 'mail' || h === 'whatsapp' ? h : 'home'); };
    read();
    window.addEventListener('hashchange', read);
    return () => window.removeEventListener('hashchange', read);
  }, []);
  const go = (p) => { window.location.hash = p === 'home' ? '' : p; setPage(p);
    window.scrollTo(0, 0); };
Read the hash only in an effect (the server render has no hash), so the first paint is Home
for a moment even on /#mail; that is acceptable because the first paint is "Loading…" anyway.
Rebuild: when going Home, use history.pushState(null, '', '/') instead of setting an empty
hash, so the address bar does not end in a bare "#".

Navigation bar (Mail and WhatsApp only), <nav className="tabs" aria-label="Sections">, flex,
gap 12, wrap, margin-bottom 12:
  "← Home" link button (13 px, class back), then a .seg with two buttons "Mail" and
  "WhatsApp" (aria-pressed on the current one).

Filter bar (Mail and WhatsApp only), <div className="filters" role="toolbar"
aria-label="Filters">, flex, gap 8, wrap, margin-bottom 16:
  .seg aria-label="Date range": "Last 7 days" | "Last 14 days" | "Last 30 days"
  .seg aria-label="Brand": "All brands" | SB | 99M | 99S | PE | SC (swatch + code,
  title = full brand name)
Changing a filter recomputes the view instantly from the data already loaded (no request).

What the filters affect:
  range  all per-day charts, "Emails sent", "Replies", "Reply rate", "Messages sent",
         "WhatsApp replies", and the per-brand sent/replies in "Emails sent by brand".
  brand  everything on Mail and WhatsApp: tiles, charts, pipeline, mailboxes, lists.
  Neither affects "today" numbers (always today), all-time numbers (Bounced, Approved,
  Delivered, Read, Not delivered: these come from the brand tabs as they are now), or the
  recent lists' length (the feed sends the latest 15, or 25 for WhatsApp replies).
Home ignores both filters (see 22.5).

Done when: opening /#whatsapp in a new tab lands on WhatsApp, the back button walks
WhatsApp -> Mail -> Home, an unknown hash shows Home, and changing range or brand updates all
affected cards without a network request.
```

### 22.4 Data loading, auto-refresh and the page states

```text
Loading logic (in Dashboard):

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch('/api/data', { cache: 'no-store' });
      if (res.status === 401) { window.location.href = '/login'; return; }
      const json = await res.json();
      if (json.error) throw new Error(json.error);
      setData(json); setError('');
    } catch (e) { setError(String(e.message || e)); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => {
    load();
    const t = setInterval(load, REFRESH_MS);          // 60 000 ms
    const vis = () => { if (document.visibilityState === 'visible') load(); };
    document.addEventListener('visibilitychange', vis);
    return () => { clearInterval(t); document.removeEventListener('visibilitychange', vis); };
  }, [load]);

Why these choices: 60 s matches the owner's sense of "live" while the sheet caches its feed
for 30 s, so at most every second request does real work in Apps Script. Reloading when the
tab becomes visible again means a phone that was locked for an hour shows fresh numbers the
moment it is unlocked. 401 means the cookie expired or the password changed: go to /login.

Rebuild improvements (keep behaviour, remove waste):
- Pause the interval while document.visibilityState is "hidden" (a background tab should not
  call Apps Script 1,440 times a day). Restart it on "visible" after the immediate load.
- Ignore a response that arrives after a newer request started (keep a request counter), so
  a slow old response can never overwrite newer data.
- Abort the request after 25 s (AbortController) and show the error banner with
  "the sheet feed took too long to answer".
- If res.json() fails (an HTML error page from the platform), set the error to
  "the dashboard server returned an unexpected answer (HTTP <status>)".

PAGE STATES - what each one looks like:

  First load       data null, error ''  -> header "Loading…", body "Loading…" (muted p).
                   No skeletons: the feed usually answers in 1-4 s and skeletons that
                   flash are worse than a word.
  First load fails data null, error set -> header "Loading…" with amber dot, error banner
                   "Could not refresh: <message>", no body. The next minute retries.
  Normal           data set, error ''  -> green dot, full view.
  Refreshing       loading true with data -> view dimmed (.stale) after 300 ms.
  Refresh failed   data set, error set -> amber dot, error banner ending "Showing the last
                   good data.", the old view stays fully usable.
  Sample mode      data.sample true -> sample banner, real layout, demo numbers.
  Partial data     feed fields missing (an older sheet version without WhatsApp fields):
                   every optional array defaults to [] and every optional count to 0
                   (data.recentWaReplies || [], d.waReplies || {}, b.waSent || 0), so the
                   page renders with zeros and empty-list sentences instead of crashing.
                   Rebuild: if data.daily or data.brands is missing, show the error banner
                   "the sheet feed is missing <field>; publish a new web app version" and
                   keep the last good data.
  Signed out       401 from /api/data -> redirect to /login.
  Not configured   DASHBOARD_PASSWORD missing -> middleware answers 503 with the plain text
                   "Dashboard password is not configured (DASHBOARD_PASSWORD)." on every path.

Error messages come from the server route (chapter 19) and are already written for the owner,
for example "feed: unauthorized - the SHEET_API_KEY on Vercel does not match the sheet key
(114 characters; a sheet key has 64). Create a new key in the sheet and paste it again." Show
them verbatim; do not wrap them in "Error:" or a stack trace.

Done when: with the network tab throttled offline the page keeps the last numbers and shows
the amber dot and banner, coming back online heals it within a minute without a reload, a
hidden tab makes no requests, and a feed without WhatsApp fields renders Mail fully and
WhatsApp with zeros.
```

### 22.5 Home

```text
Home is the landing view. It answers "Is anything broken?" and lets the reader pick a channel.
It has no nav bar and no filters, and its numbers are always for ALL brands.

Rebuild fix: the reference computed Home from the same view as Mail/WhatsApp, so if someone
filtered Mail to SB and went back Home, Home silently showed SB only while saying "Numbers are
for all brands". Build a separate all-brands view (buildView(data, 7, 'ALL')) for Home.

Layout, top to bottom:

1. Intro line, p.secondary, margin 0 0 14:
     Choose a channel. Numbers are for all brands.

2. Two choice cards in .grid.two (side by side above 1000 px, stacked below):

   MAIL card  (button, go('mail'))
     head:  MailIcon, h2 "Mail", "→"
     stats: value fmt(view.today)            label "sent today"
            value fmt(view.mailToday7Replies) label "replies, last 7 days"
            value fmt(view.approved)          label "approved, waiting"
     sub:   Sends per day, replies, lead pipeline, mailboxes and limits
   Formulas: today = sum of brands[].sentToday; mailToday7Replies = sum of
   daily[-7..].replies over all brands (fixed 7 days, independent of the range filter);
   approved = sum of brands[].approved (rows with a draft, Approve = Yes, not sent yet).

   WHATSAPP card (button, go('whatsapp'))
     head:  ChatIcon, h2 "WhatsApp", "→"
     stats: value fmt(view.waTodayMsgs)    label "sent today"
            value fmt(view.waRead)         label "read"
            value fmt(view.waTodayReplies) label "replies today"
     sub:   Replies with their messages, delivery and read status, failures with reasons
   Formulas: waTodayMsgs = daily[last].whatsapp summed over brands (WhatsApp Log rows with
   result Sent today); waRead = sum of brands[].waRead (brand-tab column U = "Read", all
   time); waTodayReplies = daily[last].waReplies summed (WhatsApp Replies rows today with a
   matched brand).
   Rebuild: label the middle stat "read (all time)" so it is not mistaken for today.

3. Needs-attention banner (.banner, margin-top 14), shown only when at least one item exists:
     Needs attention: <item> · <item> · <item>
   Items, in this order, each only when its count > 0:
     "<n> mailbox need attention" / "<n> mailboxes need attention"
         n = mailboxes whose mailboxStatus(m).kind === 'bad' (Needs reconnect or Paused)
     "<n> email failed today" / "<n> emails failed today"
         n = sum of brands[].failedToday (Mail Log rows today with result Failed)
     "<n> WhatsApp not delivered"
         n = sum of brands[].waUndelivered (column U starts with "Failed", all time)
   Rebuild: the WhatsApp item counts all-time failures, so it never goes away. Count only
   failures whose send time (waFailures[].time) is within the last 7 days and write
   "<n> WhatsApp not delivered this week". Also add, when any brand has mailOn false,
   "Mail is off for <codes>" so a switched-off brand is not forgotten.
   Use "1 mailbox needs attention" (singular verb) in the rebuild; the reference's
   "1 mailbox need attention" is a grammar slip.

4. Latest WhatsApp reply (only when view.waReplyList is not empty), section.card.section:
     h2 "Latest WhatsApp reply", then one ReplyItem (22.10) for waReplyList[0].
   It is here because a customer reply is the most valuable event in the system; seeing it on
   the landing view means nobody has to dig for it.

States: no data yet -> "Loading…"; sample -> banner + sample numbers; all zero -> cards show
0s, no attention banner, no reply card (that is a normal quiet morning, not an error).

Done when: Home shows the two cards with these six numbers for all brands regardless of any
filter used before, the attention banner lists only non-zero items with correct singular and
plural words, and the newest WhatsApp reply appears under the cards.
```

### 22.6 Mail view: KPI tiles

```text
The Mail view begins with six tiles in .grid.kpis. Wrap the whole view in a div that gets
.stale while refreshing. Every formula uses the brand filter (codes) and the range filter
(days = data.daily.slice(-range)) as noted.

  #  Label                Value                               Note
  1  Emails sent today    fmt(view.today)                     "<n> failed today" or
     (hero)                                                   "No failures today"
  2  Emails sent          fmt(view.sent)                      "last <range> days"
  3  Replies              fmt(view.replies)                   "last <range> days"
  4  Reply rate           view.rate.toFixed(1) + "%"          "replies ÷ emails sent"
  5  Bounced              fmt(sum of brands[].bounced)        "all time · added to Do Not
                                                              Contact"
  6  Approved, waiting    fmt(view.approved)                  "<drafts> drafts to review"

Formulas (codes = selected brand codes):
  today       = Σ brands[c].sentToday          Mail Log rows dated today with result Sent
  failedToday = Σ brands[c].failedToday        Mail Log rows dated today with result Failed
  sent        = Σ over days, Σ over codes of daily.mail[c]
  replies     = Σ over days, Σ over codes of daily.replies[c]   (rows with Replied = Yes,
                bucketed by the Replied at date)
  rate        = sent ? replies / sent * 100 : 0
  bounced     = Σ brands[c].bounced            rows whose Email status is Bounced or
                Unsubscribed (the sender also adds them to Do Not Contact)
  approved    = Σ brands[c].approved           draft present, Approve email = Yes, status
                not Sent/Bounced/Unsubscribed/Failed
  drafts      = Σ brands[c].drafts             draft present, not approved yet

Notes on meaning, to keep in mind when wording:
- Reply rate divides replies dated in the period by emails sent in the period. A reply to an
  email sent before the period counts, so with few sends the rate can exceed what you expect.
  That is fine for a trend; do not "fix" it by joining replies to sends.
- "Emails sent today" uses the Mail Log (attempts), not the brand tab, so it matches what
  the mailboxes table shows.
- The "failed today" note should read "1 failed today" or "3 failed today" (the reference
  writes "<n> failed today" for every n, which is already correct English).

States: zero sends -> tiles show 0 and "0.0%"; sample -> sample numbers; a brand filter that
has no data -> zeros, never blank tiles.

Done when: the six tiles show these exact labels and notes, changing the range changes tiles
2-4 only, changing the brand changes all six, and each value can be reproduced by hand from
the Mail Log and brand tab of the sheet.
```

### 22.7 Mail view: per-day charts and emails by brand

```text
Below the tiles, three chart cards.

1. EMAILS SENT PER DAY (full width, .section)
   ChartCard title "Emails sent per day"
             sub   "Last <range> days, by brand · hover a day for details"
             legend: series legend when more than one brand is shown
             chart: StackedColumns days=view.mailDays series=view.series unit="emails sent"
                    height=240
             table: DayTable(view.mailDays, view.series)
   mailDays = days.map(d => ({ date: d.date, values: d.mail })). Sundays show as zero
   columns (the sender runs Monday-Saturday); do not drop them, a gap is information.

2. REPLIES PER DAY (left of a .grid.two.section)
   ChartCard title "Replies per day"
             sub   "Last <range> days · from the 10 AM / 6 PM reply check"
             chart: StackedColumns days=view.replyDays unit="replies" height=200
             table: DayTable(view.replyDays, view.series)
   The subtitle tells the reader why replies arrive in two daily bursts: the reply check runs
   with the 10:00 and 18:00 reports, not continuously.

3. EMAILS SENT BY BRAND (right of the same row)
   ChartCard title "Emails sent by brand"
             sub   "Last <range> days · reply rate in brackets"
             chart: HBars valueLabel="Emails sent" rows = one per brand in view.series:
                      value = Σ mailDays values[brand]
                      note  = sent ? "(" + (rep / sent * 100).toFixed(1) + "%)" : ''
                      where rep = Σ replyDays values[brand]
             table: BrandTable: Brand (BrandCell), Sent, Replies, Reply rate ("–" when no
                    sends), Sent today (brands[].sentToday)

Empty data: a period with no sends draws only gridlines 0-1 and the day labels (niceTicks(0)
gives max 1), the table shows rows of zeros, and HBars draws no bars but still prints "0"
next to each brand. Never show "No data" instead of a chart: an empty week is a fact.

Done when: the three cards render for 7, 14 and 30 days, their tables add up to the tiles
above (sum of the "Emails sent per day" table = "Emails sent" tile, sum of the replies
table = "Replies" tile), and the HBars notes match the Reply rate column of BrandTable.
```

### 22.8 Mail view: pipeline, mailboxes and recent lists

```text
4. LEAD PIPELINE (left of a .grid.two.section)
   ChartCard title "Lead pipeline"
             sub   "All leads in each brand tab, by stage"
             legend: the five STAGES (always shown, the stage colours need a key)
             chart: StageBars stages=STAGES rows = view.brands.map(b => ({ key: b.code,
                    label: brand name, values: { toDraft: b.toDraft, drafts: b.drafts,
                    approved: b.approved, sentOnly: max(0, b.sent - b.replied),
                    replied: b.replied } }))
             table: PipelineTable: Brand, Leads, No draft, To review, Approved, Sent,
                    Replied, Bounced
   STAGES (in order): toDraft "New (no draft yet)" stage-1; drafts "Draft to review"
   stage-2; approved "Approved, waiting" stage-3; sentOnly "Sent" stage-4; replied
   "Replied" stage-5. Bounced and Failed rows are not in the bar (they left the pipeline)
   but are in the table. "Sent" in the bar excludes replied leads so the bar adds up.

5. MAILBOXES TODAY (right of the same row), a plain section.card (no chart):
   h2 "Mailboxes today"; sub "Sent today against each Gmail account's daily limit"
   Table columns: Mailbox | Brand | Today (28% wide) | Status
     Mailbox: the address with "@gmail.com" removed, and the warm-up stage ("Stage 2") as a
              muted 12 px second line
     Brand:   the code
     Today:   "4 / 5" (12 px tabular) above the meter (21.7)
     Status:  a pill from mailboxStatus(m), checked in this order:
       /invalid_grant|authentication repair/i in lastResult -> bad  "Needs reconnect"
       m.paused                                              -> bad  "Paused"
       !m.enabled                                            -> warn "Off"
       dailyLimit && sentToday >= dailyLimit                 -> warn "Limit reached today"
       otherwise                                             -> ok   "OK"
   Rebuild: show m.lastResult (first 80 characters) in the title attribute of the Status
   pill, and for "Needs reconnect" add a muted second line "Run tools/connect_gmail.sh" so
   the owner knows the fix (the Gmail sign-in expired; see the mail chapters).

6. LATEST REPLIES (left of a .grid.two.section)
   h2 "Latest replies"; sub "Leads who replied to our emails (newest first)"
   Columns: Brand (BrandCell) | Name / email (name, email muted below) | Phone ("–" if
   blank) | Replied ("29 Sep, 16:19")
   Data: view.replyList = recentReplies filtered by brand (the feed's 15 newest across all
   brands; after filtering there may be fewer).
   Empty: "No replies yet."

7. LATEST EMAILS (right of the same row)
   h2 "Latest emails"; sub "Most recent send attempts"
   Columns: Time | Brand (code) | To (address, "from <mailbox without @gmail.com>" muted
   below) | Result (pill ok "Sent", or pill bad with the result word or "Failed", error
   text in title)
   Data: view.sendList = recentSends filtered by brand.
   Empty: the reference says "No emails in this period." although the list is not filtered by
   the range. Rebuild copy: "No emails sent yet."

Privacy note: the Mail view shows lead names, email addresses and phone numbers in full,
because the readers are the team that owns those leads and the dashboard is behind a
password. Phone numbers on the WhatsApp view are masked by the feed. Do not add export,
download or copy-all buttons.

Done when: the pipeline bar for each brand equals its table row minus Bounced/Failed, the
mailbox with an invalid_grant last result shows a red "Needs reconnect" pill, a full mailbox
shows an amber meter and "Limit reached today", and both recent lists respect the brand
filter and fall back to their empty sentences.
```

### 22.9 WhatsApp view: KPI tiles

```text
The WhatsApp view has the same shell, nav and filters as Mail. It starts with six tiles in
.grid.kpis, wrapped in a div that gets .stale while refreshing.

  #  Label              Value                          Note
  1  WhatsApp replies   fmt(view.waReplies)            "last <range> days · <n> leads have
     (hero)                                            replied"
  2  Messages sent      fmt(view.whatsapp)             "last <range> days"
  3  Delivered          fmt(view.waDelivered)          "<p>% of confirmed", or the text
                                                       "reports since <DELIVERY_SINCE>" when
                                                       nothing is confirmed yet
  4  Read               fmt(view.waRead)               "blue ticks"
  5  Not delivered      fmt(view.waUndelivered)        "reasons below"
  6  Sending            "Live" or "Test mode" (18 px)  "automatic sending <on (every 5
                                                       min) | off>"

Formulas (codes = selected brands):
  waReplies      = Σ days Σ codes daily.waReplies[c]   WhatsApp Replies rows in the period
                   that matched a brand
  waRepliedLeads = Σ brands[c].waReplied               brand rows with WhatsApp replied =
                   Yes (column V), all time
  whatsapp       = Σ days Σ codes daily.whatsapp[c]    WhatsApp Log rows with result Sent
  waDelivered    = Σ brands[c].waDelivered             column U = Delivered or Read
  waRead         = Σ brands[c].waRead                  column U = Read
  waUndelivered  = Σ brands[c].waUndelivered           column U starts with "Failed"
  confirmed      = waDelivered + waUndelivered
  p              = confirmed ? round(waDelivered / confirmed * 100) : 0
  Sending value  = data.settings.whatsappLive ? "Live" : "Test mode"
  Sending note   = "automatic sending " + lower(data.settings.whatsappAuto || "Off")
                   e.g. "automatic sending on (every 5 min)" or "automatic sending off"

Why "of confirmed": Meta reports delivery only through the reply webhook, which was switched
on after the first messages were sent. Messages without any report would make a "delivered
of sent" percentage look terrible for no reason. Dividing by messages with a report
(delivered or failed) is honest; the note says so. <DELIVERY_SINCE> is the day the webhook
started receiving status updates in your build (the reference says "29 Sep"); put it in one
constant.

"Test mode" means the Settings tab has "WhatsApp live sending" = No: only the test numbers
receive messages. Showing it as a tile stops people wondering why nothing reaches leads.

Done when: the six tiles show these labels and notes, "Delivered" switches between a
percentage and the "reports since" note correctly, and the Sending tile changes within a
minute of editing Settings B2 in the sheet (plus the 30 s feed cache).
```

### 22.10 WhatsApp view: latest replies

```text
Directly under the tiles, one full-width card (.section > section.card):

  h2  "Latest replies"
  sub "Messages customers sent to the WhatsApp number (newest first)"
  body: up to 12 ReplyItem components from view.waReplyList, or the empty sentence
        "No WhatsApp replies in this selection yet."

view.waReplyList = (data.recentWaReplies || []).filter(r => r.brand ? codes.includes(r.brand)
  : brand === 'ALL'). The feed sends the 25 newest. A reply from a number that matched no
lead has brand '' and is shown only under "All brands", with "Unknown number" in place of
the brand cell, because it may be a new enquiry and must not be hidden.

ReplyItem layout (see 21.8):
  meta line:  [swatch + brand name | "Unknown number"]  [name | "No name"]
              [masked phone, e.g. 9198****233]  [29 Sep, 16:14]
  bubble:     the message text, or a muted "[type]" when the text is empty
Name comes from the lead row (column A) when matched, else the WhatsApp profile name. The
phone is masked by the feed (first four digits, four stars, last three): the dashboard never
receives full customer numbers for WhatsApp, so it cannot leak them.

A STOP reply ("stop", "unsubscribe", ...) appears like any other message; the sheet has
already added the number to Do Not Contact. Rebuild: when the message text, trimmed and
lower-cased without trailing punctuation, is one of the stop words in chapter 19, add a small
muted tag "added to Do Not Contact" after the time.

Rebuild: if more than 12 replies are available, add a link button "Show all <n>" under the
list that expands to all of them (no new request); it collapses again on view change.

Order and sanity: the list is newest first by the feed's "yyyy-MM-dd HH:mm" time strings.
Two replies with the same minute keep the feed order. React keys: use time + phone + index,
not index alone, so a refresh does not re-use the wrong DOM node for a new reply.

Done when: replies from the sample feed appear with brand, name, masked phone, time and a
bubble; filtering to a brand hides unknown-number replies; and an empty selection shows the
exact empty sentence.
```

### 22.11 WhatsApp view: charts, delivery, failures and sent messages

```text
1. Per-day charts (.grid.two.section):

   WHATSAPP SENT PER DAY
     title "WhatsApp sent per day"; sub "Last <range> days, by brand"
     StackedColumns days=view.waDays series=view.series unit="messages sent" height=200
     table DayTable(view.waDays, ...)   waDays = days.map(d => ({ date, values:
     d.whatsapp || {} }))

   WHATSAPP REPLIES PER DAY
     title "WhatsApp replies per day"; sub "Last <range> days, by brand"
     StackedColumns days=view.waReplyDays unit="replies" height=200
     table DayTable(view.waReplyDays, ...)  waReplyDays uses d.waReplies || {}
   Both show the legend when more than one brand is selected.

2. Delivery and failures (.grid.two.section):

   DELIVERY BY BRAND (ChartCard)
     title "Delivery by brand"
     sub   "Every message sent from the sheet · delivery reports exist since <DELIVERY_SINCE>"
     legend WA_STAGES (always)
     chart StageBars stages=WA_STAGES rows = view.brands.map(b => ({ key, label, values: {
             read: b.waRead,
             delivered: max(0, b.waDelivered - b.waRead),
             failed: b.waUndelivered,
             pending: max(0, b.waSent - b.waDelivered - b.waUndelivered) } }))
     WA_STAGES order and words: read "Read" stage-5; delivered "Delivered, not read yet"
       stage-3; pending "No delivery report yet" stage-1; failed "Not delivered" critical.
     table  Brand | Sent | Delivered | Read | Not delivered | Replied  (waSent, waDelivered,
            waRead, waUndelivered, waReplied; zeros as 0)
   The bar is "sent → delivered → read" made visual: a long dark segment is good, a long pale
   segment means Meta has not reported yet, red means failed. Replies are in the table, not
   in the bar, because a reply can come without a read receipt.

   NOT DELIVERED (plain card)
     h2 "Not delivered"; sub "Messages Meta accepted but could not deliver, with the reason"
     columns: Sent ("29 Sep, 18:03") | Brand (code) | To (name or "–", masked phone muted
       below) | Reason (plain English, with "code 131049" muted below)
     data: view.waFailList = waFailures filtered by brand (the feed's 15 newest)
     empty: "Nothing failed."
     Plain reasons, from explainFailure(reason) on the leading Meta error code:
       131049  Meta limited marketing messages to this person (not a system error; try
               later)
       131026  Number cannot receive WhatsApp (not on WhatsApp or old app)
       131047  More than 24 hours since their last message: only templates allowed
       131051  Message type not supported
       other   the raw reason text from Meta (already trimmed to 160 characters)
     The code line is reason.split(' ')[0]. Keep the explanations in one table in
     lib/view.js so the email report and this page can share them.
   131049 deserves its own words because it is the most common failure and it is not ours:
   Meta stops delivering marketing templates to a person who has received too many from
   businesses recently. Owners otherwise assume the system is broken (it happened with
   Skyline Capital sends).

3. LATEST MESSAGES SENT (full width .section card)
     h2 "Latest messages sent"
     sub "Template messages sent from the sheet · “Sent” means Meta accepted it; see
          Delivery above"
     columns: Time | Brand | Phone (masked as logged) | Template | Result
       Result: pill ok "Sent", else pill bad with the result word (Failed, Retry, Opted out,
       Uncertain, Do not contact)
     data: view.waList = recentWhatsApp filtered by brand (the 15 newest log rows)
     empty: "No WhatsApp messages yet."

Then the WhatsApp footer line (22.2).

Done when: the delivery bar segments for each brand add up to its "Sent" table value, every
131049 failure reads "Meta limited marketing messages to this person ...", unknown codes show
Meta's own words, and the sub-title of Latest messages sent explains that "Sent" is not
"delivered".
```

### 22.12 Login page and sign-out

```text
app/login/page.js is a server component; it works without JavaScript.

  export const metadata = { title: 'Sign in · Automation Dashboard' };
  export default async function Login({ searchParams }) {
    const sp = await searchParams;           // Next 15: searchParams is a Promise
    return (
      <main className="login">
        <form method="post" action="/api/login" className="card login-card">
          <h1>Automation Dashboard</h1>
          <p className="muted">Mail and WhatsApp activity for all brands.</p>
          <label htmlFor="password">Password</label>
          <input id="password" name="password" type="password"
                 autoComplete="current-password" required autoFocus />
          {sp?.error ? <p className="err" role="alert">Wrong password.</p> : null}
          <button type="submit">Open dashboard</button>
        </form>
      </main>
    );
  }

Styles: .login { min-height 100vh; display grid; place-items center; padding 16 }
.login-card { width 100%; max-width 360; display grid; gap 8 } h1 20 px;
input: padding 9 x 10, 1 px --axis border, radius 8, background --surface-1;
button: margin-top 6, padding 9 x 12, no border, radius 8, background --text-primary, colour
--page, 600, pointer. .err is --critical, margin 0.

Flow (security details are in chapter 18; only the visible behaviour is here):
- Correct password: POST /api/login answers 303 to "/" and sets the session cookie for 30
  days. The dashboard opens on Home.
- Wrong password: after a deliberate 0.8 s delay, 303 to "/login?error=1"; the page shows
  "Wrong password." under the field, and the field is empty and focused again.
- Already signed in and visiting /login: the page still shows (harmless). Rebuild: if the
  cookie is valid, redirect /login to "/".
- Sign out: the header form POSTs /api/logout -> cookie deleted -> 303 to /login.
- Changing DASHBOARD_PASSWORD or SHEET_API_KEY on Vercel (and redeploying) signs everyone
  out, because the cookie value is derived from both. Tell the owner this when they rotate.
- After a successful login the browser may offer to save the password; that is fine.

Copy rules for the login page: no "Welcome back", no logo, no brand list, no "Forgot
password?" link (there is no account system: the owner sets the password on Vercel).

Done when: the login page works with JavaScript disabled, a wrong password shows "Wrong
password." after a short pause, a right one lands on Home, and Sign out returns to the login
page with the cookie gone.
```

### 22.13 States matrix

```text
Build and test every component against this matrix. "Sample" means no SHEET_API_URL or
SHEET_API_KEY (the route returns sampleSnapshot() with sample: true).

Component            Loading         Empty                       Error after data  Sample
-------------------  --------------  --------------------------  ----------------  --------
Header status        "Loading…"      n/a                         amber dot        normal
KPI tiles            not rendered    0, "0.0%", notes still shown dimmed old values   demo
StackedColumns       not rendered    gridlines 0-1, day labels   old chart         demo
HBars / StageBars    not rendered    labels + "0" totals         old chart         demo
Mailboxes table      not rendered    header row only *           old table         demo
Latest replies       not rendered    "No replies yet."           old list          2 rows
Latest emails        not rendered    "No emails sent yet."       old list          5 rows
WA latest replies    not rendered    "No WhatsApp replies in     old list          1 reply
                                     this selection yet."
Not delivered        not rendered    "Nothing failed."           old list          1 (131049)
WA latest sent       not rendered    "No WhatsApp messages yet." old list          1 row
Home attention       not rendered    hidden                      old banner        shows
                                                                                   (sample
                                                                                   has a
                                                                                   paused box)
Home latest reply    not rendered    card hidden                 old card          1 reply

* Rebuild: when a brand has no mailboxes in the filter, show "No mailboxes for this brand."
  instead of an empty table.

Edge cases to test by hand with an edited sample:
- One brand only selected: legends disappear, colours unchanged, HBars has one bar.
- A brand code in the feed that is not in BRANDS (a sixth brand added in the sheet first):
  BrandCell shows the code, brandVar falls back to slot 1; nothing crashes. Add it to BRANDS
  to give it a colour.
- A mailbox with dailyLimit 0: "3 / –", meter empty, status not "Limit reached".
- generatedAt older than 10 minutes: amber dot, no banner.
- Very long reply text (1,000 characters): bubble wraps, card grows, page does not scroll
  sideways.
- A reply with brand '' while a brand is selected: not shown.
- daily with 30 entries but range 7: only the last 7 are used.

Done when: each cell of the matrix has been seen at least once (screenshots in chapter 23
cover the sample column; the empty column is covered by a sample variant with zeroed arrays).
```

### 22.14 Copy deck

```text
Every visible string in one list, so a reviewer can check tone in one pass. Keep them exactly
unless the owner asks for a change; if a string changes, change it here too.

Shell:   Automation Dashboard · Loading… · Updated <HH:MM> India time · Refreshes every
         minute · Refresh now · Sign out · ← Home · Mail · WhatsApp · Last 7 days ·
         Last 14 days · Last 30 days · All brands
Banners: Showing sample data: the sheet feed is not connected yet (set SHEET_API_URL and
         SHEET_API_KEY on Vercel).
         Could not refresh: <message> Showing the last good data.
         Needs attention: <items joined by " · ">
Home:    Choose a channel. Numbers are for all brands. · sent today · replies, last 7 days ·
         approved, waiting · Sends per day, replies, lead pipeline, mailboxes and limits ·
         read (all time) · replies today · Replies with their messages, delivery and read
         status, failures with reasons · Latest WhatsApp reply
Mail:    Emails sent today · No failures today · <n> failed today · Emails sent · Replies ·
         last <n> days · Reply rate · replies ÷ emails sent · Bounced · all time · added to
         Do Not Contact · Approved, waiting · <n> drafts to review · Emails sent per day ·
         Last <n> days, by brand · hover a day for details · Replies per day · Last <n>
         days · from the 10 AM / 6 PM reply check · Emails sent by brand · reply rate in
         brackets · Lead pipeline · All leads in each brand tab, by stage · New (no draft
         yet) · Draft to review · Approved, waiting · Sent · Replied · Mailboxes today ·
         Sent today against each Gmail account's daily limit · Needs reconnect · Paused ·
         Off · Limit reached today · OK · Latest replies · Leads who replied to our emails
         (newest first) · No replies yet. · Latest emails · Most recent send attempts ·
         No emails sent yet. · from <mailbox>
WhatsApp: WhatsApp replies · <n> leads have replied · Messages sent · Delivered · <p>% of
         confirmed · reports since <DELIVERY_SINCE> · Read · blue ticks · Not delivered ·
         reasons below · Sending · Live · Test mode · automatic sending <state> · Messages
         customers sent to the WhatsApp number (newest first) · Unknown number · No name ·
         No WhatsApp replies in this selection yet. · WhatsApp sent per day · WhatsApp
         replies per day · Delivery by brand · Every message sent from the sheet · delivery
         reports exist since <DELIVERY_SINCE> · Read · Delivered, not read yet · No delivery
         report yet · Not delivered · Messages Meta accepted but could not deliver, with the
         reason · Nothing failed. · code <code> · Latest messages sent · Template messages
         sent from the sheet · "Sent" means Meta accepted it; see Delivery above · No
         WhatsApp messages yet.
Charts:  Show table · Show chart · Total · None · <day> · <unit>
Login:   Sign in · Automation Dashboard · Mail and WhatsApp activity for all brands. ·
         Password · Wrong password. · Open dashboard
Errors from the server route (chapter 19) are shown verbatim.

Tone rules: sentence case; short; say what happened and, if the reader must act, what to do
and where ("set SHEET_API_URL and SHEET_API_KEY on Vercel"); name sheet tabs and columns
exactly as the sheet does; never blame the reader; no exclamation marks; no emojis; numbers
as digits.

Done when: grep for each string in the source finds it, and no other user-visible string
exists in the frontend.
```

## 23. Frontend quality

The reference dashboard shipped with three unit tests and a manual check. That was enough to
launch, but the rebuild should add the view-model tests and screenshot checks below, because
almost every dashboard bug so far was a wrong number or a layout problem, not a crash.

### 23.1 Unit tests (npm test)

```text
Use Node's built-in test runner; add no test framework. package.json:
  "type": "module",
  "engines": { "node": ">=20" },
  "scripts": { "dev": "next dev", "build": "next build", "start": "next start",
               "test": "node --test test/*.test.mjs" }
Test files are ES modules (*.test.mjs) that import from lib/ with explicit ".js"
extensions. They must run without a browser, without network and without env files.

Tests that exist in the reference (test/auth.test.mjs) and must be kept:
 1. "session token depends on password and key, compare is exact": with
    DASHBOARD_PASSWORD=pw1 and SHEET_API_KEY = 64 x "k" the token is 64 hex characters;
    changing the password changes it; safeEqual(a, a) is true; safeEqual(a, b),
    safeEqual('', '') and safeEqual(a, a.slice(1)) are false; with no password the token
    is ''.
 2. "sample snapshot has the feed shape": sampleSnapshot(new Date('2026-09-29T05:00:00Z'))
    has 30 daily entries, today '2026-09-29', brand codes in BRANDS order, and the keys
    mailboxes, recentReplies, recentSends, recentWhatsApp, settings.
 3. "axis ticks are clean whole numbers": niceTicks(37) = { max 40, ticks 0..40 by 10 },
    niceTicks(2) = { max 2, ticks [0,1,2] }, niceTicks(0) = { max 1, ticks [0,1] },
    niceTicks(1340).max = 1500.

Tests to add in the rebuild (test/view.test.mjs), after moving the pure helpers into
lib/view.js (22.1):
 4. buildView(sample, 7, 'ALL'): sent equals the sum of the last 7 daily.mail values over
    all brands; rate = replies / sent * 100; today = Σ sentToday.
 5. buildView(sample, 30, 'PE'): every list contains only PE rows; series has one entry
    with colour var(--series-4).
 6. Home view ignores the filter: buildHome(sample) equals buildView(sample, 7, 'ALL') for
    the six Home numbers.
 7. mailboxStatus: invalid_grant -> Needs reconnect; paused -> Paused; enabled false ->
    Off; 5/5 -> Limit reached today; 0 limit -> OK; order of checks respected (a paused
    mailbox with invalid_grant shows Needs reconnect).
 8. explainFailure: the four known codes give their sentences; "131000 something" gives ''.
 9. attention(view): returns [] for a quiet sample; singular and plural wording for 1 and 2.
10. Missing optional fields: a feed without recentWaReplies, waFailures, waReplies and wa*
    counts builds a view with [] and 0, no exception.
11. fmt(125000) === '1,25,000'; fmt(undefined) === '0'; dayLabel('2026-09-05') === '5 Sep'.
12. The WhatsApp delivery rows: read + delivered + failed + pending equals waSent for each
    brand of the sample (pending never negative).

Rules for writing these tests:
- Compare plain data with assert.deepStrictEqual. When the objects come from a vm context
  (the Apps Script tests in the other repo load .gs files into node:vm), deepStrictEqual
  fails on identical-looking objects because their prototypes differ; compare
  JSON.parse(JSON.stringify(x)) instead. This bit the project once (fix 15).
- Tests set process.env values and delete them afterwards; never read a real .env.
- No snapshot files of rendered HTML: they break on every copy edit and hide real changes.

Done when: npm test runs at least the 12 tests above in under 2 seconds with no network, and
a deliberate bug (for example rate = sent / replies) makes test 4 fail.
```

### 23.2 Build checks

```text
Run these before every pull request and paste the summary lines into the PR description:

  npm ci                      clean install from package-lock.json (commit the lock file)
  npm test                    all unit tests pass
  npm run build               next build succeeds with no errors and no warnings you added
  grep -rn "SHEET_API_KEY" app components lib --include=*.js | grep -v "process.env"
                              must print nothing: the key is only read from process.env
                              on the server (route.js, lib/auth.js)
  grep -rln "'use client'" app components
                              must list only app/page.js and components/charts.js (and
                              components/views/* in the rebuild); lib/auth.js, the API
                              routes and middleware must never be client code

What next build tells you and what to check in its output:
- The route table: "/" and "/login" are small; "/api/data", "/api/login", "/api/logout"
  are dynamic (ƒ); middleware is listed. If "/api/data" shows as static (○), the
  export const dynamic = 'force-dynamic' line is missing and the dashboard would serve
  stale build-time data. Fix before merging.
- First Load JS for "/" should stay near the framework baseline (about 100-110 kB); see the
  budget in 23.4.

Dependencies: exactly next, react, react-dom at runtime. Dev dependencies allowed:
@playwright/test (screenshots, 23.3) only. Any other package needs a written reason in the
PR and the owner's yes, because every dependency is future upgrade work for a small team.

Node version: Vercel uses the project's Node setting; keep it on the current LTS (20 or 22)
and keep "engines" in package.json in line.

Done when: the five commands above pass on a clean checkout, the build output shows the API
routes as dynamic, and package.json has no runtime dependency other than the three listed.
```

### 23.3 Screenshot checks with Playwright (desktop and mobile, sample data)

```text
Screenshots catch the bugs unit tests cannot: overflowing tables, overlapping labels, missing
dark-mode tokens. Run them against sample data so they need no secrets and give the same
numbers every time (sampleSnapshot is seeded; pass a fixed date through an env flag).

Setup (dev dependency only, nothing ships to users):
  npm i -D @playwright/test && npx playwright install chromium
Script scripts/shots.mjs, run with: npm run shots   ("shots": "node scripts/shots.mjs")
  1. Start the app: DASHBOARD_PASSWORD=shots SAMPLE_NOW=2026-09-29T05:00:00Z
     next build && next start -p 3100 (no SHEET_API_URL / SHEET_API_KEY -> sample data).
     Rebuild: let /api/data pass new Date(process.env.SAMPLE_NOW) to sampleSnapshot when
     that variable is set, so screenshots are stable.
  2. For each viewport in [desktop 1366x900, tablet 820x1180, mobile 390x844, small 360x740]
     and each colour scheme in [light, dark] (page.emulateMedia({ colorScheme })):
       a. open /login, screenshot login-<vp>-<scheme>.png, type the password, submit;
       b. wait for the text "Showing sample data";
       c. screenshot full page of /, /#mail, /#whatsapp;
       d. on /#mail click every "Show table" button, screenshot again (mail-tables-...);
       e. assert: document.scrollingElement.scrollWidth <= window.innerWidth (no sideways
          scroll); no console errors or failed requests; the texts "Emails sent today",
          "Lead pipeline", "Mailboxes today", "Delivery by brand", "Not delivered" exist;
          the sample banner exists; the Home attention banner contains "need".
  3. Write PNGs to shots/ (in .gitignore) and print a one-line summary per viewport.
  4. Wrong-password check once: submit "nope", expect "Wrong password." within 2 s.

How to use the screenshots: look at them yourself (you can read images) before claiming a
layout change works, and attach the mobile and desktop Home, Mail and WhatsApp shots to the
pull request so the owner can approve the look without opening a preview. Do not commit the
PNGs and do not add pixel-diff tooling; a person looking is the check.

Fallback when a browser cannot be installed (locked-down environment): run next start and
fetch /login and /api/data with curl to prove the server works, say clearly in the PR that
screenshots were not taken, and ask the owner to open the Vercel preview on a phone.

Done when: npm run shots produces 4 viewports x 2 schemes x (login + 3 views + mail tables)
PNGs, every no-overflow and text assertion passes, and the PR shows the key shots.
```

### 23.4 Performance budget

```text
The dashboard is light by design; keep it that way. Budgets (measure with next build output
and Chrome DevTools on a mid-range phone profile, "Fast 4G"):

  First Load JS for "/"             <= 120 kB gzipped (reference is close to the Next.js
                                    baseline because there are no UI or chart libraries)
  CSS                               one file, <= 10 kB uncompressed (reference ~9 kB)
  Web fonts, images                 none (favicon SVG only, < 1 kB)
  /api/data response                <= 95,000 characters of JSON. The sheet feed caches
                                    only below this size (Apps Script CacheService limit is
                                    100 KB per value); above it every request rebuilds the
                                    snapshot and gets slow. Keep lists short (15/25 items),
                                    messages trimmed (300 characters), 30 days only.
  Time to data, warm cache          < 1.5 s after the HTML (route -> Apps Script cache hit)
  Time to data, cold                < 6 s (Apps Script reads every tab); the page shows
                                    "Loading…" meanwhile
  Re-render on filter change        < 16 ms (one frame) for 30 days x 5 brands: no
                                    memo tricks needed beyond the one useMemo for view
  Chart re-layout on resize         handled by one ResizeObserver per chart; no window
                                    resize listeners

Request budget: with the rebuild's "pause when hidden" rule, one open tab makes at most one
/api/data call per minute while visible. Each call is one Vercel function invocation and at
most one Apps Script web-app execution (often a cache hit). That is far inside the free
Hobby plan and the Apps Script consumer quotas for a handful of viewers. If the team grows
past about 10 people watching all day, raise REFRESH_MS to 120000 rather than paying for
anything.

Never add: client-side analytics, error-tracking SDKs, A/B tooling or third-party scripts.
They cost bundle size, may cost money and would send business data to another company.

Done when: next build reports "/" within budget, a cold load on a throttled phone shows data
in under 6 s, and the /api/data payload of the real sheet is checked to be under 95,000
characters (the route can log its length once at deploy time, never the content).
```

### 23.5 Vercel deployment (Hobby plan)

```text
Host on Vercel's free Hobby plan, from its own private GitHub repository
(automation-dashboard). Vercel's Hobby plan is meant for non-commercial use; tell the owner
this once, plainly, and note that the same app runs unchanged on Cloudflare Pages or Netlify
if that ever matters. Do not move hosts without being asked.

First-time setup (the owner clicks; you give numbered steps and wait at each checkpoint):
 1. In the sheet: AUTOMATION > Dashboard > Create access key. A dialog shows a 64-character
    key once. The owner copies it (and only it).
 2. AUTOMATION > Dashboard > Show feed link gives the web app URL ending in /exec.
 3. vercel.com/new -> Import the automation-dashboard repository (GitHub access can be
    limited to this one repository). Framework preset: Next.js. Root: the repo root.
 4. BEFORE the first deploy, add three Environment Variables for Production and Preview:
      SHEET_API_URL       the /exec URL from step 2
      SHEET_API_KEY       the 64 characters from step 1 (no spaces, no quotes)
      DASHBOARD_PASSWORD  a password the owner chooses and shares with the team
    The owner types or pastes these values into Vercel. You never see them and never ask for
    them in chat.
 5. Deploy. A build takes about a minute. Open the URL, sign in, and check the header shows
    "Updated <time> India time" with no sample banner.
 6. If the project already exists, change variables only under Project > Settings >
    Environment Variables. Values typed into the import form after the project exists are
    not saved. After any change: Deployments > latest > ... > Redeploy, because settings
    apply only to new deployments.

Lessons from the reference deployment (keep them in the README repair table):
- "feed: unauthorized ... (114 characters; a sheet key has 64)": a longer text than the key
  had been pasted into SHEET_API_KEY. Create a new key, paste exactly 64 characters,
  redeploy. The route trims stray spaces, but cannot fix extra text.
- A deployment marked "Canceled" was stopped before finishing: Redeploy and let it run.
- "feed did not return JSON": the Apps Script web app is not deployed with access "Anyone",
  or the URL is wrong (a /dev URL or a copied editor URL).
- Feed code changed in the sheet but data looks old: the Apps Script web app serves a fixed
  version. Deploy > Manage deployments > edit > Version: New version > Deploy. The /exec URL
  stays the same.

Auto-deploy: every push to main deploys Production automatically. Every push to another
branch, and every pull request, gets a Preview deployment with its own URL; Vercel comments
the link on the PR. Previews use the Preview environment variables; give them the same feed
URL and key (read-only, so safe) so the owner reviews with real numbers.

Done when: the production URL shows real data behind the password, a pull request receives a
preview link that also works, and the README has a "Settings" table and a "Repair guide"
table matching the lessons above.
```

### 23.6 Release checklist

```text
Work rule for this project: you prepare, the owner executes. You may create branches, commit,
push a branch and open a pull request. You do not merge your own pull requests, do not change
Vercel settings, do not paste secrets, and do not touch the live sheet. The owner reviews the
preview and merges; the merge deploys.

Before opening the pull request:
  [ ] Branch from the latest main; one topic per PR; title says what the reader will notice
      ("WhatsApp view: show reasons for undelivered messages").
  [ ] npm ci && npm test && npm run build all pass; paste the summary lines.
  [ ] npm run shots passes; attach Home, Mail, WhatsApp at 390 px and 1366 px, light theme,
      plus one dark-mode shot if colours changed.
  [ ] Every new number has its formula written in the PR (and in chapter 22's terms).
  [ ] Every new string is added to the copy deck (22.14) and follows the tone rules.
  [ ] No secrets, sheet IDs with keys, or real customer data in code, tests or screenshots
      (screenshots use sample data only).
  [ ] If the change needs a new feed field: the sheet side (Dashboard.gs) is changed in the
      other repository first, has its own PR and tests, and the owner has published a New
      version of the web app. The frontend must still render if the field is missing.
  [ ] README updated if setup, settings or repair steps changed.

In the PR description, end with "What you need to do": usually "Open the preview link on
your phone and laptop, check <the specific card>, then Merge". If the owner must also do
something in the sheet (publish a new web app version) or on Vercel (add a variable), list
it as numbered steps in the order they must happen.

After the owner merges:
  [ ] Watch the Production deployment finish (Vercel dashboard or the GitHub check).
  [ ] Open the production URL, sign in, confirm "Updated <time>" is current, no error banner,
      and the changed card looks like the preview.
  [ ] Tell the owner in two lines what changed and how to undo it (23.7).

Done when: every release has a PR with test output and screenshots, the owner merged it, and
you confirmed the production page afterwards.
```

### 23.7 Rollback

```text
Three independent things can be rolled back. Tell the owner which one applies.

1. The dashboard code (Vercel). Fastest: Vercel > Project > Deployments > pick the last good
   Production deployment > ... > "Promote to Production" (instant rollback; no rebuild).
   Then fix forward on a branch. Permanent: on GitHub, revert the merge commit
   ("Revert" button on the merged PR), which opens a revert PR; merging it redeploys the old
   code. Never force-push main.

2. The dashboard settings (Vercel environment variables). If a key or URL change broke the
   feed: put the previous value back (the owner keeps it in their password manager), then
   Redeploy. If the old key is lost, create a new key in the sheet (this invalidates the old
   one) and paste it.

3. The sheet feed (Apps Script web app). Extensions > Apps Script > Deploy > Manage
   deployments > edit (pencil) on the active web app > Version: choose the previous version
   number > Deploy. The /exec URL does not change, so Vercel needs nothing. Remember that
   the same web app also receives WhatsApp webhooks (doPost): rolling back the version also
   rolls back reply handling, so check the version you pick still has the reply code.

The dashboard is read-only: a broken dashboard never stops mail or WhatsApp sending. So there
is no emergency; roll back calmly, and never "fix" the dashboard by editing the live sheet.

Done when: the README repair table names these three rollbacks, and the owner has once
practised "Promote to Production" on an older deployment and back.
```

## 24. The Google Sheet as a user interface

The owner and team spend far more time in the sheet "Automation Control Center" than on the
dashboard. The sheet is where leads are added, emails approved, WhatsApp sent and limits
changed. Treat it as a real user interface with the same care: predictable layout, plain
dialogs, safe defaults. The sheet's data rules and code are in the backend part of this
prompt; this chapter covers only what people see and click.

### 24.1 Principles for the sheet UI

```text
1. One sheet, one menu. Everything a person can trigger lives under one custom menu named
   AUTOMATION (all caps, so it stands out next to Google's menus). No buttons drawn on tabs,
   no images with assigned scripts (they break on mobile and are easy to click by accident).
2. Columns are the interface. Most work is typing in cells: names, emails, "Yes" in an
   approval column. Make those columns obvious (bold header, coloured header band,
   dropdowns) and keep everything automatic in clearly labelled "(auto)" columns.
3. Safe by default. New brands start with WhatsApp OFF, live WhatsApp sending "No" (test
   numbers only), new mailboxes at 3 emails a day. Anything that sends asks YES/NO first and
   shows who will receive it.
4. Repairable. "Set up / repair tabs" can be run any time: it adds what is missing, fixes
   headers and formats, and never deletes data or rows.
5. Secrets never in cells. Tokens and keys go into Script Properties through a dialog; the
   sheet shows at most the last four characters.
6. Text, not magic numbers. Columns that hold phones, dates written by code, IDs and
   status words are formatted as plain text ("@") so Sheets never turns a phone into
   9.19876E+11, drops a leading zero, or re-interprets "2026-09-29 16:19:10" as a date in
   another time zone.
7. The assistant prepares, the owner executes. You may write Apps Script code and give
   install steps. You do not bulk-edit the live sheet, delete rows, clear columns, change
   live settings or run send functions yourself. When a data fix is needed, give the owner a
   menu item or a function with a confirmation dialog, plus exact click steps, and let them
   run it.

Done when: every action a team member needs is reachable from the AUTOMATION menu or by
typing in a labelled column, and no step requires opening the Apps Script editor except
first-time installation and web-app deployment.
```

### 24.2 The AUTOMATION menu tree

```text
Build the menu in onOpen() (common/Core.gs) exactly like this. Item text is what people see;
the function after the arrow is what runs.

AUTOMATION
├─ Set up / repair tabs                         -> ccSetup
├─ ──────────
├─ Mail
│  ├─ Send mail to selected rows                -> mlSendSelected
│  ├─ Show send-now results                     -> mlShowSendNow
│  ├─ ──────────
│  ├─ Add a sending mailbox                     -> mlAddMailbox
│  └─ Show mail status                          -> mlShowStatus
├─ WhatsApp
│  ├─ Send WhatsApp to selected rows            -> waSendSelected
│  ├─ ──────────
│  ├─ Save access token                         -> waSaveToken
│  ├─ Check templates                           -> waCheckTemplates
│  ├─ Send now (within limits)                  -> waSendNow
│  ├─ Turn automatic sending ON (every 5 min)   -> waAutoOn
│  ├─ Turn automatic sending OFF                -> waAutoOff
│  ├─ ──────────
│  ├─ Set up reply webhook (read replies)       -> waSetupWebhook
│  └─ Check reply webhook                       -> waCheckWebhook
└─ Dashboard
   ├─ Create access key                         -> dbCreateKey
   └─ Show feed link                            -> dbShowLink

Ordering logic: the daily actions come first in each submenu (send selected, see results);
setup actions (token, templates, mailbox, webhook) come after a separator; dangerous or rare
actions are never first. Labels start with a verb, say what will happen, and include the
scope in brackets where it matters ("within limits", "every 5 min", "read replies").

Things deliberately NOT in the menu:
- "Import from old email sheet" (mlImportFromOldSheet): a one-time migration, removed from
  the menu after the switch-over and blocked by Settings "Mail switched to this sheet" = Yes.
- Draft regeneration and bulk rewrites: these run on Cloud Run from Cloud Shell
  (go_master.sh regen / regen-brand), where they hold the run lock and keep backups.
- Anything that deletes data.

Running functions from the editor: tell the owner to run things from the AUTOMATION menu,
not from the Apps Script editor's Run button. In the editor the function dropdown sometimes
does not keep the selection and Run executes onOpen instead (it happened during setup); if
the editor must be used, pick the function in the dropdown, check its name is shown, then
press Run.

Done when: reloading the sheet shows AUTOMATION with exactly these four groups and 15 items,
and every item opens a dialog or alert (no silent actions).
```

### 24.3 Dialog and alert text rules

```text
Every menu action ends with a dialog. Three kinds exist; use them like this:

  ccAlert_(msg)     ui.alert with an OK button. For results and for stopping with a reason.
                    Falls back to Logger.log when there is no UI (time-driven trigger or
                    web app), so the same function works from a trigger.
  ccConfirm_(msg)   ui.alert with YES / NO. Required before anything that sends, changes many
                    rows, replaces a key, or changes where WhatsApp messages go. Returns true
                    when run without a UI (editor), so tests can call it.
  ui.prompt(title, text, OK_CANCEL)   for a single typed value (brand code, Gmail address,
                    limit, access token). Cancel always means "do nothing, say nothing".

Writing rules:
1. First line says the outcome or the question: "Send mail NOW to 4 row(s) in SB?",
   "WhatsApp: 3 sent, 1 failed", "Nothing added: ...", "Set up complete.".
2. When stopping, say why and where to fix it, naming the tab, column and value exactly:
   "Mail is OFF for SB (Limits tab, Mail row, On = No). Nothing queued."
3. Always say when nothing happened: "Nothing sent.", "Nothing queued.", "Nothing saved.",
   "Nothing added:", "Nothing to change." People must never wonder.
4. Menu paths use " > ": "AUTOMATION > WhatsApp > Save access token".
5. Lists are capped: at most 8 preview rows in a confirmation, at most 10 skipped or failed
   rows in a result, then "..." on its own line. Each line starts with "Row <n>: ".
6. Skipped rows are grouped under a blank line and "Skipped:" with a short reason each:
   "no valid email", "already emailed", "in Do Not Contact", "already waiting to be sent",
   "WhatsApp consent is not Yes", "test mode - only the Settings test numbers get
   WhatsApp", "already sent".
7. Warn about the consequences people may not expect, in capitals only for the one key word:
   "2 row(s) have no draft: the AI writes one and it is sent WITHOUT your review."
   "Sending hours and the gap are ignored. Mailbox daily limits still apply."
8. Never show a secret. A token is confirmed as "Token saved (ends with ...1a2b)." Keys are
   shown only in their one-time creation dialog (24.4).
9. Times in dialogs are India time "yyyy-MM-dd HH:mm" and say so when it matters
   ("10:00-18:00 Mon-Sat").
10. No exclamation marks, no emojis, no "Oops", no stack traces. If an exception is caught,
    show e.message after a short lead-in ("template problem - ...").
11. "row(s)" is acceptable in dialogs built from counts (it avoids plural logic in Apps
    Script), but prefer correct singular/plural in new code.

Done when: every dialog in Core.gs, Mail.gs, WhatsApp.gs and Dashboard.gs follows these rules,
and a reviewer reading only the dialog texts can tell what happened and what to do next.
```

### 24.4 Every dialog, prompt and modal

```text
Reproduce these texts (\n = new line). <..> are filled in at run time.

SETUP
  ccSetup end:            Set up complete.
  missing tab (thrown):   Tab "<name>" is missing. Run AUTOMATION > Set up / repair tabs.
  web app without id:     SHEET_ID is not saved yet: open the sheet and run any AUTOMATION
                          menu item once.

MAIL > Send mail to selected rows  (mlSendSelected, max 25 rows)
  not a brand tab:  Open a brand tab (SB, 99M, 99S, PE or SC) and select the lead rows first.
  no rows:          Select one or more lead rows (row 3 and below).
  too many:         Select at most 25 rows at a time (you selected <n>).
  brand off:        Mail is OFF for <code> (Limits tab, Mail row, On = No). Nothing queued.
  none ready:       Nothing to send.\n\nSkipped:\nRow 7: already emailed ...
  confirm (YES/NO): Send mail NOW to <n> row(s) in <code>?\n\nRow 5: Asha - asha@x.com
                    ...(max 8)\n\n<k> row(s) have no draft: the AI writes one and it is
                    sent WITHOUT your review.\n\nSending hours and the gap are ignored.
                    Mailbox daily limits still apply.[\n\nSkipped: ...]
  queued, started:  <n> row(s) queued.\n\nSending started. The rows turn "Sent" in about 2
                    minutes (AUTOMATION > Mail > Show send-now results).
  queued, not started: <n> row(s) queued.\n\nCould not start the mail tool right now
                    (<HTTP code: message>).\nThey will be sent by the next scheduled run
                    (every 5 min, 10:00-18:00 Mon-Sat), or use AUTOMATION > Mail > Show
                    send-now results to try again.

MAIL > Show send-now results
  none yet:         Nothing has been sent with "Send mail to selected rows" yet.
  list:             Latest send-now requests (newest first)\n\nSB row 5 (a@x.com): Sent ...
                    (12 newest)
  with pending (YES/NO): ...\n\n<p> still waiting. Start the mail tool again now?
  after YES:        Started. Check again in about 2 minutes. | Could not start it (<msg>).

MAIL > Add a sending mailbox  (three prompts, then one alert)
  prompt 1 title "Add a sending mailbox (1/3)": Brand code: SB, 99M, 99S, PE or SC
  prompt 2 title "Add a sending mailbox (2/3)": Gmail address to send from:
  prompt 3 title "Add a sending mailbox (3/3)": Emails per day for this mailbox (new
           account: 3; you can change it later in the Mailboxes tab):
  success: <email> added to <code> (daily limit <n>, hourly 1, Stage 1).\n\nOne step left -
           connect the Gmail once (Cloud Shell, in the unpacked mail/ folder):\n
           bash tools/connect_gmail.sh <email>\n\nUntil then the mail tool simply skips
           this mailbox.
  errors (prefixed "Nothing added: "): Unknown brand code "<x>" (use SB, 99M, 99S, PE or
           SC). | "<x>" is not an email address. | Daily limit must be between 1 and 50 (new
           Gmail accounts: start with 3). | <email> is already a mailbox (brand <code>).

MAIL > Show mail status (reads the Dashboard tab)
  Mail status\n\nShaadi Bells: 120 sent (4 today), 300 approved waiting, 5 drafts to
  approve, 1 replied, mail on: Yes\n...\nTOTAL: ...\n\nMail runs from this sheet: Yes\n
  Last import: <stamp - summary | never>

WHATSAPP > Send WhatsApp to selected rows  (max = Settings "Max WhatsApp per run", 30)
  not a brand tab:  Open a brand tab (SB, 99M, 99S, PE or SC) and select the rows first.
  brand off:        WhatsApp is OFF for <code> (Limits tab, WhatsApp row, On = No). Nothing
                    sent.
  setup missing:    <code>: fill Phone Number ID, WABA ID and Template name in the WhatsApp
                    Setup tab first.
  no token:         <code>: no access token saved (AUTOMATION > WhatsApp > Save access token).
  confirm (YES/NO): Send WhatsApp template "<name>" NOW to <n> row(s) in <code>?\n\nRow 5:
                    Asha +919876543210 ...\n\nSending hours, the gap and the daily/hourly
                    limits are ignored.[\n\nSkipped: ...]
  busy:             Another WhatsApp run is in progress. Try again in a minute.
  template issues:  <code>: template problem - <msg> | <code>: template status is <STATUS>.
                    Nothing sent. | <code>: template not supported - <reason>
  result:           WhatsApp: <n> sent[, <f> failed\n\nRow 9: <reason> ...][Skipped ...]

WHATSAPP > Save access token
  prompt "Save WhatsApp access token": Paste the permanent access token (one token is used
         by every brand).\nIt is stored privately in this script, not in any cell.
  bad:   That does not look like a token (too short or has spaces). Nothing saved.
  ok:    Token saved (ends with ...<last 4>). Next: AUTOMATION > WhatsApp > Check templates.

WHATSAPP > Check templates: WhatsApp templates\n\nSB: APPROVED - 1 variable(s)\n99M: ...
  per-brand messages: Fill Phone Number ID, WABA ID and Template name | No access token
  saved (WhatsApp > Save access token) | APPROVED - 2 variable(s) - set a column for Var 2 |
  ... - image header: fill Header media URL | Problem: <msg>. The same text is written to
  WhatsApp Setup J (Template check) with the time in K (Checked at).
WHATSAPP > Send now: WhatsApp run finished\n\nSB: off\n99M: 2 sent (test mode: only test
  numbers)\n99S: outside hours 10:00-19:00\nPE: daily limit reached (50) ...
WHATSAPP > Turn automatic sending ON: Automatic WhatsApp sending is ON (every 5 minutes,
  within the Limits tab).\nLive sending: <Yes|No> (No = test numbers only).
WHATSAPP > Turn automatic sending OFF: Automatic WhatsApp sending is OFF.
WHATSAPP > Check reply webhook: see 24.5 for the modal; alerts: Run "Set up reply webhook"
  first. | Number +91 ...: messages go to the business account address https://...  = THIS
  SHEET | ... (not this sheet) | then YES/NO: Send WhatsApp messages to this sheet
  now?\nThe sheet then passes every message on to the current address, so whatever it does
  today keeps working. | result: Messages are passed on to <url>\n<path>: now points to
  this sheet\n\nSend a WhatsApp message to the business number to test.

DASHBOARD > Create access key: if a key exists, YES/NO "A dashboard access key already
  exists. Replace it? The dashboard stops working until you paste the new key into
  Vercel." then the key modal (24.5).
DASHBOARD > Show feed link: Dashboard feed URL (put in Vercel as SHEET_API_URL):\n\n<url>
  | or: The feed is not deployed yet: Extensions > Apps Script > Deploy > New deployment >
  Web app (Execute as: Me, Access: Anyone).

Done when: every string above appears in the code, each dialog has been opened once in a
test copy of the sheet, and the offline tests (common/test) assert the key ones.
```

### 24.5 HtmlService modals and sidebars

```text
Use plain ui.alert / ui.prompt wherever possible: they look native, need no HTML and work on
every browser. Use an HtmlService modal only when the person must COPY a long value, because
alert text cannot be selected reliably. The reference has two modals:

1. "Dashboard access key" (dbCreateKey), 460 x 170:
   <div style="font-family:Arial;font-size:13px">Copy this key into Vercel as
   <b>SHEET_API_KEY</b>. It is shown only now.<br><br>
   <textarea style="width:100%;height:60px" readonly onclick="this.select()">KEY</textarea>
   </div>
   The key (two UUIDs without dashes = 64 hex characters) is saved in Script Properties
   (DASH_KEY) before the modal opens. Closing the modal is the only way out; there is no
   "show key again" item, by design.

2. "WhatsApp reply webhook" (waSetupWebhook), 520 x 330: one sentence of where to paste
   (Meta developer app > WhatsApp > Configuration > Webhook > Edit, then Verify and save),
   a privacy line ("Keep them private (anyone with the URL could post fake replies into the
   sheet)."), a read-only textarea "Callback URL" holding <live /exec URL>?key=<hook key>,
   a read-only textarea "Verify token", and a closing line: "Webhook fields: messages must
   be Subscribed. Replies then appear in the brand tabs (columns V-X) and in the tab
   'WhatsApp Replies'." The URL is the stored live deployment URL (Script Property
   WEBAPP_URL), never ScriptApp.getService().getUrl(), which returned a test URL that Meta
   could not reach.

Modal design rules:
- Arial 13 px, line-height 1.5, no colours, no CSS frameworks, no external scripts or fonts.
- Read-only <textarea> with onclick="this.select()" for anything to copy; width 100%.
- Escape every inserted value (& and <) even though they are generated by the script.
- The dialog title (second argument of showModalDialog) names the thing, not the action.
- Size the modal so nothing scrolls at 100% zoom on a laptop.

Sidebars: the reference uses none, and the rebuild should not add one by default. A sidebar
is worth it only for a repeated, multi-field task (for example a future "Add a lead" form for
phone users). If you build one: HtmlService.createHtmlOutputFromFile('Sidebar')
.setTitle('<Short name>'), 300 px wide, google.script.run calls with a success and failure
handler each, a visible "Working…" state, the same copy rules as dialogs, and the same input
validation as the menu functions (reuse the *Core_ functions such as mlAddMailboxCore_).

Done when: both modals open from the menu, their values can be copied with one click and
Ctrl/Cmd+C, and no modal contains a secret other than the one it exists to hand over once.
```

### 24.6 Tabs: order, visibility, colours

```text
"Set up / repair tabs" (ccSetup) creates missing tabs and then orders them (ccOrderTabs_):

  1 Dashboard          in-sheet summary (24.9); opened on every repair
  2-6 SB, 99M, 99S, PE, SC   one lead tab per brand (24.7), named by brand code
  7 Limits             on/off, caps, gap, hours per brand and channel
  8 Mailboxes          per-Gmail limits and status
  9 WhatsApp Setup     Meta ids, template, variables, header media per brand
 10 Do Not Contact     shared suppression list
 11 WhatsApp Log       one row per WhatsApp send attempt (written by code)
 12 WhatsApp Replies   one row per customer message (written by the webhook)
 13 Settings           key / value / notes

Hidden technical tabs (created hidden, never shown in the order above):
  Mail Control <code>  settings rows A1:C10 (formulas from Limits) and mailbox rows 13+
  Mail Log <code>      the mail sender's log (A:I)
  Mail Send Now        queue for "Send mail to selected rows"
  Old drafts (backup)  created by the draft regeneration tool before any draft is rewritten
  OLD - <name>         tabs from an earlier sheet version, renamed and hidden, never deleted
Tell the owner: hidden tabs are under View > Hidden sheets (or the tab list menu). They can
be looked at but should not be edited by hand.

Tab colours: the reference sets none. Rebuild: colour the five brand tabs with the same
colours as the dashboard (SB #2a78d6, 99M #eb6834, 99S #1baf7a, PE #eda100, SC #e87ba4) via
sheet.setTabColor(), leave the control tabs uncoloured and colour Dashboard dark grey
(#52514e). Same brand, same colour, everywhere. Set colours only in ccSetup so repair
restores them.

Retiring old tabs: ccSetup renames earlier-version tabs (Dashboard, Brands, Settings, Mail,
WhatsApp, SMS, WA Templates, SMS Templates, Send Log, Tasks, Untitled) to "OLD - <name>"
unless they carry the A1 note "Automation Control Center" (which marks the current
Dashboard and Settings), then hides them at the very end, because a spreadsheet must always
keep at least one visible tab.

Done when: after "Set up / repair tabs" the visible tabs are exactly the 13 above in that
order, the technical tabs are hidden, and running it a second time changes nothing.
```

### 24.7 Brand tab layout, formats and dropdowns

```text
Each brand tab (SB, 99M, 99S, PE, SC) has the same 24 columns, A to X.

Row 1: A1 "From", C1 the brand name ("Shaadi Bells"). Only written when A1 is empty.
Row 2: headers, bold, background #f3f4f6, with coloured bands that group the columns:
  A Person / Company            B Email                  C Details (optional, used by AI)
  D Subject (auto)              E Email draft (auto)     F Email status
  G Sent at                     H Error                  I Sent from
  J Approve email (Yes)         K Gmail message ID       L Follow-up
  M Replied            ┐ band #e8f5e9 (light green: "what came back")
  N Replied at         ┘
  O Phone              ┐
  P Send WhatsApp (Yes)│
  Q WhatsApp consent (Yes)  band #e0f2f1 (light teal: WhatsApp inputs and send result)
  R WhatsApp status    │
  S WhatsApp sent at   │
  T WhatsApp message ID / error ┘
  U WhatsApp delivery  ┐
  V WhatsApp replied   │ band #e8f5e9 (written by the reply webhook)
  W WhatsApp replied at│
  X WhatsApp last reply┘
Rows 3+: one lead per row. Never insert rows above row 3 and never sort the header rows.

Freeze: 2 rows and 1 column (the header stays, the name stays visible while scrolling right).
Column widths (set only when the tab is created, so people's own widths survive repair):
  A 180, B 230, E 320, O 140 px. Others keep the default 100.
Number format: the whole tab A:X is plain text ("@") when created; on repair U:X are forced
to text (they were added later). Text format keeps phones like 09876543210 intact and stops
"Yes" from being autocorrected.
Dropdowns: J3:J, P3:P, Q3:Q get a Yes/No list (requireValueInList(['Yes','No'], true)) with
setAllowInvalid(true), so a pasted "yes" or blank is accepted (the code compares
case-insensitively) and paste-ins from other sheets never fail.

Who writes what (tell the team): people type A, B, C, J, O, P, Q (and may type "Yes" in J
before a draft exists to auto-approve). The mail tool writes D-I, K, L, M, N. The WhatsApp
sender writes R-T. The webhook writes U-X. Columns marked "(auto)" or written by code should
not be edited, except clearing a Failed status to retry, which the operator guide covers.

Rebuild additions (optional, owner approves first):
- A note on each header cell of an auto column: "Written by the mail tool - do not edit".
- Conditional formatting, subtle, text colour only: F = "Sent" green #006300, F = "Failed"
  or "Bounced" red #d03b3b; R = "Sent" green, R starts with "Failed" red, R = "Waiting (test
  mode)" grey #6f6d68; U starts with "Failed" red, U = "Read" green; M or V = "Yes" bold.
  Apply with SpreadsheetApp.newConditionalFormatRule() in ccSetup, replacing only rules the
  script created (keep a marker in the rule ranges) so people's own rules survive.

Done when: a new brand tab built by ccSetup matches this layout cell for cell, Yes/No
dropdowns appear in J, P and Q from row 3 down, and a pasted 11-digit phone number keeps its
leading zero.
```

### 24.8 Control tabs: Limits, Mailboxes, WhatsApp Setup, Do Not Contact, logs, Settings

```text
All control tabs have bold #f3f4f6 headers in row 1 and row 1 frozen (ccEnsureTab_).

LIMITS  (A Brand | B Channel | C On (Yes/No) | D Max per day | E Max per hour |
         F Minimum gap (minutes) | G Start (HH:MM) | H End (HH:MM) | I Notes)
  Rows 2-6: one Mail row per brand: Yes, blank, blank, 25, 10:00, 18:00,
            "Blank max = only the mailbox limits apply".
  Rows 7-11: one WhatsApp row per brand: No, 50, 10, 2, 10:00, 19:00,
            "Meta also limits new numbers (about 250 new contacts/day)".
  C has a Yes/No dropdown; G:H are text so "10:00" stays text. All nine columns 150 px.
  This is the main switchboard: "turn WhatsApp off for 99S" = set C10 to No.
  The hidden Mail Control tabs read the Mail rows by formula, so editing Limits is enough.

MAILBOXES (Brand | Mailbox | Enabled (Yes/No) | Daily limit | Hourly limit | Warm-up stage |
           Paused (Yes/No) | Sent today (auto) | Last result (auto))
  One row per Gmail sender; defaults Yes, 3, 1, Stage 1, No. H and I are formulas that look
  up the hidden Mail Control tab (do not type there). C and G have Yes/No dropdowns. B is
  260 px wide. New rows come from AUTOMATION > Mail > Add a sending mailbox.

WHATSAPP SETUP (Brand | Phone Number ID | WABA ID | Template name | Language | Var 1 = column
               | Var 2 = column | Var 3 = column | Var 4 = column | Template check |
               Checked at | Header media URL)
  Whole tab text. One row per brand, Language default "en", Var 1 default "A" (the name).
  J and K are written by Check templates. L is a public https link (Google Drive "anyone
  with the link" works; the script converts it to a direct download).

DO NOT CONTACT (Email | Reason | Added At | Brand | Phone)
  Whole tab text, A 260 px. Shared by all brands and both channels. Bounces, unsubscribes and
  WhatsApp STOP replies are added by code; people may add rows by hand.

WHATSAPP LOG (Time | Brand | Row | Phone | Template | Result | Message ID / Error)
  Text. Written only by code; phone masked (9198****210). Do not sort or edit; the sender
  counts today's sends from it for the limits.

WHATSAPP REPLIES (Received at | Brand | Row | Name | Phone | Message | Type | Message ID)
  Text. Written by the webhook, one row per incoming message, de-duplicated by Message ID.
  This is where the team reads replies in the sheet (24.11).

SETTINGS (Setting | Value | Notes), widths 220 / 320 / 520, B is text, A1 carries the note
  "Automation Control Center". Rows: WhatsApp live sending (No, dropdown in B2) · WhatsApp
  test numbers · Graph API version (v26.0) · Default country code (91) · Max WhatsApp per run
  (30) · Old email sheet ID · Mail switched to this sheet · Last import · Automatic WhatsApp
  (Off; written by the menu). Repair adds missing rows and never changes values.

Done when: each tab exists with these headers, defaults appear only in a newly created tab,
and editing Limits C (On) for a brand is reflected in the Dashboard tab's "Mail on" /
"WhatsApp on" columns immediately.
```

### 24.9 The in-sheet Dashboard tab

```text
The first tab gives the same headline numbers without leaving Sheets. ccSetupDashboard_
clears and rebuilds it on every repair, so it must contain formulas only, never hand-typed
data.

Layout:
  A1   "AUTOMATION CONTROL CENTER — live figures from this sheet", bold, 14 pt, with the
       note "Automation Control Center" (marks it as the current Dashboard)
  Row 3 headers (bold, #f3f4f6, wrap): Brand | Code | Leads | Drafts waiting for approval |
       Approved, waiting to send | Emails sent | Emails sent today | Email failed | Replied |
       WhatsApp sent | WhatsApp sent today | WhatsApp failed | Mail on | WhatsApp on
  Rows 4-8: one brand each, formulas (t = 'SB'!, lg = 'Mail Log SB'!):
       Leads                 =COUNTIF(t B3:B,"?*")
       Drafts waiting        =COUNTIFS(t F3:F,"Generated", t J3:J,"<>Yes")
       Approved, waiting     =ARRAYFORMULA(SUM(COUNTIFS(t J3:J,"Yes",
                                t F3:F,{"Generated","Approved","Scheduled"})))
       Emails sent           =COUNTIF(t F3:F,"Sent")
       Emails sent today     =ARRAYFORMULA(SUM((IFERROR(INT(VALUE(lg A2:A)),0)=TODAY())
                                *(lg F2:F="Sent")))
       Email failed          =COUNTIF(t F3:F,"Failed")
       Replied               =COUNTIF(t M3:M,"Yes")
       WhatsApp sent         =COUNTIF(t R3:R,"Sent")
       WhatsApp sent today   same pattern on 'WhatsApp Log' A, B = code, F = "Sent"
       WhatsApp failed       =COUNTIF(t R3:R,"Failed*")
       Mail on / WhatsApp on =Limits!C<mail row> / =Limits!C<whatsapp row>
  Row 9: TOTAL (bold) with =SUM over C..L.
  Rows 11-16: "How to use" (bold) and five numbered lines:
       1. Add leads   In a brand tab (SB, 99M, 99S, PE, SC): name, email, phone, optional
                      details.
       2. Email       The AI writes a draft; set "Approve email" = Yes to send (or set it
                      Yes up front).
       3. WhatsApp    Set "Send WhatsApp" = Yes and "WhatsApp consent" = Yes; the brand
                      template is sent within limits.
       4. Limits      Limits tab: on/off, max per day/hour, gap and hours per brand and
                      channel. Mailboxes tab: per-sender limits.
       5. Never contact  Add the email/phone to "Do Not Contact".
  Widths: A 200, B..N 105. Freeze 3 rows.

These counts are deliberately simpler than the web dashboard (no per-day history, no
delivery). Where they differ (the web "Approved, waiting" excludes Failed rows; the sheet
counts statuses Generated/Approved/Scheduled with J = Yes) the web dashboard is the
reference; say so in the README so nobody reconciles them by hand.
AUTOMATION > Mail > Show mail status reads this tab's rows 4-9 and formats them as text.

Done when: the Dashboard tab shows one row per brand plus TOTAL with live formulas, "Emails
sent today" rises within seconds of a send being logged, and repair rebuilds it without
leaving stray cells.
```

### 24.10 Protections

```text
The reference sheet has no protected ranges: the owner and two or three trusted team members
edit it, and hard protections blocked the script's own writes during early tests. Keep the
sheet editable, but add WARNING-ONLY protections in the rebuild so accidental edits get a
"Are you sure?" prompt while the script (running as the owner) is never blocked:

  range / tab                         why
  Brand tabs rows 1:2                 headers are read by position; a renamed header breaks
                                      nothing in code but confuses people and the repair
  Brand tabs D:I, K:N, R:X (rows 3+)  written by the mail tool, WhatsApp sender and webhook
  Mailboxes H:I                       formulas
  Dashboard (whole tab)               formulas, rebuilt by repair
  Limits A:B, Settings A and C        names the code looks up
  WhatsApp Log, WhatsApp Replies      logs the limits and dashboard count from
  hidden Mail Control / Mail Log tabs counters and logs of the mail tool

Implementation: range.protect().setDescription('Written by AUTOMATION - edit only if you
know why').setWarningOnly(true), created in ccSetup only when a protection with that
description does not exist yet (so repair does not stack duplicates). Never use
removeEditors / full protection without the owner asking: it can lock the owner's own
team out, and the Cloud Run job writes through the Sheets API under its own identity.

Real protection of what matters lives elsewhere: secrets are in Script Properties and Secret
Manager, the dashboard is read-only, sending needs explicit Yes values and passes limits, and
backups exist ("Old drafts (backup)", Google Sheets version history). Remind the owner that
File > Version history > See version history can restore the whole sheet to any earlier
time.

Done when: editing a header or a log cell shows Google's warning prompt, people can still
type leads, approvals and limits without prompts, and the script and the Cloud Run job write
as before.
```

### 24.11 Operator workflows

```text
Write these as short numbered guides in the README (and the handover note). Each one uses
only the sheet and the AUTOMATION menu.

ADD LEADS
 1. Open the brand tab (for example SB). Go to the first empty row below row 2.
 2. Type Person / Company (A), Email (B), optional Details (C: a sentence about them; the AI
    uses it, so only true facts), Phone (O) if you have one.
 3. Paste many at once if you like; paste values only (Ctrl+Shift+V) so formats stay text.
 4. Leave D-I empty. The mail tool writes a draft within its next run (every 5 min,
    10:00-18:00 Mon-Sat). Single-word handles longer than 12 letters get "Hi there," so
    clean the Name column of Instagram-style names and company abbreviations.

APPROVE EMAILS
 1. Read the draft in D (subject) and E (body). Edit the text if you want; your edit is
    what is sent.
 2. Set J "Approve email" to Yes. The sender sends approved rows within limits and hours.
 3. To approve in advance, set J = Yes before a draft exists; the draft is then sent
    without review. Use this only for brands whose drafts you trust.
 4. Do not approve a draft that contains brackets like [Name] or another sender name.
    Clear D and E (leave F blank) so the tool writes a new one, or ask for a regeneration
    run, which backs up the old draft first.

SEND SELECTED EMAILS NOW
 1. In a brand tab, select the rows (up to 25; they can be non-adjacent).
 2. AUTOMATION > Mail > Send mail to selected rows. Read the confirmation (who, how many,
    which have no draft yet), press YES.
 3. About 2 minutes later: AUTOMATION > Mail > Show send-now results. Rows turn "Sent".
    Hours and gap are skipped; mailbox daily limits still apply.

SEND WHATSAPP
 1. The lead needs a phone (O) and WhatsApp consent = Yes (Q). Never set consent without
    real consent.
 2. Automatic: set P "Send WhatsApp" = Yes. With automatic sending ON (AUTOMATION >
    WhatsApp > Turn automatic sending ON) rows go out every 5 minutes within Limits.
 3. Right now: select rows, AUTOMATION > WhatsApp > Send WhatsApp to selected rows, YES.
 4. In test mode (Settings "WhatsApp live sending" = No) only the test numbers receive
    messages; other rows show "Waiting (test mode)". Going live is the owner's decision.
 5. Status lands in R (Sent / Failed / Retry / Opted out / Uncertain), delivery in U.
    "Failed: 131049 ..." means Meta limited marketing messages to that person: not our
    error; do not resend the same day.

READ REPLIES
 - Email replies: column M = Yes and N = time in the brand tab (checked at 10:00 and
   18:00), plus the morning and evening report email, plus the dashboard Mail view.
 - WhatsApp replies: tab WhatsApp Replies (newest at the bottom; use Data > Create a filter
   to filter by Brand), columns V-X in the brand tab, the dashboard WhatsApp view, and the
   "Latest WhatsApp reply" card on the dashboard Home.
 - A reply of STOP adds the number to Do Not Contact automatically.

STOP A BRAND OR A CHANNEL
 - Limits tab: set On (C) to No in the brand's Mail or WhatsApp row. Takes effect on the
   next run (within 5 minutes). Stop all WhatsApp: AUTOMATION > WhatsApp > Turn automatic
   sending OFF.

ADD A MAILBOX, CONNECT THE DASHBOARD, CONNECT REPLIES
 - AUTOMATION > Mail > Add a sending mailbox, then the Cloud Shell command it shows.
 - AUTOMATION > Dashboard > Create access key / Show feed link, then Vercel (23.5).
 - AUTOMATION > WhatsApp > Set up reply webhook, paste into Meta, then Check reply webhook.

Done when: a new team member can add a lead, approve it, send one WhatsApp to a test number
and find the reply, using only these guides, without asking anyone.
```

### 24.12 Copy guidelines for the sheet

```text
Headers
- Say what goes in the column and, for inputs, the value expected: "Approve email (Yes)",
  "On (Yes/No)", "Start (HH:MM)", "Minimum gap (minutes)", "Var 1 = column".
- Mark automatic columns "(auto)" when people might otherwise type in them: "Subject
  (auto)", "Email draft (auto)", "Sent today (auto)", "Last result (auto)".
- Mark optional inputs: "Details (optional, used by AI)".
- Never rename a header that code reads without changing CC.LEAD_HEADERS and running repair:
  headers are rewritten from that list, and the dashboard feed reads by position.

Status words (written by code, read by people, the dashboard and the reports):
  Email status F: Generated · Approved · Scheduled · Sent · Failed · Bounced · Unsubscribed
  WhatsApp status R: Sent · Failed · Retry · Opted out · Uncertain · Do not contact ·
                     Waiting (test mode) · Sending...
  Delivery U: Delivered · Read · Failed: <code> <reason>
  Yes/No columns: exactly "Yes" or "No" (blank means No)
Use one word per state, capitalised, the same in the sheet, dialogs, reports and dashboard.
Adding a status means updating the feed counters (dbLeadStats_), the dashboard copy deck and
the Dashboard tab formulas in the same change.

Notes column text (Limits I, Settings C): one short sentence that answers "what happens if I
change this?" ("No = only the test numbers below receive WhatsApp. Change to Yes to go
live.").

Errors written into cells (H, T): start with the reason a person can act on, keep the
provider's code in brackets, stay under about 150 characters: "Rate limited: ... (code
130429)", "Access token problem: ...", "No clear answer from Meta; check WhatsApp Manager
before resending: ...".

Language: the same plain English as the dashboard (22.14): short, sentence case, no jargon,
no exclamation marks, no emojis, Indian date and time conventions (yyyy-MM-dd HH:mm in cells
for sorting, "29 Sep" on the dashboard).

Done when: a reviewer reading the header rows, the Settings notes and the status words finds
the same vocabulary as the dashboard and the reports, with no state spelled two ways.
```
