"""今日の雑学ショート動画を1本作る。

使い方:
  python -m zatsugaku.generate                 # 本番（Claude で台本作成 → 音声 → 動画）
  python -m zatsugaku.generate --sample        # サンプル台本で音声と動画だけ試す
  python -m zatsugaku.generate --force         # 今日の分があっても作り直す
  python -m zatsugaku.generate --genre 宇宙     # ジャンルを指定
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import wave
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

from . import render, tts

ROOT = Path(__file__).resolve().parent.parent
JST = timezone(timedelta(hours=9))
MAX_ATTEMPTS = 3


def load_json(path: Path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def save_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def make_script(cfg: dict, genre: str, history: list[str]) -> dict:
    from . import writer

    rejected: list[str] = []
    for attempt in range(1, MAX_ATTEMPTS + 1):
        print(f"台本を作成中...（{attempt}回目, ジャンル: {genre}）")
        script = writer.write_script(cfg, genre, history, rejected)
        print(f"  雑学: {script['topic']}")
        print("事実確認中...")
        check = writer.fact_check(cfg, script)
        print(f"  判定: {check['verdict']} — {check['reason']}")
        if check["verdict"] == "ok":
            script["fact_check"] = check["reason"]
            return script
        rejected.append(f"{script['topic']}（不採用: 正確性に疑問あり）")
    raise RuntimeError("事実確認を通過する台本を作れませんでした")


def post_text(cfg: dict, script: dict) -> str:
    v = cfg["voices"]
    tags = " ".join(dict.fromkeys(script.get("hashtags", []) + cfg["channel"]["hashtags"]))
    return f"""【タイトル】
{script['title']}

【説明文】
{script['description']}

{tags}

---
VOICEVOX:{v['guest']['name']} / VOICEVOX:{v['host']['name']}
イラスト: Noto Emoji (Apache License 2.0)
"""


def finish(cfg: dict, out_root: Path, args) -> None:
    """古い日の動画を整理し、一覧ページを作る（配信サイト用のオプション指定時のみ）。"""
    if args.keep_days > 0:
        days = sorted((p for p in out_root.iterdir() if p.is_dir() and p.name.isdigit()), reverse=True)
        for old in days[args.keep_days:]:
            for f in old.iterdir():
                f.unlink()
            old.rmdir()
            print(f"  古い動画を整理: {old.name}")
    if args.page:
        from . import site

        site.build_index(cfg, out_root)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default=str(ROOT / "output"))
    ap.add_argument("--config", default=str(ROOT / "config.yaml"))
    ap.add_argument("--force", action="store_true", help="今日の分があっても作り直す")
    ap.add_argument("--sample", action="store_true", help="Claude を使わずサンプル台本で試す")
    ap.add_argument("--genre", help="ジャンルを指定（省略時は日替わり）")
    ap.add_argument("--keep-days", type=int, default=0,
                    help="配信サイト用: 最新N日分だけ残し、古い日の動画フォルダを削除する（0=削除しない）")
    ap.add_argument("--page", action="store_true", help="動画一覧ページ（index.html）も作る")
    args = ap.parse_args()

    cfg = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    out_root = Path(args.out_dir)
    out_root.mkdir(parents=True, exist_ok=True)
    engine_url = os.environ.get("VOICEVOX_URL", "http://127.0.0.1:50021")

    now = datetime.now(JST)
    stamp = now.strftime("%Y%m%d")
    day_dir = out_root / stamp
    if (day_dir / "video.mp4").exists() and not args.force:
        print(f"{stamp} の動画は作成済みです（作り直す場合は --force）")
        finish(cfg, out_root, args)
        return 0

    state_path = out_root / "history.json"
    state = load_json(state_path, {"topics": []})

    # 1. 台本
    if args.sample:
        script = load_json(ROOT / "zatsugaku" / "sample_script.json", None)
    else:
        genres = cfg["topics"]["genres"]
        genre = args.genre or genres[now.date().toordinal() % len(genres)]
        script = make_script(cfg, genre, state["topics"])
        script["genre"] = genre
    for line in script["lines"]:
        print(f"  {line['speaker']}: {line['text']}  {line['emoji']}")

    day_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        # 2. 音声
        print("音声を合成中...")
        wav_path = str(Path(tmp) / "voice.wav")
        timings = tts.render_voice(script, cfg, engine_url, wav_path)
        with wave.open(wav_path) as w:
            duration = w.getnframes() / w.getframerate()
        print(f"  長さ {duration:.1f}秒")

        # 3. 動画（一時ファイルに書いてから置き換える。Google ドライブ同期中の書き込み対策）
        print("動画を描画中...")
        tmp_mp4 = str(Path(tmp) / "video.mp4")
        render.render_video(script, timings, wav_path, tmp_mp4, cfg, ROOT, duration)
        (day_dir / "video.mp4").write_bytes(Path(tmp_mp4).read_bytes())

    save_json(day_dir / "script.json", script)
    (day_dir / "post.txt").write_text(post_text(cfg, script), encoding="utf-8")

    if not args.sample:
        state["topics"] = (state["topics"] + [script["topic"]])[-cfg["topics"]["history_size"]:]
        save_json(state_path, state)

    finish(cfg, out_root, args)
    size = (day_dir / "video.mp4").stat().st_size / 1e6
    print(f"完了: {day_dir / 'video.mp4'}（{duration:.1f}秒, {size:.1f}MB）")
    print(f"タイトル: {script['title']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
