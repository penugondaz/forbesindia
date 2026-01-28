import requests
from bs4 import BeautifulSoup
import json
import os

URL = "https://www.bseindia.com/corporates/Forth_Results.html"
DATA_FILE = "earnings_data.json"

def fetch_data():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    }

    response = requests.get(URL, headers=headers, timeout=20)
    soup = BeautifulSoup(response.text, "html.parser")

    rows = soup.select("table tr")
    results = []

    for row in rows:
        cols = [c.get_text(strip=True) for c in row.find_all("td")]

        # BSE rows usually have 7 to 9 columns
        if len(cols) >= 5:
            results.append({
                "company": cols[0],
                "quarter": cols[1],
                "date": cols[2],
                "time": cols[3],
                "exchange": "BSE"
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

    old_keys = set()
    for i in old_data:
        old_keys.add(f"{i['company']}|{i['quarter']}")

    diff = []
    for i in new_data:
        key = f"{i['company']}|{i['quarter']}"
        if key not in old_keys:
            diff.append(i)

    if diff:
        print("NEW_ENTRIES_FOUND")
        for d in diff:
            print(d)

    save_new(new_data)


if __name__ == "__main__":
    main()
