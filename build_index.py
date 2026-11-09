#!/usr/bin/env python3
"""
Febri (https://febri.jp/) 記事アーカイブ索引づくり

1. febri.jp の記事URLを集める（サイトマップ＋各一覧ページのページ送り）
2. 各記事からタイトル・日付・カテゴリ・本文を取り出す
3. インターネットアーカイブ（Wayback Machine）の保存状況を調べ、最新の保存URLを付ける
4. （任意）未保存の記事を Wayback Machine に保存依頼する
5. 検索ページ用の data.js を書き出す（タイトル・日付・カテゴリ・リンクのみ。本文は含めない）

本文を含む全データは cache/articles.jsonl に残ります（公開リポジトリには入れないこと）。

使い方:
    pip install requests beautifulsoup4
    python build_index.py                 # 収集→アーカイブ照合→data.js
    python build_index.py --save-missing  # 未保存の記事を保存依頼してから data.js

途中で止めても、取得済みの記事は cache/articles.jsonl に残り、再実行時は飛ばします。
"""
import argparse
import json
import re
import sys
import time
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

BASE = "https://febri.jp"
SECTIONS = ["/topics/", "/febritalk/", "/febri_talk/", "/series/", "/tv/"]
# 記事とみなすURL: /<カテゴリ>/<スラッグ>/
ARTICLE_RE = re.compile(r"^/(topics|febri_talk|series|tv)/([^/]+)/(?:[^/]+/)?$")
EXCLUDE_SLUGS = {"page", "list", "feed"}
CATEGORY_NAMES = {
    "topics": "TOPICS",
    "febri_talk": "Febri TALK",
    "series": "SERIES",
    "tv": "Febri TV",
    "febritv": "Febri TV",
    "gppedia": "ガルパン用語辞典",
    "kataribe": "カタリベ",
    "coverart": "カバーアート",
}
# 記事ではないページの種類
EXCLUDE_CATS = {"yahoo_feeds", "contact", "addl", "page", "post", "kataribe", "gppedia"}  # gppedia は用語ごとの空ページ（本体は /series/gppedia/storyNN/）


def is_excluded(url):
    segs = [x for x in urlparse(url).path.split("/") if x]
    if not segs or segs[0] in EXCLUDE_CATS:
        return True
    return segs[0] == "series" and len(segs) == 2  # 連載の目次ページ

HERE = Path(__file__).resolve().parent
CACHE = HERE / "cache"
ARTICLES_JSONL = CACHE / "articles.jsonl"
URLS_TXT = CACHE / "urls.txt"
WAYBACK_JSON = CACHE / "wayback.json"
OUT_JS = HERE / "data.js"
SERIES_JS = HERE / "series.js"  # 連載（SERIES）の各回。記事検索とは別の一覧ページ用

session = requests.Session()
session.headers["User-Agent"] = "Mozilla/5.0 (personal archive index builder)"

DELAY = 1.0  # 1リクエストごとの待ち時間（秒）


def get(url, tries=3, timeout=30, **kw):
    for i in range(tries):
        try:
            r = session.get(url, timeout=timeout, **kw)
            time.sleep(DELAY)
            if r.status_code == 200:
                return r
            if r.status_code == 404:
                return None
        except requests.RequestException as e:
            print(f"  ! {url}: {e}", file=sys.stderr)
        time.sleep(3 * (i + 1))
    return None


def normalize(url):
    """比較用にURLをそろえる（スキーム・www・末尾スラッシュ・クエリを無視）"""
    p = urlparse(url)
    host = p.netloc.lower().removeprefix("www.").split(":")[0]
    path = p.path.rstrip("/") + "/"
    return host + path


def article_path(url, loose=False):
    p = urlparse(urljoin(BASE, url))
    if p.netloc.lower().removeprefix("www.") != "febri.jp":
        return None
    segs = [s for s in p.path.split("/") if s]
    if loose:
        # サイトマップ由来は /<種類>/<スラッグ>/ と /<種類>/<連載>/<回>/ をすべて記事として扱う
        if (2 <= len(segs) <= 3 and not re.search(r"_(tags|cat)$", segs[0])
                and not set(segs[1:]) & EXCLUDE_SLUGS):
            return "/" + "/".join(segs) + "/"
        return None
    m = ARTICLE_RE.match(p.path)
    if not m or set(segs[1:]) & EXCLUDE_SLUGS:
        return None
    return "/" + "/".join(segs) + "/"


