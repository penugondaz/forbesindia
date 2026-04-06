import os
import smtplib
import requests
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timezone, timedelta
from bs4 import BeautifulSoup

# ── Config from GitHub Secrets ──────────────────────────────────────────────
GMAIL_USER         = os.environ["GMAIL_USER"].strip()
GMAIL_APP_PASSWORD = os.environ["GMAIL_APP_PASSWORD"].strip()
TO_EMAILS          = [e.strip() for e in os.environ["TO_EMAIL"].split(",")]

# ── Date in IST ──────────────────────────────────────────────────────────────
IST = timezone(timedelta(hours=5, minutes=30))
today = datetime.now(IST)
date_str   = today.strftime("%A, %d %B %Y")
date_param = today.strftime("%Y-%m-%d")  # e.g. 2026-04-06
date_mc    = today.strftime("%d-%m-%Y")  # Moneycontrol format e.g. 06-04-2026

URL = "https://www.moneycontrol.com/economic-calendar/"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.moneycontrol.com/economic-calendar/",
}

IMPACT_MAP = {"1": "⭐", "2": "⭐⭐", "3": "⭐⭐⭐"}

def scrape_india_events():
    # Try multiple known Moneycontrol API endpoints
    api_attempts = [
        f"https://www.moneycontrol.com/mc/widget/basiceconomiccalendar/get_economic_data?country=IND&start_date={date_param}&end_date={date_param}",
        f"https://www.moneycontrol.com/mc/widget/basiceconomiccalendar/get_economic_data?country=IND&date={date_mc}",
        f"https://www.moneycontrol.com/economic-calendar/index.php?country=IND&date={date_mc}",
    ]

    for api_url in api_attempts:
        try:
            resp = requests.get(api_url, headers=HEADERS, timeout=15)
            resp.raise_for_status()
            ct = resp.headers.get("Content-Type", "")
            if "json" in ct:
                data = resp.json()
                items = data if isinstance(data, list) else data.get("data", data.get("result", data.get("events", [])))
                if items:
                    events = []
                    for item in items:
                        events.append({
                            "time":      item.get("time", item.get("event_time", "–")),
                            "event":     item.get("event_name", item.get("event", item.get("name", "–"))),
                            "impact":    IMPACT_MAP.get(str(item.get("impact", item.get("importance", ""))), "–"),
                            "actual":    item.get("actual", "–") or "–",
                            "previous":  item.get("previous", "–") or "–",
                            "consensus": item.get("consensus", item.get("forecast", "–")) or "–",
                        })
                    return events, None
        except Exception:
            continue

    # Final fallback: scrape the HTML page and filter by today's IST date
    try:
        resp = requests.get(URL, headers=HEADERS, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        return [], f"Failed to fetch page: {e}"

    soup = BeautifulSoup(resp.text, "html.parser")

    # Look for today's date header in the page
    today_display = today.strftime("%-d %B %Y")   # e.g. "6 April 2026"
    today_display2 = today.strftime("%B %-d, %Y") # e.g. "April 6, 2026"

    all_rows = soup.find_all("tr")
    in_today = False
    events = []

    for row in all_rows:
        row_text = row.get_text(" ", strip=True)

        # Check if this row is a date header matching today
        if today_display in row_text or today_display2 in row_text or date_str in row_text:
            in_today = True
            continue

        # Stop if we hit another date header (tomorrow's section)
        if in_today:
            cells = row.find_all("td")
            if not cells:
                th = row.find("th")
                if th:
                    break
                continue

            if len(cells) < 5:
                continue

            if "IND" not in row_text and "India" not in row_text:
                continue

            try:
                stars = cells[3].find_all("i") if len(cells) > 3 else []
                filled = sum(1 for s in stars if "fill" in s.get("class", []))
                impact = "⭐" * filled if filled else cells[3].get_text(strip=True) if len(cells) > 3 else "–"

                events.append({
                    "time":      cells[0].get_text(strip=True),
                    "event":     cells[2].get_text(strip=True),
                    "impact":    impact,
                    "actual":    cells[4].get_text(strip=True) if len(cells) > 4 else "–",
                    "previous":  cells[5].get_text(strip=True) if len(cells) > 5 else "–",
                    "consensus": cells[6].get_text(strip=True) if len(cells) > 6 else "–",
                })
            except Exception:
                continue

    # If date-anchored search found nothing, fall back to any IND rows
    if not events:
        for row in all_rows:
            cells = row.find_all("td")
            if len(cells) < 5:
                continue
            row_text = row.get_text(" ", strip=True)
            if "IND" not in row_text and "India" not in row_text:
                continue
            try:
                stars = cells[3].find_all("i") if len(cells) > 3 else []
                filled = sum(1 for s in stars if "fill" in s.get("class", []))
                impact = "⭐" * filled if filled else cells[3].get_text(strip=True) if len(cells) > 3 else "–"
                events.append({
                    "time":      cells[0].get_text(strip=True),
                    "event":     cells[2].get_text(strip=True),
                    "impact":    impact,
                    "actual":    cells[4].get_text(strip=True) if len(cells) > 4 else "–",
                    "previous":  cells[5].get_text(strip=True) if len(cells) > 5 else "–",
                    "consensus": cells[6].get_text(strip=True) if len(cells) > 6 else "–",
                })
            except Exception:
                continue

    return events, None

# ── Build Email ───────────────────────────────────────────────────────────────
def build_html(events, error=None):
    rows_html = ""

    if error:
        rows_html = f'<tr><td colspan="6" style="color:red;padding:12px">{error}</td></tr>'
    elif not events:
        rows_html = '<tr><td colspan="6" style="padding:12px;color:#666">No India events scheduled for today.</td></tr>'
    else:
        for e in events:
            rows_html += f"""
            <tr>
              <td style="padding:8px 12px;border-bottom:1px solid #eee">{e['time']}</td>
              <td style="padding:8px 12px;border-bottom:1px solid #eee">{e['event']}</td>
              <td style="padding:8px 12px;border-bottom:1px solid #eee;text-align:center">{e['impact']}</td>
              <td style="padding:8px 12px;border-bottom:1px solid #eee;text-align:center">{e['actual']}</td>
              <td style="padding:8px 12px;border-bottom:1px solid #eee;text-align:center">{e['previous']}</td>
              <td style="padding:8px 12px;border-bottom:1px solid #eee;text-align:center">{e['consensus']}</td>
            </tr>"""

    return f"""
    <html><body style="font-family:Arial,sans-serif;color:#333;max-width:700px;margin:auto">
      <div style="background:#1a3c6e;color:white;padding:18px 24px;border-radius:8px 8px 0 0">
        <h2 style="margin:0">🇮🇳 India Economic Calendar</h2>
        <p style="margin:4px 0 0;opacity:.8">{date_str}</p>
      </div>
      <table width="100%" cellspacing="0" cellpadding="0"
             style="border:1px solid #ddd;border-top:none;border-radius:0 0 8px 8px;overflow:hidden">
        <thead style="background:#f5f5f5">
          <tr>
            <th style="padding:10px 12px;text-align:left">Time (IST)</th>
            <th style="padding:10px 12px;text-align:left">Event</th>
            <th style="padding:10px 12px">Impact</th>
            <th style="padding:10px 12px">Actual</th>
            <th style="padding:10px 12px">Previous</th>
            <th style="padding:10px 12px">Consensus</th>
          </tr>
        </thead>
        <tbody>{rows_html}</tbody>
      </table>
      <p style="font-size:11px;color:#aaa;margin-top:12px;text-align:center">
        Source: <a href="{URL}" style="color:#aaa">Moneycontrol Economic Calendar</a> &nbsp;|&nbsp; Sent at 9:30 AM IST
      </p>
    </body></html>
    """

# ── Send Email ────────────────────────────────────────────────────────────────
def send_email(subject, html_body):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = GMAIL_USER
    msg["To"]      = ", ".join(TO_EMAILS)
    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        server.sendmail(GMAIL_USER, TO_EMAILS, msg.as_string())
    print("✅ Email sent successfully.")

# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print(f"Fetching India economic calendar for {date_str}...")
    events, error = scrape_india_events()
    print(f"Found {len(events)} India event(s)." if not error else f"Error: {error}")

    count   = len(events)
    subject = f"🇮🇳 India Economic Calendar – {date_str} ({count} event{'s' if count != 1 else ''})"
    html    = build_html(events, error)

    send_email(subject, html)
