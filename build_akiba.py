#!/usr/bin/env python3
"""
アキバ総研（akiba-souken.com、2024年10月閉鎖）の記事から、索引に入れるものを選んで akiba.js を作る。

元データは fushihara さんのクローラーの配布ファイル（CC0）:
  https://github.com/fushihara/akiba-souken-crawler/releases/tag/release-2024-0928-1950  の articles.json
同じフォルダに articles.json があればそれを使い、なければダウンロードする。

どの記事を入れるかは akiba_selection.json（連載のタグ名と、スタッフインタビューの記事番号）で決める。

使い方:
    py build_akiba.py
"""
import datetime
import json
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "articles.json"
URL = "https://github.com/fushihara/akiba-souken-crawler/releases/download/release-2024-0928-1950/articles.json"
SEL = HERE / "akiba_selection.json"
OUT = HERE / "akiba.js"
JST = datetime.timezone(datetime.timedelta(hours=9))
# コラム系の連載は連載一覧にだけ出し、記事検索には入れない（インタビュー系の連載は両方に出す）
COLUMNS = {"アニメコラム", "中年アニメライターの懐かしアニメ回顧録", "中国オタクのアニメ事情", "犬も歩けばアニメに当たる。",
           "アニメライターが選ぶ厳選アニメ", "編集部レビュー", "編集部感想"}
UMBRELLA = "アニメコラム"  # ほかの連載をまとめた大分類。連載一覧ではほかの連載に入らない記事だけを並べる


def load_articles():
    if not SRC.exists():
        print("articles.json をダウンロードしています…")
        urllib.request.urlretrieve(URL, SRC)
    return json.loads(SRC.read_text(encoding="utf-8"))


def main():
    sel = json.loads(SEL.read_text(encoding="utf-8"))
    tags, ids = sel["series_tags"], set(sel["interview_ids"])
    items, groups = [], {t: [] for t in tags}
    for x in load_articles():
        if x["breadLinks"][0] != sel["category"]:
            continue
        hit = [t for t in tags if t in x["tags"]]
        if not hit and x["articleId"] not in ids:
            continue
        aid = x["articleId"]
        item = {
            "t": x["title"],
            "d": datetime.datetime.fromtimestamp(x["timestampMs"] / 1000, JST).strftime("%Y-%m-%d"),
            "c": "アキバ総研",
            "u": f"https://akiba-souken.com/article/{aid}/",
            # 保存ページはリダイレクトのスクリプトが入っているので、スクリプトを止めた小窓で見る閲覧ページを通す
            "a": f"viewer.html?id={aid}&t={x['iaUrlKey']}" + (f"&n={x['maxPageNumber']}" if x["maxPageNumber"] > 1 else ""),
        }
        if not hit or not set(hit) <= COLUMNS or aid in ids:
            items.append(item)
        named = [t for t in hit if t != UMBRELLA]
        for t in named or hit:
            groups[t].append(item)
    items.sort(key=lambda x: (x["d"], x["t"]), reverse=True)
    series = []
    for t, xs in groups.items():
        if not xs:
            continue
        xs.sort(key=lambda x: (x["d"], x["u"]))
        name = t + "（ほかの連載以外）" if t == UMBRELLA else t
        series.append({"s": "akiba-" + str(len(series)), "n": name, "site": "アキバ総研", "items": xs})
    series.sort(key=lambda g: g["items"][0]["d"])
    OUT.write_text(
        "window.AKIBA_DATA = " + json.dumps(items, ensure_ascii=False, separators=(",", ":")) + ";\n"
        "window.AKIBA_SERIES = " + json.dumps(series, ensure_ascii=False, separators=(",", ":")) + ";\n",
        encoding="utf-8")
    print(f"akiba.js を書き出しました: 記事 {len(items)} 件、連載 {len(series)} 本（{OUT.stat().st_size / 1e6:.1f} MB）")
    for g in series:
        print(f"  {g['n']}: {len(g['items'])} 本")


if __name__ == "__main__":
    main()
