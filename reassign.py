"""Возвращает чат в Sitniks прежнему менеджеру, если ответственным стал пушер."""
import os, time, requests
from datetime import datetime, timedelta, timezone

BASE = "https://crm.sitniks.com"
TOKEN = os.environ["SITNIKS_TOKEN"]
PUSHER_EMAIL = os.environ["PUSHER_EMAIL"].strip().lower()
WINDOW_MIN = int(os.environ.get("WINDOW_MIN", "15"))
H = {"Authorization": f"Bearer {TOKEN}"}


def req(method, path, **kw):
    for _ in range(5):
        r = requests.request(method, BASE + path, headers=H, timeout=30, **kw)
        if r.status_code == 429:
            time.sleep(65)
            continue
        r.raise_for_status()
        time.sleep(1.1)  # лимит чатов: 10 запросов за 10 секунд
        return r.json() if r.text else None
    raise RuntimeError("Sitniks API: слишком много 429 подряд")


def all_pages(path, limit, **params):
    skip = 0
    while True:
        page = req("GET", path, params={"skip": skip, "limit": limit, **params})
        yield from page["data"]
        skip += limit
        if skip >= page.get("count", 0) or not page["data"]:
            break


managers = list(all_pages("/open-api/managers", 100))
name_to_id = {m["user"]["fullname"]: m["id"] for m in managers}
pusher = next((m for m in managers if (m["user"].get("email") or "").lower() == PUSHER_EMAIL), None)
if not pusher:
    raise SystemExit(f"Менеджер с почтой {PUSHER_EMAIL} не найден")
PUSHER_ID, PUSHER_NAME = pusher["id"], pusher["user"]["fullname"]
if os.environ.get("DEBUG"):
    for m in managers:
        print("debug manager", m["id"], m["user"].get("fullname"),
              {k: v for k, v in m.items() if k not in ("user",)},
              {k: v for k, v in m["user"].items() if k.lower().endswith("id")})
    raise SystemExit(0)
print(f"Пушер: {PUSHER_NAME} (id {PUSHER_ID})")

print(f"Окно с: {(datetime.now(timezone.utc) - timedelta(minutes=WINDOW_MIN)).isoformat()}")
since = (datetime.now(timezone.utc) - timedelta(minutes=WINDOW_MIN)).isoformat()
checked = moved = 0
total = 0
for chat in all_pages("/open-api/chats", 50, startDate=since):
    total += 1
    if os.environ.get("DEBUG"):
        safe = {k: (v if k.lower().endswith(("id", "managername", "at", "status")) else type(v).__name__)
                for k, v in chat.items()}
        print("debug", safe)
    is_pusher = (chat.get("assignedManagerId") == PUSHER_ID
                 or chat.get("assignedManagerName") == PUSHER_NAME)
    if not is_pusher:
        continue
    checked += 1
    msgs = req("GET", f"/open-api/chats/{chat['id']}/messages", params={"limit": 50})["data"]
    msgs.sort(key=lambda m: m["createdAt"], reverse=True)
    prev = next((m["managerName"] for m in msgs
                 if m.get("managerName") and m["managerName"] != PUSHER_NAME
                 and m["managerName"] in name_to_id), None)
    if prev:
        req("PUT", f"/open-api/chats/{chat['id']}", json={"assignedManagerId": name_to_id[prev]})
        moved += 1
        print(f"чат {chat['id']}: вернули на {prev}")

print(f"Чатов за окно: {total}")
print(f"Чатов у пушера: {checked}, возвращено: {moved}")
