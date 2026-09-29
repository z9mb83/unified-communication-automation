"""Write reply status into the lead tabs (columns M "Replied" and N "Replied At").

Only columns M and N are ever written; the lead data in A:L is never touched.
A row is marked once and never un-marked, so running this again is harmless.
"""
from __future__ import annotations

REPLIED_COL, REPLIED_AT_COL = "M", "N"
HEADERS = [["Replied", "Replied At"]]


def earliest_replies(replies):
    """{(brand name, lead email): earliest reply time} from report reply items."""
    found = {}
    for reply in replies:
        key = (reply["brand"], reply["sender"].strip().lower())
        if key not in found or reply["time"] < found[key]:
            found[key] = reply["time"]
    return found


def plan_updates(tab, rows, replied, brand_name):
    """rows = lead tab values from A3:N. Returns [(range, values)] for unmarked replied leads."""
    updates = []
    for offset, raw in enumerate(rows):
        row = list(raw) + [""] * max(0, 14 - len(raw))
        email = str(row[1]).strip().lower()
        when = replied.get((brand_name, email))
        if when is None or str(row[12]).strip().lower() == "yes":
            continue
        number = offset + 3
        updates.append((f"'{tab}'!{REPLIED_COL}{number}:{REPLIED_AT_COL}{number}",
                        [["Yes", when.strftime("%d-%b-%Y %H:%M")]]))
    return updates


def mark_replied(brands, replied, sheet_factory):
    """Returns (rows marked, warnings). Never raises for a single brand's failure."""
    marked, warnings, sheets = 0, [], {}
    for brand in brands:
        if not any(key[0] == brand.brand_name for key in replied):
            continue
        try:
            if brand.sheet_id not in sheets:
                sheets[brand.sheet_id] = sheet_factory(brand.sheet_id)
            sheet = sheets[brand.sheet_id]
            tab = brand.lead_tab
            quoted = tab.replace("'", "''")
            props = {s["properties"]["title"]: s["properties"] for s in sheet.spreadsheet_metadata()["sheets"]}[tab]
            grid = props["gridProperties"]
            if grid.get("columnCount", 0) < 14:
                sheet.batch_update([{"appendDimension": {"sheetId": props["sheetId"], "dimension": "COLUMNS",
                                                         "length": 14 - grid.get("columnCount", 0)}}])
            if not any(any(cell for cell in r) for r in sheet.get(f"'{quoted}'!M2:N2")):
                sheet.update(f"'{quoted}'!M2:N2", HEADERS)
            rows = sheet.get(f"'{quoted}'!A3:N{grid['rowCount']}") if grid["rowCount"] >= 3 else []
            updates = plan_updates(quoted, rows, replied, brand.brand_name)
            if updates:
                sheet.batch_values(updates)
                marked += len(updates)
        except Exception as error:  # one brand failing must not stop the others or the report
            warnings.append(f"{brand.brand_name}: could not write reply status ({type(error).__name__}).")
    return marked, warnings


# ----------------------------------------------------------------------------------------------
# Bounces: a lead whose email came back "undeliverable" is marked Bounced (column F, only when it
# is still "Sent") and added once to the shared Do Not Contact tab, so it is never emailed again.

def bounced_leads(bounces):
    """{(brand name, lead email): earliest bounce time}."""
    found = {}
    for item in bounces:
        lead = str(item.get("lead", "")).strip().lower()
        if not lead:
            continue
        key = (item["brand"], lead)
        if key not in found or item["time"] < found[key]:
            found[key] = item["time"]
    return found


def plan_bounce_updates(tab, rows, bounced, brand_name):
    """rows = lead tab values from A3:H. Only rows whose status is exactly 'Sent' are changed."""
    updates = []
    for offset, raw in enumerate(rows):
        row = list(raw) + [""] * max(0, 8 - len(raw))
        when = bounced.get((brand_name, str(row[1]).strip().lower()))
        if when is None or str(row[5]).strip() != "Sent":
            continue
        number = offset + 3
        updates.append((f"'{tab}'!F{number}", [["Bounced"]]))
        updates.append((f"'{tab}'!H{number}", [[f"Bounced {when.strftime('%d-%b-%Y')}: address could not receive mail"]]))
    return updates


def mark_bounced(brands, bounced, sheet_factory):
    """Returns (rows marked, Do Not Contact rows added, warnings). Never raises for one brand."""
    marked, listed, warnings, sheets, dnc_seen = 0, 0, [], {}, {}
    for brand in brands:
        mine = {k: v for k, v in bounced.items() if k[0] == brand.brand_name}
        if not mine:
            continue
        try:
            if brand.sheet_id not in sheets:
                sheets[brand.sheet_id] = sheet_factory(brand.sheet_id)
            sheet = sheets[brand.sheet_id]
            quoted = brand.lead_tab.replace("'", "''")
            rows = sheet.get(f"'{quoted}'!A3:H")
            updates = plan_bounce_updates(quoted, rows, mine, brand.brand_name)
            if updates:
                sheet.batch_values(updates)
                marked += len(updates) // 2
            dnc_tab = brand.suppression_tab.replace("'", "''")
            key = (brand.sheet_id, dnc_tab)
            if key not in dnc_seen:
                dnc_seen[key] = {str(r[0]).strip().lower() for r in sheet.get(f"'{dnc_tab}'!A2:A") if r}
            new = []
            for (_, email), when in sorted(mine.items()):
                if email not in dnc_seen[key]:
                    new.append([email, "Bounced", when.strftime("%Y-%m-%d %H:%M"), brand.lead_tab])
                    dnc_seen[key].add(email)
            if new:
                sheet.append(f"'{dnc_tab}'!A:D", new)
                listed += len(new)
        except Exception as error:
            warnings.append(f"{brand.brand_name}: could not write bounce status ({type(error).__name__}).")
    return marked, listed, warnings
