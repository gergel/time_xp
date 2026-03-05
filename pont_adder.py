import os
import time
import requests

NOTION_TOKEN = os.environ.get("NOTION_TOKEN")
MAIN_DB_ID = os.environ.get("MAIN_DB_ID")
VAGOK_DB_ID = os.environ.get("VAGOK_DB_ID")

HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
}


# -----------------------
# Notion HTTP helpers
# -----------------------
def notion_post(url: str, payload: dict):
    res = requests.post(url, headers=HEADERS, json=payload)
    if res.status_code != 200:
        print("❗ Notion POST failed:", res.status_code, res.text)
        return None
    return res.json()


def notion_get(url: str):
    res = requests.get(url, headers=HEADERS)
    if res.status_code != 200:
        print("❗ Notion GET failed:", res.status_code, res.text)
        return None
    return res.json()


def notion_patch(url: str, payload: dict):
    res = requests.patch(url, headers=HEADERS, json=payload)
    if res.status_code != 200:
        print("❗ Notion PATCH failed:", res.status_code, res.text)
        return None
    return res.json()


# -----------------------
# VÁGÓK lookup (stable)
# -----------------------
def build_vago_index_by_person_id():
    """
    Build a mapping: notion person_id (user id) -> Vágók page id.

    This avoids unreliable `people.contains` by name.
    Assumes Vágók DB has a People property named exactly: "Person"
    and each row has (at least) one person selected.
    """
    url = f"https://api.notion.com/v1/databases/{VAGOK_DB_ID}/query"
    person_to_page = {}

    has_more = True
    start_cursor = None

    while has_more:
        payload = {}
        if start_cursor:
            payload["start_cursor"] = start_cursor

        data = notion_post(url, payload)
        if not data:
            return {}

        for page in data.get("results", []):
            try:
                people = page["properties"]["Person"]["people"]
                if not people:
                    continue
                pid = people[0].get("id")
                if pid:
                    person_to_page[pid] = page["id"]
            except (KeyError, TypeError, IndexError):
                continue

        has_more = data.get("has_more", False)
        start_cursor = data.get("next_cursor")

    return person_to_page


# -----------------------
# MAIN entries
# -----------------------
def get_main_entries():
    """
    Query MAIN DB for entries that:
    - jóváírva == False
    - jóváírandó pont is not empty

    PLUS (extra criterion requested):
    - "Aki ellenőrzésbe tette 1" People is not empty
      (enforced in Python for robustness)
    """
    url = f"https://api.notion.com/v1/databases/{MAIN_DB_ID}/query"
    payload = {
        "filter": {
            "and": [
                {"property": "jóváírva", "checkbox": {"equals": False}},
                {"property": "jóváírandó pont", "number": {"is_not_empty": True}},
            ]
        }
    }

    data = notion_post(url, payload)
    if not data:
        return []

    results = data.get("results", [])

    filtered = []
    for entry in results:
        try:
            people = entry["properties"]["Aki ellenőrzésbe tette 1"]["people"]
            if people and len(people) > 0:
                filtered.append(entry)
        except (KeyError, TypeError):
            continue

    if not filtered:
        print(
            "ℹ️ 0 results after filtering for non-empty 'Aki ellenőrzésbe tette 1'. "
            f"(raw results={len(results)})"
        )

    return filtered


def get_current_project_points(vago_page_id):
    url = f"https://api.notion.com/v1/pages/{vago_page_id}"
    data = notion_get(url)
    if not data:
        return None
    try:
        return data["properties"]["projekt pont"]["number"]
    except (KeyError, TypeError):
        return None


def update_project_points(vago_page_id, new_total):
    url = f"https://api.notion.com/v1/pages/{vago_page_id}"
    payload = {"properties": {"projekt pont": {"number": new_total}}}
    res = requests.patch(url, headers=HEADERS, json=payload)
    return res.status_code == 200


def mark_as_processed(main_page_id):
    url = f"https://api.notion.com/v1/pages/{main_page_id}"
    payload = {"properties": {"jóváírva": {"checkbox": True}}}
    requests.patch(url, headers=HEADERS, json=payload)


def main():
    print("🔁 Új jóváírás ellenőrzés...")

    # Build vágók index (person_id -> page_id)
    vago_index = build_vago_index_by_person_id()
    if not vago_index:
        print("⚠️ Vágók index üres. Ellenőrizd:")
        print("   - VAGOK_DB_ID jó-e")
        print("   - a Vágók DB-ben a People property neve pontosan 'Person'-e")
        # nem return-ölünk, mert lehet hogy csak üres a DB; de jellemzően itt gond van.

    entries = get_main_entries()
    print(f"📄 Feldolgozandó elemek: {len(entries)}")

    for entry in entries:
        page_id = entry.get("id")

        try:
            person = entry["properties"]["Aki ellenőrzésbe tette 1"]["people"][0]
            person_id = person.get("id")
            person_name = person.get("name")
            points = entry["properties"]["jóváírandó pont"]["number"]
        except (KeyError, IndexError, TypeError):
            print("❗ Hiányos adat, kihagyva.")
            continue

        if not person_id:
            print(f"❗ Hiányzó person_id, kihagyva: {person_name}")
            continue

        vago_id = vago_index.get(person_id)
        if not vago_id:
            print(f"❌ Nincs vágó találat: {person_name} (person_id={person_id})")
            continue

        current_points = get_current_project_points(vago_id)
        if current_points is None:
            print(f"⚠️ Nem tudtam kiolvasni a 'projekt pont'-ot: {person_name}")
            continue

        if points is None:
            print(f"⚠️ Üres jóváírandó pont, kihagyva: {person_name}")
            continue

        new_total = current_points + points
        updated = update_project_points(vago_id, new_total)

        if updated:
            print(f"✅ {person_name} pont frissítve: {current_points} → {new_total}")
            mark_as_processed(page_id)
        else:
            print(f"⚠️ Nem sikerült frissíteni: {person_name}")


if __name__ == "__main__":
    while True:
        main()
        time.sleep(60)
