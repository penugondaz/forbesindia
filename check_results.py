import requests
from bs4 import BeautifulSoup
import json
import os

URL = "https://www.moneycontrol.com/earnings-calendar"
DATA_FILE = "earnings_data.json"

def fetch_data():
    response = requests.get(URL, timeout=20)
    soup = BeautifulSoup(response.text, "html.parser")

    rows = soup.select("table tbody tr")
    results = []

    for row in rows:
        cols = [c.get_text(strip=True) for c in row.find_all("td")]
        if len(cols) >= 3:
            results.append({
                "date": cols[0],
                "company": cols[1],
                "quarter": cols[2]
            })

    return results

def load_old():
    if not os.path.exists(DATA_FILE):
        return []
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def save_new(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

def main():
    new_data = fetch_data()
    old_data = load_old()

    old_keys = {
        f"{i['date']}|{i['company']}|{i['quarter']}"
        for i in old_data
    }

    diff = [
        i for i in new_data
        if f"{i['date']}|{i['company']}|{i['quarter']}" not in old_keys
    ]

    if diff:
        print("NEW_ENTRIES_FOUND")
        for d in diff:
            print(d)

    save_new(new_data)

if __name__ == "__main__":
    main()
