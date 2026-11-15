#!/usr/bin/env python3
"""
bonet.info（2013〜2016年ごろの日本語版。閉鎖済み）の記事から、インタビューとコラム（レビュー）を選んで bonet.js を作る。
元データは tools/bonet/bonet_articles.json（GitHub Actions で保存ページから集めたもの。tools/bonet/ の cdx.py → pages.py → retry.py）。

- インタビューは記事検索と連載一覧（連載名のあるもの）に、コラムは連載一覧にだけ出す
- 2013年夏の移転で同じ記事が古いURL（animon01 など）と番号のURLに分かれているので、番号のほうに一本化する
- 日付が取れなかった記事（サイドバーの日付 2014-06-06 を拾ったものを含む）は、記事番号から推定して「頃」を付ける
"""
import bisect
import sys
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "tools" / "bonet" / "bonet_articles.json"
OUT = HERE / "bonet.js"
BAD_DATE = "2014-06-06"

SERIES = [  # (連載名, タイトルの決まり, 種類)
    ("アニメのゆくえ201X→", r"^アニメのゆくえ201X", "interview"),
    ("Drawing with Wacom CREATORS INTERVIEW", r"^(Drawing|Sculpting) with ?Wacom", "interview"),
    ("イラストレーターのわ", r"^イラストレーターのわ", "interview"),
    ("ギターを持ったマンガ家の唄", r"ギターを持ったマンガ家の唄", "interview"),
    ("経済特区と本土の狭間で", r"経済特区と本土の狭間で", "interview"),
    ("『たまゆら〜もあぐれっしぶ〜』インタビュー", r"^『たまゆら", "interview"),
    ("藤津亮太のアニメ時評 帰ってきたアニメの門", r"帰ってきたアニメの門", "review"),
    ("藤津亮太のアニメ時評 四代目アニメの門", r"四代目\s*アニメの門|^第\d回：『", "review"),
]
OTHER_COLUMNS = "そのほかのコラム"


def clean(t):
    return re.sub(r"\s+", " ", t or "").strip()


