"""Возвращает чат в Sitniks прежнему менеджеру, если ответственной стала пушер."""
import os, time, collections, requests
from datetime import datetime, timedelta, timezone

BASE = "https://crm.sitniks.com"
TOKEN = os.environ["SITNIKS_TOKEN"]
PUSHER_EMAIL = os.environ["PUSHER_EMAIL"].strip().lower()
WINDOW_MIN = int(os.environ.get("WINDOW_MIN") or "15")
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
by_name = collections.defaultdict(list)
for m in managers:
    by_name[m["user"]["fullname"]].append(m["id"])
pusher = next((m for m in managers if (m["user"].get("email") or "").lower() == PUSHER_EMAIL), None)
if not pusher:
    raise SystemExit(f"Менеджер с почтой {PUSHER_EMAIL} не найден")
PUSHER_NAME = pusher["user"]["fullname"]
print(f"Пушер: {PUSHER_NAME}, окно {WINDOW_MIN} мин")

since = (datetime.now(timezone.utc) - timedelta(minutes=WINDOW_MIN)).isoformat()
stats = collections.Counter()
for chat in all_pages("/open-api/chats", 50, startDate=since):
    # ID в списке чатов из другой нумерации, чем /managers, поэтому сверяем по имени
    if chat.get("assignedManagerName") != PUSHER_NAME:
        continue
    stats["у пушера"] += 1
    msgs = req("GET", f"/open-api/chats/{chat['id']}/messages", params={"limit": 50})["data"]
    msgs.sort(key=lambda m: m["createdAt"], reverse=True)
    prev = next((m["managerName"] for m in msgs
                 if m.get("managerName") and m["managerName"] != PUSHER_NAME), None)
    if not prev:
        stats["нет прежнего менеджера"] += 1
        continue
    ids = by_name.get(prev, [])
    if len(ids) != 1:
        stats["имя не уникально или не найдено"] += 1
        print(f"чат {chat['id']}: пропуск, менеджеров с именем '{prev}': {len(ids)}")
        continue
    req("PUT", f"/open-api/chats/{chat['id']}", json={"assignedManagerId": ids[0]})
    stats["возвращено"] += 1
    print(f"чат {chat['id']}: вернули на {prev}")

print("Итог:", dict(stats) or "чатов у пушера нет")
