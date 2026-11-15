"""タイトルが取れなかった記事・人名の抜けたタイトルを、別の保存ページと見出しの全文で取り直す（GitHub Actions で実行）"""
import json, re, html as H
from concurrent.futures import ThreadPoolExecutor
exec(open("tools/bonet/pages.py", encoding="utf-8").read().split("cdx = json.load")[0])  # key_of, fetch, meta などを借りる

OUT = "tools/bonet/bonet_articles.json"
arts = json.load(open(OUT))
cdx = json.load(open("tools/bonet/cdx.json"))
variants = {}
for e in cdx:
    if "html" in e["mime"]:
        k = key_of(e["url"])
        if k:
            variants.setdefault("/".join(k), []).append(e)

def bad(r):
    t = r["title"]
    return (not t or t in ("Page has moved", "bonet.info") or re.search(r"CREATORS INTERVIEW\s*\d*$", t)
            or re.search(r"^Drawing with", t) and "：" not in t)

def text(s):
    return re.sub(r"\s+", " ", H.unescape(re.sub(r"<[^>]+>", " ", s))).strip()

def full_title(doc):
    cands = [meta(doc, "og:title")]
    for tag in ("h1", "h2"):
        m = re.search(r"<%s[^>]*>(.*?)</%s>" % (tag, tag), doc, re.S | re.I)
        if m:
            cands.append(text(m.group(1)))
    m = re.search(r"<title>(.*?)</title>", doc, re.S | re.I)
    if m:
        cands.append(re.sub(r"\s*[|｜].*$", "", text(m.group(1))))
    cands = [c for c in cands if c and c not in ("Page has moved", "bonet.info") and "bonet" not in c.lower()[:8]]
    return max(cands, key=len) if cands else ""

def work(r):
    kk = r["section"] + "/" + r["slug"]
    tries = []
    for e in sorted(variants.get(kk, []), key=lambda e: e["first"]):
        if "ww" in e["url"].split("//")[1][:4]:
            continue
        tries += [(e["first"], e["url"]), (e["last"], e["url"])]
    for ts, url in dict.fromkeys(tries):
        doc = fetch(ts, url)
        if not doc:
            continue
        t = full_title(doc)
        if t and len(t) > len(r["title"] or "") and not re.search(r"Page has moved", t):
            _, date = parse_article(doc)
            return kk, t, ts, url
    return kk, None, None, None

todo = [r for r in arts if r["section"] in ("interview", "review") and bad(r)]
print("todo", len(todo), flush=True)
byk = {r["section"] + "/" + r["slug"]: r for r in arts}
with ThreadPoolExecutor(4) as ex:
    for i, (kk, t, ts, url) in enumerate(ex.map(work, todo), 1):
        if t:
            byk[kk]["title"], byk[kk]["ts"], byk[kk]["url"] = t, ts, url
        print(f"[{i}/{len(todo)}] {kk} {t}", flush=True)
json.dump(arts, open(OUT, "w"), ensure_ascii=False, indent=0)
