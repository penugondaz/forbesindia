import os
import smtplib
import requests
from bs4 import BeautifulSoup
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timezone, timedelta

# ── Config from GitHub Secrets ──────────────────────────────────────────────
GMAIL_USER         = os.environ["GMAIL_USER"].strip()
GMAIL_APP_PASSWORD = os.environ["GMAIL_APP_PASSWORD"].strip()
TO_EMAILS          = [e.strip() for e in os.environ["TO_EMAIL"].split(",")]

# ── Date in IST ──────────────────────────────────────────────────────────────
IST = timezone(timedelta(hours=5, minutes=30))
today      = datetime.now(IST)
date_str   = today.strftime("%A, %d %B %Y")
date_param = today.strftime("%Y-%m-%d")

MC_URL = (
    f"https://www.moneycontrol.com/economic-widget"
    f"?duration=&startDate={date_param}&endDate={date_param}"
    f"&impact=&country=India&deviceType=web&classic=true"
)

# ── Fetch Events ──────────────────────────────────────────────────────────────
def fetch_india_events():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Referer": "https://www.moneycontrol.com/economic-calendar",
        "Accept-Language": "en-US,en;q=0.9",
    }
    try:
        resp = requests.get(MC_URL, headers=headers, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        return [], f"Failed to fetch data: {e}"

    soup = BeautifulSoup(resp.text, "lxml")

    # Find all table rows with event data
    rows = soup.select("table tr")
    if not rows:
        # Try alternate selector
        rows = soup.select("tr")

    events = []
    for row in rows:
        cols = row.find_all("td")
        if len(cols) < 4:
            continue

        # Skip header rows
        time_text = cols[0].get_text(strip=True)
        if not time_text or time_text.lower() == "time":
            continue

        # Event name — usually in a link
        event_el = cols[2].find("a") or cols[2]
        event_name = event_el.get_text(strip=True) if event_el else "–"

        # Impact — look for image alt or text
        impact_el = cols[3] if len(cols) > 3 else None
        impact_text = "–"
        if impact_el:
            img = impact_el.find("img")
            if img:
                alt = img.get("alt", "").lower()
                if "high" in alt:   impact_text = "⭐⭐⭐"
                elif "medium" in alt: impact_text = "⭐⭐"
                elif "low" in alt:  impact_text = "⭐"
            else:
                raw = impact_el.get_text(strip=True).lower()
                if "high" in raw:   impact_text = "⭐⭐⭐"
                elif "medium" in raw: impact_text = "⭐⭐"
                elif "low" in raw:  impact_text = "⭐"

        actual    = cols[4].get_text(strip=True) if len(cols) > 4 else "–"
        previous  = cols[5].get_text(strip=True) if len(cols) > 5 else "–"
        consensus = cols[6].get_text(strip=True) if len(cols) > 6 else "–"

        events.append({
            "time":      time_text or "–",
            "event":     event_name or "–",
            "impact":    impact_text,
            "actual":    actual    or "–",
            "previous":  previous  or "–",
            "consensus": consensus or "–",
        })

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
        Source: <a href="https://www.moneycontrol.com/economic-calendar" style="color:#aaa">Moneycontrol Economic Calendar</a>
        &nbsp;|&nbsp; Sent at 9:30 AM IST
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
    events, error = fetch_india_events()
    print(f"Found {len(events)} India event(s)." if not error else f"Error: {error}")

    count   = len(events)
    subject = f"🇮🇳 India Economic Calendar – {date_str} ({count} event{'s' if count != 1 else ''})"
    html    = build_html(events, error)

    send_email(subject, html)