# ---------- 1. 記事URLを集める ----------

def urls_from_sitemaps():
    found = set()
    seen = set()
    queue = [BASE + p for p in ("/sitemap.xml", "/sitemap_index.xml", "/wp-sitemap.xml")]
    while queue:
        sm = queue.pop()
        if sm in seen:
            continue
        seen.add(sm)
        r = get(sm)
        if not r or "<loc>" not in r.text:
            continue
        print(f"  sitemap: {sm}")
        for loc in re.findall(r"<loc>\s*(.*?)\s*</loc>", r.text, re.S):
            loc = re.sub(r"^<!\[CDATA\[|\]\]>$", "", loc.strip()).strip()
            loc = loc.replace("&amp;", "&")
            if loc.endswith(".xml") or "sitemap" in loc:
                # タグ・カテゴリ・著者の一覧は記事ではないので読まない
                if not re.search(r"(tags?|category|author)[-_]?sitemap", loc):
                    queue.append(loc)
            else:
                ap = article_path(loc, loose=True)
                if ap:
                    found.add(ap)
    return found


def urls_from_listings():
    found = set()
    for sec in SECTIONS:
        page = 1
        while True:
            url = BASE + sec if page == 1 else f"{BASE}{sec}page/{page}/"
            r = get(url)
            if not r:
                break
            soup = BeautifulSoup(r.text, "html.parser")
            new = 0
            for a in soup.find_all("a", href=True):
                ap = article_path(a["href"])
                if ap and ap not in found:
                    found.add(ap)
                    new += 1
            print(f"  {sec} p.{page}: +{new}（計 {len(found)}）")
            # 次ページへのリンクがなければ終了
            nxt = soup.find("a", href=re.compile(rf"{re.escape(sec)}page/{page + 1}/?$"))
            if not nxt:
                break
            page += 1
    return found


def collect_urls(refresh=False):
    if URLS_TXT.exists() and not refresh:
        urls = [l.strip() for l in URLS_TXT.read_text().splitlines() if l.strip()]
        print(f"記事URL: キャッシュから {len(urls)} 件")
        return urls
    print("記事URLを集めています（サイトマップ）…")
    urls = urls_from_sitemaps()
    print(f"  サイトマップから {len(urls)} 件")
    print("記事URLを集めています（一覧ページ）…")
    urls |= urls_from_listings()
    urls = sorted(urls)
    URLS_TXT.write_text("\n".join(urls) + "\n")
    print(f"記事URL: 合計 {len(urls)} 件")
    return urls


# ---------- 2. 記事の中身 ----------

DATE_RE = re.compile(r"(20\d\d)[./年-](\d{1,2})[./月-](\d{1,2})")
JST = timezone(timedelta(hours=9))
LABELS = r"(?:取材・構成・文|取材・文|構成・文|取材・構成|文|構成|取材|執筆|Text|TEXT)"
CREDIT_RE = re.compile(rf"(?:^|\s){LABELS}\s*[／/：:]\s*\S")


def meta(soup, *names):
    for n in names:
        tag = soup.find("meta", attrs={"property": n}) or soup.find("meta", attrs={"name": n})
        if tag and tag.get("content"):
            return tag["content"].strip()
    return ""


def clean_text(s):
    s = re.sub(r"[ \t　]+", " ", s)
    s = re.sub(r"\n\s*\n+", "\n", s)
    return s.strip()


