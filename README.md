# Febri・アキバ総研・bonet 記事アーカイブ索引

2026年11月25日に閉鎖されるアニメ情報サイト Febri（febri.jp）の記事を、インターネットアーカイブ（Wayback Machine）の保存ページへのリンクとあわせてまとめた索引です。タイトル・著者名で検索できます。連載（SERIES）とカバーアート、Febri TV は連載一覧（series.html）にまとめています。

- `index.html` … 検索ページ
- `data.js` … 記事一覧（タイトル・日付・分類・著者・アーカイブURL）
- `series.html` / `series.js` … 連載一覧
- `akiba.js` … アキバ総研の記事一覧と連載（`build_akiba.py` で作成）
- `viewer.html` … アキバ総研の保存ページを、リダイレクトのスクリプトを止めて表示する閲覧ページ
- `build_akiba.py` / `akiba_selection.json` … アキバ総研の記事の選び方（元データは fushihara/akiba-souken-crawler の配布ファイル articles.json、CC0）
- `bonet.js` / `build_bonet.py` … bonet（bonet.info、2013〜2016年ごろの日本語版）のインタビューとコラム。元データは `tools/bonet/`（GitHub Actions でインターネットアーカイブの保存ページから集めたもの）
- `build_index.py` … 一覧の作成スクリプト

アキバ総研（2024年10月閉鎖）は、アニメ分類のうちスタッフインタビューと連載コラムだけを収録しています。
bonet は、インタビューとコラム（「アニメの門」など）だけを収録しています。日付に「頃」とあるものは記事番号から推定した日付です。
