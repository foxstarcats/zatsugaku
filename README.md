# 1日1雑学（自動生成ショート動画）

毎日1本、**ずんだもん（聞き役）× 四国めたん（解説役）** が雑学を紹介する約30秒の縦長動画（ショート動画向け 1080×1920）を自動で作ります。費用は0円です。

## しくみ

毎朝4時台に GitHub Actions が自動で動きます（PCの電源は不要）。

```
1. Claude（サブスクリプション）が今日のジャンルから雑学を1つ選び、台本を作成
2. Claude が別の視点で事実確認（俗説・あいまいな話は不採用にして作り直し）
3. VOICEVOX で2人の声を合成
4. 背景アニメ・見出し・字幕（キーワード強調）・絵文字イラストを描画して MP4 に書き出し
5. 動画一覧ページを GitHub Pages に公開（直近14日分）
        ↓
スマホでページを開き「動画を保存」→「投稿文をコピー」→ YouTube ショート / TikTok などに投稿
```

## ファイル構成

| ファイル | 役割 |
|---|---|
| `config.yaml` | チャンネル名・声・長さ・ジャンルなどの設定（ここだけ触ればOK） |
| `zatsugaku/writer.py` | Claude で雑学選び・台本作成・事実確認 |
| `zatsugaku/tts.py` | VOICEVOX で音声合成 |
| `zatsugaku/render.py` | 動画の描画と書き出し |
| `zatsugaku/generate.py` | 全体の流れ（メイン） |
| `assets/fonts/` | 字幕フォント（Noto Sans JP） |
| `assets/characters/` | 立ち絵を置くと動画に表示（任意） |
| `assets/bgm/` | BGM を置くと小さく流す（任意） |
| `zatsugaku/site.py` | 動画一覧ページの作成 |
| `gas/drive_sync.gs` | Google ドライブへの自動保存（Apps Script） |
| `.github/workflows/daily.yml` | 毎日の自動実行の設定 |

紹介済みの雑学（重複防止用の `history.json`）は、動画と一緒に `gh-pages` ブランチに保存されます。

---

## セットアップ手順（初回のみ・約10分）

### 1. Claude の認証トークンを発行する
ポッドキャストで発行したトークンをそのまま使えます（期限切れなら作り直し）。新しく作る場合は PowerShell で:

```powershell
claude setup-token
```

`sk-ant-oat...` で始まるトークンをコピーします（他人に見せないこと）。

### 2. GitHub にリポジトリを作る
https://github.com/new で作成（名前の例: `zatsugaku`、**Public**、README などは追加せず空のまま）。
このフォルダの中身をアップロードします（Claude に「プッシュして」と頼めば代行できます）。

### 3. トークンを登録する
リポジトリの **Settings → Secrets and variables → Actions → New repository secret**
- Name: `CLAUDE_CODE_OAUTH_TOKEN`
- Secret: 手順1のトークン

### 4. 初回を手動で実行する
**Actions** タブ → 左の「Daily zatsugaku video」→「Run workflow」→ 緑のボタン（5分ほどで完了）

### 5. GitHub Pages を有効にする
**Settings → Pages** → Source: 「Deploy from a branch」→ Branch: **`gh-pages`** / `(root)` → Save
- 1〜2分後、`https://<ユーザー名>.github.io/<リポジトリ名>/` で動画一覧ページが開けます。スマホのホーム画面に追加しておくと便利です。

### 6. Google ドライブへの自動保存（任意）
新しい動画と投稿文を、ドライブの `01_個人フォルダ/Claude/雑学/動画/` に自動で保存します（Google Apps Script・無料・PC不要）。

1. https://script.google.com →「新しいプロジェクト」（名前の例: 雑学動画の保存）
2. 最初からあるコードを消して、`gas/drive_sync.gs` の中身を貼り付けて保存
3. 上部の関数の選択で **`setup`** を選び「実行」
4. 「権限を確認」→ 自分のアカウント → 「詳細」→「（プロジェクト名）に移動（安全ではないページ）」→「許可」
   - 自分で作ったスクリプトなので表示される通常の警告です
5. 実行ログに「保存しました」と出れば完了。以後は3時間ごとに新しい動画を保存します

ドライブで動画を移動・削除しても、同じ動画が再び保存されることはありません。保存先を変えるときは、コード冒頭の `FOLDER_PATH` を書き換えます。

### 費用
GitHub Actions / Pages（公開リポジトリ）・VOICEVOX は無料、Claude は加入中プランの利用枠内（1日2〜3回の呼び出し）。**追加費用 0円**。

---

## PCで試す（任意）

前提: VOICEVOX インストール済み（起動していなければ自動で起動します）、`claude` にログイン済み。

```powershell
pip install -r requirements.txt
```

```powershell
python -m zatsugaku.generate
```

- `--sample` : Claude を使わずサンプル台本で動画だけ試す
- `--force` : 今日の分を作り直す
- `--genre 宇宙` : ジャンルを指定

1本あたり、台本と事実確認に1〜3分、音声と動画に30秒ほどかかります。PCで作った動画は `output/日付/` に入ります。

Actions の「Run workflow」では、作り直し（force）やジャンル指定もできます。配信時刻は `daily.yml` の `cron`（UTC表記）で変更します。

## カスタマイズ（`config.yaml`）

- 長さ: `target_seconds`
- 声: `speaker_id`（例: 春日部つむぎ=8、青山龍星=13、冥鳴ひまり=14）。キャラクターを変えたら `zatsugaku/writer.py` の口調も合わせて変更
- ジャンル: `genres`（日替わりで順番に使われる）

### 立ち絵・BGM（任意）
- `assets/characters/guest.png`（ずんだもん）と `host.png`（四国めたん）に背景透過の立ち絵を置くと、画面下に表示され、話している方が跳ねます。立ち絵は各配布元の利用規約を確認してください。
- `assets/bgm/` に mp3 などを1つ置くと、音量を下げて流します（DOVA-SYNDROME などフリーBGMの規約を確認）。

## クレジット・注意点

- 投稿時は説明欄に `VOICEVOX:ずんだもん / VOICEVOX:四国めたん` の表記が必要です（post.txt に自動で入ります）。
- 絵文字イラストは Google Noto Emoji（Apache License 2.0）を使用しています。
- 公開リポジトリのため、ページのURLを知っている人は動画を見られます（検索エンジンには載らない設定）。
- 立ち絵やBGMをリポジトリに入れる場合は、再配布してよいか規約を確認してください。
- 事実確認を自動で行いますが、AIの誤りはゼロにはなりません。投稿前に一度目を通すのがおすすめです。