def parse_article(path, html):
    soup = BeautifulSoup(html, "html.parser")
    for t in soup(["script", "style", "noscript", "iframe", "svg", "form"]):
        t.decompose()

    title = meta(soup, "og:title") or (soup.title.get_text() if soup.title else "")
    h1 = soup.find("h1")
    if h1 and len(h1.get_text(strip=True)) > 3:
        title = h1.get_text(" ", strip=True)
    title = re.sub(r"\s*[|｜–-]\s*Febri.*$", "", title).strip()

    # 日付: メタ情報（UTCなので日本時間に直す） → time要素 → 本文中の YYYY.MM.DD
    date = ""
    raw = meta(soup, "article:published_time", "og:published_time", "date")
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if dt.tzinfo:
            dt = dt.astimezone(JST)
        raw = dt.strftime("%Y-%m-%d")
    except (ValueError, AttributeError):
        pass
    if not raw:
        t = soup.find("time")
        raw = (t.get("datetime") or t.get_text()) if t else ""
    m = DATE_RE.search(raw or "")
    if not m:
        main_guess = soup.find("article") or soup.find("main") or soup
        m = DATE_RE.search(main_guess.get_text(" "))
    if m:
        date = f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"

    # 本文: 記事本文らしい要素を順に試し、だめなら最も文字数の多いブロック
    body_el = None
    for sel in [".entry-content", ".post-content", ".article-body", ".article__body",
                ".single-content", ".content-body", "article", "main"]:
        el = soup.select_one(sel)
        if el and len(el.get_text(strip=True)) > 200:
            body_el = el
            break
    if body_el is None:
        blocks = soup.find_all(["div", "section"])
        body_el = max(blocks, key=lambda b: len(b.find_all("p")), default=soup)
    for t in body_el.select("nav, header, footer, aside, .share, .sns, .related, .ranking"):
        t.decompose()
    body = clean_text(body_el.get_text("\n"))

    # クレジット行（「文／〇〇」「取材・文／〇〇」など）をページ全体から拾う
    page_text = clean_text(soup.get_text("\n"))
    credits = []
    for line in page_text.split("\n"):
        line = line.strip()
        if len(line) <= 80 and CREDIT_RE.search(line) and line not in credits:
            credits.append(line)
        if len(credits) >= 5:
            break

    cat = path.strip("/").split("/")[0]
    return {
        "url": BASE + path,
        "title": title,
        "date": date,
        "cat": CATEGORY_NAMES.get(cat, cat),
        "author_meta": meta(soup, "author", "article:author"),
        "credits": credits,
        "body": body,
    }


def load_cache():
    data = {}
    if ARTICLES_JSONL.exists():
        for line in ARTICLES_JSONL.read_text(encoding="utf-8").splitlines():
            if line.strip():
                d = json.loads(line)
                data[d["url"]] = d
    return data


def fetch_articles(urls):
    data = load_cache()
    todo = [u for u in urls if BASE + u not in data]
    print(f"記事本文: 取得済み {len(data)} 件、残り {len(todo)} 件")
    with ARTICLES_JSONL.open("a", encoding="utf-8") as f:
        for i, path in enumerate(todo, 1):
            r = get(BASE + path)
            if not r:
                print(f"  [{i}/{len(todo)}] 取得失敗 {path}")
                continue
            d = parse_article(path, r.text)
            data[d["url"]] = d
            f.write(json.dumps(d, ensure_ascii=False) + "\n")
            f.flush()
            print(f"  [{i}/{len(todo)}] {d['date']} {d['title'][:40]}")
    return data


# ---------- 3. Wayback Machine 照合 ----------

def wayback_snapshots():
    """febri.jp 配下の保存済みURL（200）と最新タイムスタンプを一括取得"""
    print("Wayback Machine の保存状況を調べています…")
    snaps = load_wayback()
    print(f"  前回までに確認済み {len(snaps)} 種")
    resume = None
    while True:
        params = {
            "url": "febri.jp/",
            "matchType": "prefix",
            "output": "json",
            "fl": "original,timestamp",
            "filter": "statuscode:200",
            "limit": "50000",
            "showResumeKey": "true",
        }
        if resume:
            params["resumeKey"] = resume
        r = None
        for i in range(2):  # 応答がなければ1回だけ再試行して、1件ずつの確認に切り替える
            r = get("https://web.archive.org/cdx/search/cdx", params=params, timeout=120, tries=1)
            if r or i == 1:
                break
            print("  … CDX API が応答しません。30秒待って再試行します")
            time.sleep(30)
        if not r:
            print("  ! CDX API に接続できませんでした（ここまでの結果で続けます）", file=sys.stderr)
            break
        rows = r.json() if r.text.strip() else []
        resume = None
        for row in rows[1:]:
            if len(row) == 1:          # resumeKey 行
                resume = row[0]
                continue
            if not row:
                continue
            orig, ts = row[0], row[1]
            k = normalize(orig)
            if ts > snaps.get(k, ("",))[0]:
                snaps[k] = (ts, orig)
        print(f"  保存済みURL {len(snaps)} 種")
        save_wayback(snaps)
        if not resume:
            break
    return snaps


