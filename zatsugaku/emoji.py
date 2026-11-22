"""絵文字のイラスト画像（Google Noto Emoji / Apache License 2.0）を取得する。"""

from __future__ import annotations

from pathlib import Path

import requests
from PIL import Image

NOTO_URL = "https://cdn.jsdelivr.net/gh/googlefonts/noto-emoji@v2.047/png/512/emoji_u{}.png"
FALLBACK = "💡"


def _code(emoji: str) -> str:
    return "_".join(f"{ord(c):x}" for c in emoji if ord(c) != 0xFE0F)


def load(emoji: str, cache_dir: Path) -> Image.Image | None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    for e in (emoji.strip(), emoji.strip()[:1], FALLBACK):
        if not e:
            continue
        code = _code(e)
        path = cache_dir / f"{code}.png"
        if not path.exists():
            try:
                r = requests.get(NOTO_URL.format(code), timeout=20)
            except requests.RequestException:
                continue
            if not r.ok:
                continue
            path.write_bytes(r.content)
        return Image.open(path).convert("RGBA")
    return None
