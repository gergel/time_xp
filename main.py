import os
import time
import requests

NOTION_TOKEN = os.environ.get("NOTION_TOKEN")
TIMER_DB_ID = os.environ.get("TIMER_DB_ID")
VAGOK_DB_ID = os.environ.get("VAGOK_DB_ID")

HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json"
}

def get_timer_entries():
    url = f"https://api.notion.com/v1/databases/{TIMER_DB_ID}/query"
    res = requests.post(url, headers=HEADERS)
    
    data = res.json()
    if "results" not in data:
        print("❌ Nem jött vissza adat:", TIMER_DB_ID)

        return []

    return data["results"]


def get_vago_by_name(name):
    url = f"https://api.notion.com/v1/databases/{VAGOK_DB_ID}/query"
    res = requests.post(url, headers=HEADERS)
    results = res.json().get("results", [])

    for item in results:
        try:
            vago_name = item["properties"]["Person"]["people"][0]["name"]
            if vago_name == name:
                return item["id"]
        except (KeyError, IndexError):
            continue

    return None


def update_timer_entry_with_vago(timer_page_id, vago_page_id):
    url = f"https://api.notion.com/v1/pages/{timer_page_id}"
    payload = {
        "properties": {
            "Vágók": {
                "relation": [{"id": vago_page_id}]
            }
        }
    }
    res = requests.patch(url, headers=HEADERS, json=payload)
    return res.status_code == 200

def main():
    print("🔍 Ellenőrzés indul...")
    timers = get_timer_entries()
    print(f"📋 Talált bejegyzés: {len(timers)}")

    for entry in timers:
        page_id = entry["id"]
        try:
            person = entry["properties"]["Person"]["people"][0]["name"]
        except (KeyError, IndexError):
            print("❗ Nincs megadva személy.")
            continue

        vago_id = get_vago_by_name(person)
        if vago_id:
            success = update_timer_entry_with_vago(page_id, vago_id)
            if success:
                print(f"✅ Kapcsolva: {person}")
            else:
                print(f"⚠️ Nem sikerült frissíteni: {person}")
        else:
            print(f"❌ Nem található vágó: {person}")


if __name__ == "__main__":
    while True:
        main()
        time.sleep(60)