def load_wayback():
    if WAYBACK_JSON.exists():
        return {k: tuple(v) for k, v in json.loads(WAYBACK_JSON.read_text(encoding="utf-8")).items()}
    return {}


def save_wayback(snaps):
    WAYBACK_JSON.write_text(json.dumps(snaps, ensure_ascii=False), encoding="utf-8")


def check_each(urls, snaps):
    """一覧照合で見つからなかった記事を1件ずつ確かめる（反映遅れ・一覧取得失敗の補い）"""
    todo = [u for u in urls if normalize(u) not in snaps]
    if not todo:
        return snaps
    print(f"未保存と判定された {len(todo)} 件を1件ずつ確かめます…")
    found = 0
    for i, u in enumerate(todo, 1):
        r = get("https://archive.org/wayback/available", params={"url": u}, timeout=60)
        try:
            snap = r.json().get("archived_snapshots", {}).get("closest") if r else None
        except ValueError:
            snap = None
        if snap and snap.get("available") and str(snap.get("status", "200")) == "200":
            snaps[normalize(u)] = (snap["timestamp"], u)
            found += 1
        if i % 50 == 0:
            print(f"  [{i}/{len(todo)}] 保存あり {found} 件")
            save_wayback(snaps)
    save_wayback(snaps)
    print(f"  保存ありと確認できたのは {found} 件")
    return snaps


def save_page_now(url):
    try:
        r = session.get("https://web.archive.org/save/" + url, timeout=120)
        return r.status_code
    except requests.RequestException as e:
        return str(e)


# ---------- 4. 出力 ----------

def nfkc(s):
    return unicodedata.normalize("NFKC", s).lower()


INTERVIEW_TITLE = re.compile(r"インタビュー|に聞く|が語る|語る|対談|鼎談|座談会|トーク|Interview", re.I)
WRITER_RE = re.compile(r"(?:^|\s)文\s*[／/：:]\s*(.+?)(?=\s+\S{1,6}\s*[／/：:]|$)")


def writer_of(d):
    """インタビュー以外の記事の著者名。インタビューと判断したら空文字"""
    creds = d.get("credits")
    if creds is None:  # 旧版で取った記事は本文の先頭からクレジット行を探す
        creds = [l.strip() for l in d.get("body", "").split("\n")[:80]
                 if len(l.strip()) <= 80 and CREDIT_RE.search(l)][:5]
    if INTERVIEW_TITLE.search(d["title"]) or any(re.search(r"取材|構成|聞き手", c) for c in creds):
        return ""
    for c in creds:
        m = WRITER_RE.search(c)
        if m:
            # 「〇〇 バナービジュアル／△△」のように後ろに別の役割が続く場合は切る
            w = re.split(r"\s+\S+?[／/]", m.group(1).strip())[0].strip()
            return re.sub(r"・元.*$", "", w)  # 「菅（Suge）・元〇〇編集部員」→「菅（Suge）」
    return d.get("author_meta", "") if d.get("author_meta", "").lower() not in ("", "admin", "febri") else ""


EXTRA_GROUPS = {"coverart": "カバーアート", "tv": "Febri TV", "febritv": "Febri TV"}


def series_names(data):
    """連載の目次ページ（/series/<連載>/）のタイトルを連載名として集める"""
    names = {}
    for d in data.values():
        segs = [x for x in urlparse(d["url"]).path.split("/") if x]
        if len(segs) == 2 and segs[0] == "series":
            names[segs[1]] = d["title"]
    return names


