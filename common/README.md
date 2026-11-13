# Sheet script — install / repair

The Automation Control Center's Apps Script project has these files:

| Apps Script file | Copy from |
|---|---|
| `Code.gs` | `common/Core.gs` |
| `Mail.gs` | `mail/sheet/Mail.gs` |
| `WhatsApp.gs` | `whatsapp/WhatsApp.gs` |
| `Dashboard.gs` | `common/Dashboard.gs` |
| `Inbox.gs` | `common/Inbox.gs` |
| `LeadEntry.gs` | `common/LeadEntry.gs` (working tabs <BRAND> Mail / <BRAND> WhatsApp; contains the only `onEdit` in the project) |
| `appsscript.json` (Project Settings > show manifest) | `common/appsscript.json` |

1. Sheet > Extensions > Apps Script. Replace each file's content (create `Mail` and `WhatsApp` with + > Script if missing). Save.
2. Reload the sheet. Menu **AUTOMATION > Set up / repair tabs** (allow the permissions the first time).
   It only adds missing tabs and headers; it never deletes lead data. Tabs from the earlier version are renamed `OLD - …` and hidden.
3. Offline tests before pasting a change: `node --test common/test/sheet.test.js`.

## Working tabs (LeadEntry.gs)
- The 10 tabs `SB Mail`, `SB WhatsApp`, ... are made of: yellow entry columns (A-E Mail, A-F WhatsApp), a grey divider,
  a white live list (one FILTER formula in G2 / H2, warning-only protection) and a far-right Yes column (U Mail, T WhatsApp).
- Column positions are constants at the top of `LeadEntry.gs` (`LE.MAIL`, `LE.WA`, `*_ROWREF_COL`, `*_APPROVE_COL`); change them
  together with the sheet layout.
- `leSelection_` lets *Send ... to selected rows* (Mail.gs / WhatsApp.gs) work from the white list (WhatsApp: yellow rows too,
  because the lists line up).
- `leRoom_` adds empty rows to a WhatsApp tab when its white list shows `#REF!` (out of rows).
- Bulk: `leBulkSync` (run once), `leBulkOn` / `leBulkOff` (10-minute trigger).

### Restoring a white list
If a white list breaks (someone typed over its first cell), paste the formula back. For another brand replace every `'SB'`.

`SB Mail`, cell **G2** (headers in G1:T1: Person / Company, Email, Details, Subject, Email draft, Email status, Sent at, Error,
Sent from, Approved, Follow-up, Replied, Replied at, Row in SB tab):
```
=IFNA(FILTER({'SB'!A3:A, 'SB'!B3:B, 'SB'!C3:C, 'SB'!D3:D, 'SB'!E3:E, 'SB'!F3:F, 'SB'!G3:G, 'SB'!H3:H, 'SB'!I3:I, 'SB'!J3:J, 'SB'!L3:L, 'SB'!M3:M, 'SB'!N3:N, ROW('SB'!B3:B)}, LEN(TRIM('SB'!B3:B))>0), "No emails yet")
```
`SB WhatsApp`, cell **H2** (headers in H1:S1: Person / Company, Phone, Send WhatsApp, Consent, WhatsApp status, Sent at,
Message ID / error, Delivery, Replied, Replied at, Last reply, Row in SB tab). Row-by-row with the yellow column B
(matched on the last 10 digits; blank = not in SB, see the yellow Result), then the SB numbers never typed in yellow
(replied first, then sent, then by row). One SB row per number: the one with a reply, else with a WhatsApp status.
Uses binary-search XLOOKUP, so ~170,000 rows recalculate in seconds. Also replace `'SB WhatsApp'` for another brand.
```
=IFNA(ARRAYFORMULA(LET(ph,'SB'!O3:O, k,RIGHT(REGEXREPLACE(TO_TEXT(ph),"\D",""),10), d,FILTER({k,'SB'!A3:A,ph,'SB'!P3:P,'SB'!Q3:Q,'SB'!R3:R,'SB'!S3:S,'SB'!T3:T,'SB'!U3:U,'SB'!V3:V,'SB'!W3:W,'SB'!X3:X,ROW(ph),('SB'!V3:V="Yes")*2+(LEN('SB'!R3:R)>0)},LEN(k)=10), u,SORT(SORTN(SORT(d,14,FALSE,13,TRUE),9^9,2,1,TRUE),1,TRUE), keys,CHOOSECOLS(u,1), yb,'SB WhatsApp'!B2:B, n,IFNA(XMATCH("?*",TO_TEXT(yb),2,-1),0), yk,RIGHT(REGEXREPLACE(TO_TEXT(IF(n>0,ARRAY_CONSTRAIN(yb,MAX(n,1),1),"")),"\D",""),10), blank,MAKEARRAY(1,14,LAMBDA(r,c,"")), al,HSTACK(yk,XLOOKUP(yk,keys,CHOOSECOLS(u,2),"",0,2),XLOOKUP(yk,keys,CHOOSECOLS(u,3),"",0,2),XLOOKUP(yk,keys,CHOOSECOLS(u,4),"",0,2),XLOOKUP(yk,keys,CHOOSECOLS(u,5),"",0,2),XLOOKUP(yk,keys,CHOOSECOLS(u,6),"",0,2),XLOOKUP(yk,keys,CHOOSECOLS(u,7),"",0,2),XLOOKUP(yk,keys,CHOOSECOLS(u,8),"",0,2),XLOOKUP(yk,keys,CHOOSECOLS(u,9),"",0,2),XLOOKUP(yk,keys,CHOOSECOLS(u,10),"",0,2),XLOOKUP(yk,keys,CHOOSECOLS(u,11),"",0,2),XLOOKUP(yk,keys,CHOOSECOLS(u,12),"",0,2),XLOOKUP(yk,keys,CHOOSECOLS(u,13),"",0,2),XLOOKUP(yk,keys,CHOOSECOLS(u,14),"",0,2)), rest,IFNA(FILTER(u,ISNA(XMATCH(keys,SORT(UNIQUE(yk)),0,2))),blank), rs,SORT(rest,14,FALSE,13,TRUE), CHOOSECOLS(VSTACK(al,rs),2,3,4,5,6,7,8,9,10,11,12,13))),"No phone numbers yet")
```
