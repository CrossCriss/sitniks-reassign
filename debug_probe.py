import os, sys, collections
sys.argv = ["x"]
os.environ.pop("DEBUG", None)
src = open("reassign.py").read().split("since = (datetime")[0]
exec(src)
since = (datetime.now(timezone.utc) - timedelta(minutes=int(os.environ.get("WINDOW_MIN", "60")))).isoformat()
pairs = collections.Counter()
olesya = []
for chat in all_pages("/open-api/chats", 50, startDate=since):
    if chat.get("assignedManagerName"):
        pairs[(chat["assignedManagerName"], chat["assignedManagerId"])] += 1
        if chat["assignedManagerName"] == PUSHER_NAME:
            olesya.append(chat)
for (n, i), c in sorted(pairs.items()):
    print("pair", n, i, c)
for chat in olesya[:5]:
    msgs = req("GET", f"/open-api/chats/{chat['id']}/messages", params={"limit": 30})["data"]
    msgs.sort(key=lambda m: m["createdAt"])
    print("olesya chat", chat["id"], [(m["createdAt"][5:16], m.get("sentBy"), m.get("managerName"), m.get("messageScope")) for m in msgs])
