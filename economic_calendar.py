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
date_str = today.strftime("%A, %d %B %Y")

# ── Scrape Moneycontrol ──────────────────────────────────────────────────────
URL = "https://www.moneycontrol.com/economic-calendar/"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

def get_star_rating(cell):
    stars = cell.find_all("i")
    filled = sum(1 for s in stars if "fill" in s.get("class", []))
    return "⭐" * filled if filled else "–"

def scrape_india_events():
    try:
        resp = requests.get(URL, headers=HEADERS, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        return [], f"Failed to fetch page: {e}"

    soup = BeautifulSoup(resp.text, "html.parser")
    rows = soup.select("table.calendarTable tbody tr, #economicCalendarTable tbody tr, .econCalTbl tbody tr")

    if not rows:
        rows = soup.find_all("tr")

    events = []
    for row in rows:
        cells = row.find_all("td")
        if len(cells) < 5:
            continue

        text = row.get_text(" ", strip=True)
        if "IND" not in text and "India" not in text:
            continue

        try:
            time_     = cells[0].get_text(strip=True)
            country   = cells[1].get_text(strip=True)
            event     = cells[2].get_text(strip=True)
            impact    = get_star_rating(cells[3]) if cells[3].find("i") else cells[3].get_text(strip=True)
            actual    = cells[4].get_text(strip=True) if len(cells) > 4 else "–"
            previous  = cells[5].get_text(strip=True) if len(cells) > 5 else "–"
            consensus = cells[6].get_text(strip=True) if len(cells) > 6 else "–"

            events.append({
                "time": time_, "country": country, "event": event,
                "impact": impact, "actual": actual,
                "previous": previous, "consensus": consensus,
            })
        except Exception:
            continue

    return events, None

def build_html(events, error=None):
    rows_html = ""

    if error:
        rows_html = f'<tr><td colspan="6" style="color:red;padding:12px">{error}</td></tr>'
    elif not events:
        rows_html = '<tr><td colspan="6" style="padding:12px;color:#666">No India events found for today.</td></tr>'
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
        Source: <a href="{URL}" style="color:#aaa">Moneycontrol Economic Calendar</a> &nbsp;|&nbsp; Sent at 8:00 AM IST
      </p>
    </body></html>
    """

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

if __name__ == "__main__":
    print(f"Fetching economic calendar for {date_str}...")
    events, error = scrape_india_events()
    print(f"Found {len(events)} India event(s)." if not error else f"Error: {error}")

    count   = len(events)
    subject = f"🇮🇳 India Economic Calendar – {date_str} ({count} event{'s' if count != 1 else ''})"
    html    = build_html(events, error)

    send_email(subject, html)