def main():
    rows = json.loads(SRC.read_text(encoding="utf-8"))
    first = {}  # 記事ごとの最初の保存日（日付の推定の上限に使う）
    cdx = HERE / "tools" / "bonet" / "cdx.json"
    if cdx.exists():
        sys.path.insert(0, str(HERE / "tools" / "bonet"))
        src = (HERE / "tools" / "bonet" / "pages.py").read_text(encoding="utf-8").split("cdx = json.load")[0]
        ns = {}; exec(src, ns)
        for e in json.loads(cdx.read_text(encoding="utf-8")):
            k = ns["key_of"](e["url"])
            if k:
                kk = "/".join(k)
                first[kk] = min(first.get(kk, e["first"]), e["first"])
    arts = []
    for r in rows:
        if r["section"] not in ("interview", "review"):
            continue
        t = clean(r["title"])
        if not t or t in ("Page has moved", "bonet.info", "We’re getting things ready") or "bonet.info" in t:
            t = clean(r.get("list_title"))
        if not t or not re.fullmatch(r"\d+|[a-z_]+\d+", r["slug"]):
            continue  # タイトルがわからない記事と、URLの末尾にゴミが付いたもの
        arts.append({**r, "title": t})

    # 古いURL（英字）の記事は、番号の記事に同じ内容があれば落とす
    numeric = [a for a in arts if a["slug"].isdigit()]
    def num(t):
        m = re.search(r"第(\d+)回|INTERVIEW ?0*(\d+)", t)
        return int(m.group(1) or m.group(2)) if m else None
    def series_of(t):
        return next((n for n, rx, sec in SERIES if re.search(rx, t)), None)
    def core(t):
        return re.sub(r"[\s（）()「」『』前後編]", "", t)
    def dup(a):
        if a["slug"].isdigit():
            return False
        for b in numeric:
            if series_of(a["title"]) and series_of(a["title"]) == series_of(b["title"]) and num(a["title"]) == num(b["title"]):
                return True
            if a["slug"].startswith("4animon") and num(a["title"]) == num(b["title"]) and series_of(b["title"]) == "藤津亮太のアニメ時評 四代目アニメの門":
                return True
            if core(a["title"])[:18] and core(a["title"])[:18] in core(b["title"]):
                return True
        return False
    arts = [a for a in arts if not dup(a)]

    # 日付の推定：正しく取れた日付（前後と矛盾しないもの）を目印に、記事番号の間を直線で埋める。
    # インターネットアーカイブに最初に保存された日より後にはしない
    from datetime import date
    def days(d): return date.fromisoformat(d).toordinal()
    pts = sorted((int(a["slug"]), a["date"]) for a in numeric if a["date"] and a["date"] != BAD_DATE)
    good = [p for i, p in enumerate(pts)
            if (i == 0 or pts[i - 1][1] <= p[1]) and (i == len(pts) - 1 or p[1] <= pts[i + 1][1])]
    ids = [p[0] for p in good]
    def estimate(n, ts):
        i = bisect.bisect_left(ids, n)
        if i == 0: d = days(good[0][1])
        elif i >= len(good): d = days(good[-1][1])
        else:
            (x0, d0), (x1, d1) = good[i - 1], good[i]
            d = days(d0) + (days(d1) - days(d0)) * (n - x0) / max(x1 - x0, 1)
        if ts:
            d = min(d, days(f"{ts[:4]}-{ts[4:6]}-{ts[6:8]}"))
        return date.fromordinal(int(d)).isoformat()

    items, groups = [], {}
    for a in arts:
        d, est = a["date"], False
        if (not d or d == BAD_DATE) and a["slug"].isdigit() and good:
            d, est = estimate(int(a["slug"]), first.get(a["section"] + "/" + a["slug"], a["ts"])), True
        item = {"t": a["title"], "d": d, "c": "bonet", "u": a["url"],
                "a": f"https://web.archive.org/web/{a['ts']}/{a['url']}" if a["ts"] else f"https://web.archive.org/web/*/{a['url']}"}
        if est:
            item["e"] = 1  # 推定の日付
        name = next((n for n, rx, sec in SERIES if sec == a["section"] and re.search(rx, a["title"])), None)
        item["_n"] = num(a["title"])
        if a["section"] == "interview":
            items.append(item)
            if name:
                groups.setdefault(name, []).append(item)
        else:
            groups.setdefault(name or OTHER_COLUMNS, []).append(item)

    items.sort(key=lambda x: (x["d"], x["t"]), reverse=True)
    def strip(xs): return [{k: v for k, v in x.items() if k != "_n"} for x in xs]
    series = []
    for name, xs in groups.items():
        xs.sort(key=lambda x: (x["_n"] if x["_n"] is not None else 999, x["d"] or "9999", x["u"]))
        series.append({"s": "bonet-" + str(len(series)), "n": name, "site": "bonet", "items": strip(xs)})
    kind = {n: sec for n, rx, sec in SERIES}
    series.sort(key=lambda g: (kind.get(g["n"], "review") != "interview", g["n"] == OTHER_COLUMNS, g["items"][0]["d"]))
    OUT.write_text("window.BONET_DATA = " + json.dumps(strip(items), ensure_ascii=False, separators=(",", ":")) + ";\n"
                   "window.BONET_SERIES = " + json.dumps(series, ensure_ascii=False, separators=(",", ":")) + ";\n",
                   encoding="utf-8")
    print(f"bonet.js を書き出しました: 記事検索 {len(items)} 件（日付を推定 {sum('e' in x for x in items)} 件）、連載 {len(series)} 本")
    for g in series:
        print(f"  {g['n']}: {len(g['items'])} 本")


if __name__ == "__main__":
    main()