def write_series(items, names):
    """記事一覧から連載の各回を抜き出して series.js に書き、残りを返す"""
    groups, rest = {}, []
    for x in items:
        segs = [s for s in urlparse(x["u"]).path.split("/") if s]
        if len(segs) == 3 and segs[0] == "series":
            groups.setdefault(segs[1], []).append(x)
        elif segs and segs[0] in EXTRA_GROUPS:  # カバーアート・Febri TV も連載一覧にまとめる
            groups.setdefault(segs[0], []).append(x)
        else:
            rest.append(x)
    out = []
    for slug, xs in groups.items():
        xs.sort(key=lambda x: (x["d"] or "9999", x["u"]))
        out.append({"s": slug, "n": names.get(slug) or EXTRA_GROUPS.get(slug, slug), "items": xs})
    # 連載を先に、カバーアート・Febri TV をあとに。それぞれ始まった順
    out.sort(key=lambda g: (g["s"] in EXTRA_GROUPS, min((x["d"] for x in g["items"] if x["d"]), default="9999")))
    SERIES_JS.write_text("window.SERIES_DATA = " + json.dumps(out, ensure_ascii=False, separators=(",", ":")) + ";\n",
                         encoding="utf-8")
    print(f"series.js を書き出しました: 連載 {len(out)} 本、{sum(len(g['items']) for g in out)} 回")
    return rest


def write_js(data, snaps):
    items = []
    missing = 0
    valid = set(BASE + u for u in collect_urls())
    for d in data.values():
        if d["url"] not in valid or is_excluded(d["url"]):
            continue
        snap = snaps.get(normalize(d["url"]))
        if snap:
            arc = f"https://web.archive.org/web/{snap[0]}/{snap[1]}"
        else:
            arc = ""
            missing += 1
        items.append({
            "t": d["title"],
            "d": d["date"],
            "c": CATEGORY_NAMES.get(d["cat"], d["cat"]),
            "u": d["url"],
            "a": arc,
        })
        w = writer_of(d)
        if w:
            items[-1]["w"] = w
    items = write_series(items, series_names(data))
    items.sort(key=lambda x: (x["d"], x["t"]), reverse=True)
    js = ("// generated by build_index.py " + time.strftime("%Y-%m-%d %H:%M") + "\n"
          "window.FEBRI_DATA = " + json.dumps(items, ensure_ascii=False, separators=(",", ":")) + ";\n")
    OUT_JS.write_text(js, encoding="utf-8")
    mb = OUT_JS.stat().st_size / 1e6
    print(f"\ndata.js を書き出しました: {len(items)} 件（{mb:.1f} MB）、うちアーカイブ未保存 {missing} 件")
    return missing


def main():
    global DELAY
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh-urls", action="store_true", help="記事URLの一覧を取り直す")
    ap.add_argument("--save-missing", action="store_true", help="未保存の記事を Wayback Machine に保存依頼する")
    ap.add_argument("--save-delay", type=float, default=15, help="保存依頼の間隔（秒）")
    ap.add_argument("--delay", type=float, default=1.0, help="febri.jp へのリクエスト間隔（秒）")
    ap.add_argument("--cdx", action="store_true", help="前回の照合結果があっても一覧照合（CDX）をやり直す")
    args = ap.parse_args()
    DELAY = args.delay
    CACHE.mkdir(exist_ok=True)

    urls = collect_urls(args.refresh_urls)
    data = fetch_articles(urls)
    article_urls = [BASE + u for u in urls]
    if WAYBACK_JSON.exists() and not args.cdx:
        # 前回までの照合結果があれば、重い一覧照合（CDX）は飛ばして未保存分だけ確かめる
        snaps = load_wayback()
        print(f"Wayback Machine: 前回までの照合結果 {len(snaps)} 種を使います（一覧照合は省略）")
    else:
        snaps = wayback_snapshots()
    snaps = check_each(article_urls, snaps)

    if args.save_missing:
        todo = [u for u in article_urls if normalize(u) not in snaps]
        print(f"\n未保存 {len(todo)} 件を保存依頼します（{args.save_delay}秒間隔）")
        for i, u in enumerate(todo, 1):
            st = save_page_now(u)
            print(f"  [{i}/{len(todo)}] {st} {u}")
            time.sleep(args.save_delay)
        if todo:
            print("保存結果の反映を待ってから確かめ直します（2分）…")
            time.sleep(120)
            snaps = check_each(article_urls, snaps)

    write_js(data, snaps)


if __name__ == "__main__":
    main()
