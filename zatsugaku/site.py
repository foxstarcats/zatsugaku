"""出力フォルダから、スマホで動画を見て保存・投稿文をコピーできるページ（index.html）を作る。"""

from __future__ import annotations

import html
import json
from pathlib import Path


def build_index(cfg: dict, out_root: Path) -> None:
    cards, listing = [], []
    for day in sorted((p for p in out_root.iterdir() if p.is_dir() and (p / "video.mp4").exists()),
                      reverse=True):
        script = json.loads((day / "script.json").read_text(encoding="utf-8"))
        post = (day / "post.txt").read_text(encoding="utf-8") if (day / "post.txt").exists() else ""
        d = day.name
        listing.append({"date": d, "title": script["title"], "video": f"{d}/video.mp4", "post": post})
        label = f"{d[:4]}/{d[4:6]}/{d[6:]}"
        cards.append(f"""<article>
  <p class="meta">{label} ・ {html.escape(script.get('genre', ''))}</p>
  <h2>{html.escape(script['title'])}</h2>
  <video controls playsinline preload="metadata" src="{d}/video.mp4"></video>
  <div class="btns">
    <a class="btn" href="{d}/video.mp4" download="zatsugaku_{d}.mp4">動画を保存</a>
    <button class="btn" data-copy>投稿文をコピー</button>
  </div>
  <textarea readonly rows="9">{html.escape(post)}</textarea>
</article>""")
    name = html.escape(cfg["channel"]["name"])
    page = f"""<!doctype html>
<html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex">
<title>{name}</title>
<style>
:root{{--bg:#f6f6f3;--fg:#1d1d1f;--muted:#6b6b70;--card:#fff;--accent:#e0504a;--line:#e3e3de}}
@media (prefers-color-scheme:dark){{:root{{--bg:#151517;--fg:#ececef;--muted:#9a9aa2;--card:#212125;--accent:#ff7a70;--line:#34343a}}}}
body{{margin:0;background:var(--bg);color:var(--fg);font:16px/1.7 system-ui,sans-serif}}
main{{max-width:560px;margin:0 auto;padding:24px 16px}}
h1{{font-size:1.4rem;margin:8px 0 4px}} h2{{font-size:1.05rem;margin:0 0 10px}}
article{{background:var(--card);border-radius:14px;padding:16px;margin:16px 0}}
.meta{{color:var(--muted);font-size:.85rem;margin:0}}
video{{width:100%;max-height:70vh;border-radius:10px;background:#000;display:block}}
.btns{{display:flex;gap:8px;margin:12px 0}}
.btn{{flex:1;text-align:center;padding:10px;border-radius:10px;border:0;background:var(--accent);
color:#fff;font:inherit;font-weight:600;text-decoration:none;cursor:pointer}}
textarea{{width:100%;box-sizing:border-box;border:1px solid var(--line);border-radius:10px;padding:8px;
background:transparent;color:inherit;font:13px/1.6 system-ui,sans-serif;resize:vertical}}
</style></head><body><main>
<h1>{name}</h1>
<p class="meta">毎朝自動で作られる雑学ショート動画です。保存して各サービスに投稿してください。</p>
{''.join(cards) or '<p>まだ動画がありません。</p>'}
</main>
<script>
document.querySelectorAll('[data-copy]').forEach(b => b.addEventListener('click', async () => {{
  const t = b.closest('article').querySelector('textarea');
  try {{ await navigator.clipboard.writeText(t.value); }} catch (e) {{ t.select(); document.execCommand('copy'); }}
  b.textContent = 'コピーしました'; setTimeout(() => b.textContent = '投稿文をコピー', 1500);
}}));
</script></body></html>
"""
    (out_root / "index.html").write_text(page, encoding="utf-8")
    # Google ドライブへの自動保存（gas/drive_sync.gs）が読む一覧
    (out_root / "videos.json").write_text(json.dumps(listing, ensure_ascii=False, indent=2),
                                          encoding="utf-8")
    (out_root / ".nojekyll").touch()
