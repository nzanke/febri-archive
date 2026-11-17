// 「このサイトについて」の中身。今のページの説明を先頭にして、各ページの #aboutbox に入れる
(() => {
  const page = (document.currentScript && document.currentScript.dataset.page) || 'index';
  const S = {
    index: `<h3>記事検索（このページ）</h3>
      <p>主にインタビュー記事を、新しい順に並べています。コラムや連載は <a href="series.html">連載一覧</a> にあります。</p>`,
    series: `<h3>連載一覧（このページ）</h3>
      <p>コラム・連載、Febri のカバーアートと Febri TV を、サイトごと・連載ごとにまとめています。連載名を押すと開き、上の目次から各連載へ飛べます。</p>`,
  };
  const other = {
    index: `<h3>連載一覧</h3><p>コラム・連載、カバーアート、Febri TV は <a href="series.html">連載一覧</a> にまとめています（記事検索には出ません）。</p>`,
    series: `<h3>記事検索</h3><p>インタビュー記事は <a href="index.html">記事検索</a> で題名から探せます。</p>`,
  };
  const common = `
    <h3>検索と絞り込み</h3>
    <ul>
      <li>言葉をスペースで区切ると、すべてを含む記事だけに絞ります（AND）。全角・半角や大文字・小文字は区別しません。</li>
      <li>著者名が出ている記事は、著者名でも見つかります。</li>
      <li>検索欄の横の選択で、サイト・分類ごとに絞れます（「Febri」は TOPICS と Febri TALK の両方）。</li>
      <li>「古い順」で並びを逆にします。200件ずつ表示し、続きは「さらに表示」で出します。</li>
    </ul>
    <h3>表示の見方</h3>
    <ul>
      <li>色付きの札：記事の分類（TOPICS・Febri TALK は Febri、ほかはサイト名）。</li>
      <li>「文／名前」：インタビュー以外の記事の著者。記事から読み取ったもので、正確でないことがあります。</li>
      <li>「未保存」：インターネットアーカイブに保存が見つからない記事。保存の一覧へ飛びます。</li>
      <li>日付の「頃」：bonet の記事で、記事番号から推定した日付。「----.--.--」は日付がわからない記事です。</li>
    </ul>
    <h3>リンク先</h3>
    <p>題名はインターネットアーカイブ（Wayback Machine）の保存ページへのリンクです。アキバ総研の記事は、ほかのサイトから開くとトップページへ飛ばされるため、スクリプトを止めて表示する閲覧ページを通します。「サービスは終了しました」と出たら、閲覧ページの「1か月前の保存を見る」を押してください。</p>
    <h3>集めている記事</h3>
    <ul>
      <li>Febri（febri.jp、2026年11月25日閉鎖）：インタビュー、Febri TALK、連載、コラム、カバーアート、Febri TV</li>
      <li>アキバ総研（akiba-souken.com、2024年10月閉鎖）：アニメ分類のスタッフインタビューと連載・コラム</li>
      <li>bonet（bonet.info、2016年ごろ更新終了）：インタビューとコラム</li>
    </ul>
    <h3>載せていないもの</h3>
    <p>Febri の人物紹介（カタリベ）と用語の単語ページ、アキバ総研のアニメ以外の分類・ニュース・声優インタビュー、bonet のラジオ・イベントレポートなど。</p>
    <h3>出典・連絡先</h3>
    <p>アキバ総研の記事一覧は <a href="https://github.com/fushihara/akiba-souken-crawler" target="_blank" rel="noopener">fushihara さんの収集データ</a>（CC0）によります。掲載内容の削除のご要望などは X（<a href="https://x.com/bg75gf" target="_blank" rel="noopener">@bg75gf</a>）へ。</p>`;
  const html = `<p class="abh">このサイトについて</p>
    <p>閉鎖されたアニメ情報サイトの記事を、インターネットアーカイブの保存ページで読めるようにまとめた索引です。</p>
    ${S[page] || ''}${other[page] || ''}${common}`;
  const fill = () => {
    const box = document.getElementById('aboutbox');
    if (box) box.innerHTML = html;
    // 箱の外を押したら閉じる
    document.addEventListener('click', e => {
      document.querySelectorAll('details.about[open]').forEach(d => { if (!d.contains(e.target)) d.open = false; });
    });
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', fill); else fill();
})();
