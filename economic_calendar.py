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
GAS_PROXY_URL      = os.environ["GAS_PROXY_URL"].strip()

# ── Date in IST ──────────────────────────────────────────────────────────────
IST = timezone(timedelta(hours=5, minutes=30))
today      = datetime.now(IST)
date_str   = today.strftime("%A, %d %B %Y")
date_param = today.strftime("%Y-%m-%d")

# ── Fetch Events ──────────────────────────────────────────────────────────────
def fetch_india_events():
    proxy_url = f"{GAS_PROXY_URL}?startDate={date_param}&endDate={date_param}"
    try:
        resp = requests.get(proxy_url, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        return [], f"Failed to fetch data: {e}"

    soup = BeautifulSoup(resp.text, "lxml")
    rows = soup.find_all("tr")
    soup = BeautifulSoup(resp.text, "lxml")
    rows = soup.find_all("tr")

    print(f"DEBUG: response length = {len(resp.text)} chars")
    print(f"DEBUG: total <tr> = {len(rows)}")
    print(f"DEBUG: tableData rows = {len([r for r in rows if 'tableData' in (r.get('class') or [])])}")
    print(f"DEBUG: first 500 chars = {resp.text[:500]}")

    IMPACT_MAP = {"1": "⭐", "2": "⭐⭐", "3": "⭐⭐⭐"}

    IMPACT_MAP = {"1": "⭐", "2": "⭐⭐", "3": "⭐⭐⭐"}

    events = []
    for row in rows:
        if "tableData" not in (row.get("class") or []):
            continue

        cols = row.find_all("td")
        if len(cols) < 5:
            continue

        time_text = cols[1].get_text(strip=True)
        if not time_text or ":" not in time_text:
            continue

        link = row.find("a", class_="evt_alink")
        if not link:
            link = row.find("a")
        event_name = link.get_text(strip=True) if link else None
        if not event_name:
            continue

        impact_val = row.get("data-impact", "")
        impact_str = IMPACT_MAP.get(str(impact_val), "–")

        rest_cols = [c.get_text(strip=True) for c in cols[4:]]
        rest_cols = [c for c in rest_cols if c != ""] or rest_cols
        while len(rest_cols) < 3:
            rest_cols.append("–")
        actual, previous, consensus = rest_cols[-3], rest_cols[-2], rest_cols[-1]

        events.append({
            "time":      time_text,
            "event":     event_name,
            "impact":    impact_str,
            "actual":    actual    if actual    else "–",
            "previous":  previous  if previous  else "–",
            "consensus": consensus if consensus else "–",
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
