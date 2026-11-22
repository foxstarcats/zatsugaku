/**
 * 雑学動画を Google ドライブに自動保存する Google Apps Script。
 *
 * 公開ページ（GitHub Pages）の videos.json を見て、まだ保存していない動画と投稿文を
 * ドライブの FOLDER_PATH に保存します。3時間ごとに自動で動きます。
 *
 * 使い方: script.google.com で新しいプロジェクトを作り、このコードを貼り付けて
 *         関数「setup」を1回だけ実行（初回は Google アカウントの許可が必要）。
 */

const SITE_URL = 'https://foxstarcats.github.io/zatsugaku/';
const FOLDER_PATH = ['01_個人フォルダ', 'Claude', '雑学', '動画'];  // マイドライブからの場所（なければ作成）

/** 最初に1回だけ実行: 3時間ごとの自動実行を登録し、すぐに1回保存する */
function setup() {
  ScriptApp.getProjectTriggers()
    .filter(t => t.getHandlerFunction() === 'syncVideos')
    .forEach(t => ScriptApp.deleteTrigger(t));
  ScriptApp.newTrigger('syncVideos').timeBased().everyHours(3).create();
  syncVideos();
}

/** 新しい動画をドライブに保存する（自動実行される本体） */
function syncVideos() {
  const res = UrlFetchApp.fetch(SITE_URL + 'videos.json?t=' + Date.now(), { muteHttpExceptions: true });
  if (res.getResponseCode() !== 200) {
    console.log('動画一覧を取得できませんでした: ' + res.getResponseCode());
    return;
  }
  const videos = JSON.parse(res.getContentText());
  const props = PropertiesService.getScriptProperties();
  const saved = JSON.parse(props.getProperty('saved') || '[]');  // 保存済みの日付（ドライブで動画を移動・削除しても再保存しない）
  const folder = getFolder_();

  // 古い日付から順に保存する
  videos.slice().reverse().forEach(v => {
    if (saved.indexOf(v.date) >= 0) return;
    const base = v.date + '_' + safeName_(v.title);
    const blob = UrlFetchApp.fetch(SITE_URL + v.video).getBlob().setName(base + '.mp4');
    folder.createFile(blob);
    folder.createFile(base + '_投稿文.txt', v.post, MimeType.PLAIN_TEXT);
    saved.push(v.date);
    props.setProperty('saved', JSON.stringify(saved.slice(-100)));
    console.log('保存しました: ' + base);
  });
}

function getFolder_() {
  let folder = DriveApp.getRootFolder();
  FOLDER_PATH.forEach(name => {
    const it = folder.getFoldersByName(name);
    folder = it.hasNext() ? it.next() : folder.createFolder(name);
  });
  return folder;
}

function safeName_(s) {
  return String(s).replace(/[\\/:*?"<>|\r\n]/g, '_').trim().slice(0, 60);
}
