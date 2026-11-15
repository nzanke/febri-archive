"""bonet.info（日本語版、2013〜2016年ごろ）の記事を、保存ページからタイトル・日付を抜き出して tools/bonet/articles.json に書く
（GitHub Actions で実行。cdx.json が前提）"""
import json, re, time, urllib.request, html as H
from collections import defaultdict

SECTIONS = ("interview", "review", "report", "etc", "news", "radio")
UA = {"User-Agent": "archive-index-builder"}

def path_of(u):
    p = re.sub(r"^https?://[^/]+", "", u).split("?")[0]
    return re.sub(r"^:\d+", "", p)

def key_of(u):
    """記事の識別子（種類, スラッグ）。2ページ目以降や .html、付け足しのゴミは同じ記事にまとめる"""
    host = re.match(r"^https?://([^/:]+)", u).group(1)
    if host.startswith("ww") and host[2:4].isdigit():  # ww25. などはドメイン売却後の駐車ページ
        return None
    m = re.match(r"^/(%s)/([A-Za-z0-9_]+?)(?:\.html)?(?:/\d+)?/?(?:[%%,>].*)?$" % "|".join(SECTIONS), path_of(u))
    if not m or m.group(2) == "page":
        return None
    return m.group(1), m.group(2)

def fetch(ts, url, tries=2):
    for i in range(tries):
        try:
            req = urllib.request.Request(f"https://web.archive.org/web/{ts}id_/{url}", headers=UA)
            with urllib.request.urlopen(req, timeout=30) as r:
                raw = r.read()
            time.sleep(1)
            for enc in ("utf-8", "cp932", "euc-jp"):
                try:
                    return raw.decode(enc)
                except UnicodeDecodeError:
                    pass
            return raw.decode("utf-8", "replace")
        except Exception as e:
            print("  retry", i, url, e)
            time.sleep(5 * (i + 1))
    return None

def meta(doc, prop):
    m = re.search(r'<meta[^>]+(?:property|name)=["\']%s["\'][^>]+content=["\']([^"\']*)' % re.escape(prop), doc, re.I) \
        or re.search(r'<meta[^>]+content=["\']([^"\']*)["\'][^>]+(?:property|name)=["\']%s["\']' % re.escape(prop), doc, re.I)
    return H.unescape(m.group(1)).strip() if m else ""

def parse_article(doc):
    title = meta(doc, "og:title")
    if not title:
        m = re.search(r"<h1[^>]*>(.*?)</h1>", doc, re.S | re.I) or re.search(r"<title>(.*?)</title>", doc, re.S | re.I)
        title = H.unescape(re.sub(r"<[^>]+>", "", m.group(1))).strip() if m else ""
    title = re.sub(r"\s*[|｜]\s*(bonet|ボネット).*$", "", title, flags=re.I).strip()
    date = meta(doc, "article:published_time")[:10]
    if not date:
        m = re.search(r"(20[01]\d)[./年-]\s*(\d{1,2})[./月-]\s*(\d{1,2})", doc)
        date = f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}" if m else ""
    return title, date

def parse_list(doc):
    """一覧ページから記事へのリンクと文字を拾う"""
    out = {}
    for m in re.finditer(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', doc, re.S | re.I):
        href = re.sub(r"^https?://web\.archive\.org/web/\d+(?:id_)?/", "", m.group(1))
        if not href.startswith("http"):
            href = "http://bonet.info" + href if href.startswith("/") else href
        k = key_of(href) if href.startswith("http") else None
        text = H.unescape(re.sub(r"<[^>]+>", "", m.group(2))).strip()
        if k and len(text) >= 6 and (k not in out or len(text) > len(out[k])):
            out[k] = text
    return out

cdx = json.load(open("tools/bonet/cdx.json"))
arts = defaultdict(list)
lists = []
for e in cdx:
    if "html" not in e["mime"] or e["last"] < "2012":
        continue
    k = key_of(e["url"])
    if k:
        arts[k].append(e)
    elif re.match(r"^/(%s|all)(/page/\d+)?/?$" % "|".join(SECTIONS), path_of(e["url"])) and "ww" not in e["url"].split("//")[1][:4]:
        lists.append(e)
print("articles", len(arts), "list pages", len(lists))

# 途中で打ち切られても続きから再開できるように、取れた分を随時書き出す
OUT = "tools/bonet/articles.json"
try:
    result = {"/".join((r["section"], r["slug"])): r for r in json.load(open(OUT)) if r.get("ts")}
except FileNotFoundError:
    result = {}
def save():
    json.dump(sorted(result.values(), key=lambda r: (r["section"], r["slug"])), open(OUT, "w"), ensure_ascii=False, indent=0)
from concurrent.futures import ThreadPoolExecutor

def work(item):
    k, es = item
    # 閉鎖前（2017年より前）で一番新しい保存を優先し、なければ一番古い保存
    pre = [e for e in es if e["first"] < "2017"]
    e = max(pre, key=lambda e: e["first"]) if pre else min(es, key=lambda e: e["first"])
    doc = fetch(e["first"], e["url"])
    title, date = parse_article(doc) if doc else ("", "")
    return "/".join(k), {"section": k[0], "slug": k[1], "url": e["url"], "ts": e["first"], "title": title, "date": date}

todo = [it for it in sorted(arts.items()) if "/".join(it[0]) not in result]
print("todo", len(todo), flush=True)
with ThreadPoolExecutor(4) as ex:  # 4本ずつ同時に読む
    for i, (kk, r) in enumerate(ex.map(work, todo), 1):
        result[kk] = r
        print(f"[{i}/{len(todo)}] {r['date']} {r['title'][:40]}", flush=True)
        if i % 20 == 0:
            save()
save()

found_in_lists = {}
with ThreadPoolExecutor(4) as ex:
    docs = list(ex.map(lambda e: fetch(e["last"], e["url"]), lists))
for i, (e, doc) in enumerate(zip(lists, docs), 1):
    if doc:
        for k, text in parse_list(doc).items():
            kk = "/".join(k)
            if kk not in found_in_lists or len(text) > len(found_in_lists[kk]):
                found_in_lists[kk] = text
    print(f"list [{i}/{len(lists)}] {e['url']}")

for kk, text in found_in_lists.items():
    if kk in result:
        result[kk].setdefault("list_title", text)
    else:
        sec, slug = kk.split("/", 1)
        result[kk] = {"section": sec, "slug": slug, "url": f"http://bonet.info/{kk}", "ts": "", "title": "", "date": "", "list_title": text}

save()
print("total", len(result))
