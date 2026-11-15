"""bonet.info の保存一覧（CDX）を取って tools/bonet/cdx.json に書く（GitHub Actions で実行）"""
import json, time, urllib.request, urllib.parse, sys

def get(params, tries=3):
    url = "https://web.archive.org/cdx/search/cdx?" + urllib.parse.urlencode(params)
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "archive-index-builder"}), timeout=300) as r:
                return json.loads(r.read().decode() or "[]")
        except Exception as e:
            print("retry", i, e, file=sys.stderr); time.sleep(20)
    return None

rows, resume = [], None
while True:
    p = {"url": "bonet.info", "matchType": "domain", "output": "json",
         "fl": "urlkey,timestamp,original,mimetype,statuscode", "filter": "statuscode:200",
         "limit": "50000", "showResumeKey": "true"}
    if resume: p["resumeKey"] = resume
    d = get(p)
    if d is None: break
    resume = None
    for r in d[1:]:
        if len(r) == 1: resume = r[0]
        elif r: rows.append(r)
    print("rows", len(rows))
    if not resume: break

# URLごとに最初と最後の保存日時をまとめる
byurl = {}
for k, ts, orig, mime, st in rows:
    e = byurl.setdefault(k, {"url": orig, "mime": mime, "first": ts, "last": ts, "n": 0})
    e["first"], e["last"], e["n"] = min(e["first"], ts), max(e["last"], ts), e["n"] + 1
json.dump(sorted(byurl.values(), key=lambda e: e["url"]), open("tools/bonet/cdx.json", "w"), ensure_ascii=False)
print("urls", len(byurl))
