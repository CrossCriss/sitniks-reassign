import os, sys
os.environ.pop("DEBUG", None)
exec(open("reassign.py").read().split("since = (datetime")[0])
since = (datetime.now(timezone.utc) - timedelta(minutes=int(os.environ.get("WINDOW_MIN", "120")))).isoformat()
target = None
for chat in all_pages("/open-api/chats", 50, startDate=since):
    if "gerasimyuk" in (chat.get("userNickName") or "") + (chat.get("userName") or ""):
        target = chat; break
if not target:
    raise SystemExit("test chat not found")
print("test chat", target["id"], target.get("assignedManagerName"), target.get("assignedManagerId"))
msgs = req("GET", f"/open-api/chats/{target['id']}/messages", params={"limit": 50})["data"]
msgs.sort(key=lambda m: m["createdAt"])
print("history", [(m["createdAt"][5:16], m.get("managerName")) for m in msgs])
prev = next((m["managerName"] for m in reversed(msgs) if m.get("managerName") and m["managerName"] != PUSHER_NAME), None)
print("prev", prev)
cands = [m for m in managers if m["user"]["fullname"] == prev]
if len(cands) == 1:
    mid = cands[0]["id"]
    try:
        req("PUT", f"/open-api/chats/{target['id']}", json={"assignedManagerId": mid})
        after = req("GET", f"/open-api/chats/{target['id']}")
        print("after PUT manager-id", mid, "->", after.get("assignedManagerName"), after.get("assignedManagerId"))
    except Exception as e:
        print("PUT error", e, getattr(e, "response", None) and e.response.text[:300])
else:
    print("candidates", [m["id"] for m in cands])
