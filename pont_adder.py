import os
import time
import requests

NOTION_TOKEN = os.environ.get("NOTION_TOKEN")
MAIN_DB_ID = os.environ.get("MAIN_DB_ID")
VAGOK_DB_ID = os.environ.get("VAGOK_DB_ID")

HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json"
}


def get_main_entries():
    url = f"https://api.notion.com/v1/databases/{MAIN_DB_ID}/query"
    payload = {
        "filter": {
            "and": [
                {
                    "property": "jóváírva",
                    "checkbox": {"equals": False}
                },
                {
                    "property": "jóváírandó pont",
                    "number": {"is_not_empty": True}
                }
            ]
        }
    }
    res = requests.post(url, headers=HEADERS, json=payload)

    # DEBUG:
    if res.status_code != 200:
        print("❗ Notion query failed:", res.status_code, res.text)
        return []

    data = res.json()
    results = data.get("results", [])

    # plusz kritérium: "Aki ellenőrzésbe tette 1" ne legyen üres
    filtered = []
    for entry in results:
        try:
            people = entry["properties"]["Aki ellenőrzésbe tette 1"]["people"]
            if people and len(people) > 0:
                filtered.append(entry)
        except (KeyError, TypeError):
            # ha nincs ilyen property / nem people típus, akkor dobjuk
            continue

    if not filtered:
        print(f"ℹ️ 0 results after filtering for non-empty 'Aki ellenőrzésbe tette 1'. (raw results={len(results)})")

    return filtered


"""
def get_main_entries():
   
    url = f"https://api.notion.com/v1/databases/{MAIN_DB_ID}/query"
    payload = {
        "filter": {
            "and": [
                {
                    "property": "jóváírva",
                    "checkbox": {"equals": False}
                },
                {
                    "property": "jóváirandó pont",
                    "number": {"is_not_empty": True}
                },
                {
                    "property": "Aki ellenőrzésbe tette 1",
                    "person": {"is_not_empty": True}
                }
            ]
        }
    }
    res = requests.post(url, headers=HEADERS, json=payload)
    return res.json().get("results", [])

def get_main_entries():
    url = f"https://api.notion.com/v1/databases/{MAIN_DB_ID}/query"
    payload = {
        "filter": {
            "and": [
                {
                    "property": "jóváírva",
                    "checkbox": {"equals": False}
                },
                {
                    "property": "jóváírandó pont",
                    "number": {"is_not_empty": True}
                }
            ]
        }
    }
    res = requests.post(url, headers=HEADERS, json=payload)

    # DEBUG:
    if res.status_code != 200:
        print("❗ Notion query failed:", res.status_code, res.text)
        return []
    data = res.json()
    if not data.get("results"):
        print("ℹ️ 0 results. Notion response:", data)  # vigyázz, hosszú lehet
    return data.get("results", [])
"""
def get_vago_id_by_person_name(name):
    url = f"https://api.notion.com/v1/databases/{VAGOK_DB_ID}/query"
    payload = {
        "filter": {
            "property": "Person",
            "people": {
                "contains": name
            }
        }
    }
    res = requests.post(url, headers=HEADERS, json=payload)
    results = res.json().get("results", [])
    return results[0]["id"] if results else None

def get_current_project_points(vago_page_id):
    url = f"https://api.notion.com/v1/pages/{vago_page_id}"
    res = requests.get(url, headers=HEADERS)
    return res.json()["properties"]["projekt pont"]["number"]

def update_project_points(vago_page_id, new_total):
    url = f"https://api.notion.com/v1/pages/{vago_page_id}"
    payload = {
        "properties": {
            "projekt pont": {
                "number": new_total
            }
        }
    }
    res = requests.patch(url, headers=HEADERS, json=payload)
    return res.status_code == 200

def mark_as_processed(main_page_id):
    url = f"https://api.notion.com/v1/pages/{main_page_id}"
    payload = {
        "properties": {
            "jóváírva": {
                "checkbox": True
            }
        }
    }
    requests.patch(url, headers=HEADERS, json=payload)

def main():
    print("🔁 Új jóváírás ellenőrzés...")
    entries = get_main_entries()
    print(f"📄 Feldolgozandó elemek: {len(entries)}")

    for entry in entries:
        page_id = entry["id"]
        try:
            name = entry["properties"]["Aki ellenőrzésbe tette 1"]["people"][0]["name"]
            points = entry["properties"]["jóváírandó pont"]["number"]
        except (KeyError, IndexError, TypeError):
            print("❗ Hiányos adat, kihagyva.")
            continue

        vago_id = get_vago_id_by_person_name(name)
        if not vago_id:
            print(f"❌ Nincs vágó találat: {name}")
            continue

        current_points = get_current_project_points(vago_id)
        new_total = current_points + points
        updated = update_project_points(vago_id, new_total)

        if updated:
            print(f"✅ {name} pont frissítve: {current_points} → {new_total}")
            mark_as_processed(page_id)
        else:
            print(f"⚠️ Nem sikerült frissíteni: {name}")

if __name__ == "__main__":
    while True:
        main()
        time.sleep(60)
