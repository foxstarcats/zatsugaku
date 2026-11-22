"""台本と音声から縦長ショート動画（MP4）を描画する。

Pillow で1コマずつ絵を作り、ffmpeg に流し込んで音声と合わせる。
assets/characters/host.png・guest.png（立ち絵）や assets/bgm/ の音楽を置くと自動で使う。
"""

from __future__ import annotations

import math
import re
import shutil
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from . import emoji as emoji_mod

THEMES = {  # (上の色, 下の色)
    "sky": ("#7FD3FF", "#2F80ED"),
    "sunset": ("#FFC371", "#FF5F6D"),
    "mint": ("#8EF5CF", "#17A589"),
    "grape": ("#D3A4FF", "#6A3FD8"),
    "lemon": ("#FFE98A", "#F5A623"),
    "night": ("#34478A", "#0E1430"),
    "sakura": ("#FFD1E3", "#EE6A9C"),
    "ocean": ("#5EE0F0", "#1A5FB4"),
}
TEXT_DARK = (40, 40, 52, 255)
HIGHLIGHT = (232, 48, 48, 255)
MARKER = (255, 232, 92, 255)
NO_LINE_START = set("、。，．,.！？!?」』）)]ー〜～…・ぁぃぅぇぉっゃゅょゎァィゥェォッャュョヮヵヶ")
MARK_RE = re.compile(r"\[\[(.+?)\]\]")


def hex_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def find_font(root: Path) -> str:
    candidates = sorted((root / "assets" / "fonts").glob("*.[ot]t[fc]")) + [
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"),
        Path("C:/Windows/Fonts/BIZ-UDGothicB.ttc"),
        Path("C:/Windows/Fonts/meiryob.ttc"),
    ]
    for p in candidates:
        if p.exists():
            return str(p)
    raise SystemExit("日本語フォントが見つかりません（assets/fonts/ に .ttf を置いてください）")


def find_ffmpeg() -> str:
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    import imageio_ffmpeg

    return imageio_ffmpeg.get_ffmpeg_exe()


# ---------- 文字のレイアウト ----------

def parse_marks(text: str) -> list[tuple[str, bool]]:
    """「[[ ]]」で囲んだ部分を強調ありとして、1文字ずつ (文字, 強調) に分ける。"""
    chars: list[tuple[str, bool]] = []
    pos = 0
    for m in MARK_RE.finditer(text):
        chars += [(c, False) for c in text[pos:m.start()]]
        chars += [(c, True) for c in m.group(1)]
        pos = m.end()
    chars += [(c, False) for c in text[pos:]]
    return chars


def chunks_of(chars: list[tuple[str, bool]]) -> list[list[tuple[str, bool]]]:
    """改行してよい単位にまとめる。台本の「|」を優先し、なければ BudouX で文節に分ける。
    強調部分は途中で改行しないよう1つにまとめる。"""
    if any(c == "|" for c, _ in chars):
        pieces, cur = [], []
        for ch in chars:
            if ch[0] == "|":
                pieces.append(cur)
                cur = []
            else:
                cur.append(ch)
        pieces.append(cur)
    else:
        text = "".join(c for c, _ in chars)
        try:
            import budoux

            phrases = budoux.load_default_japanese_parser().parse(text)
        except ImportError:
            phrases = list(text)
        pieces, pos = [], 0
        for ph in phrases:
            pieces.append(chars[pos:pos + len(ph)])
            pos += len(ph)
    out = []
    for piece in pieces:
        if not piece:
            continue
        # 前の文節と強調部分がつながっていれば結合する
        if out and out[-1][-1][1] and piece[0][1]:
            out[-1] += piece
        else:
            out.append(piece)
    return out


def wrap(chars: list[tuple[str, bool]], font: ImageFont.FreeTypeFont, max_w: int):
    width = lambda seq: font.getlength("".join(c for c, _ in seq))  # noqa: E731
    lines, cur = [], []
    for chunk in chunks_of(chars):
        if cur and width(cur + chunk) > max_w:
            lines.append(cur)
            cur = []
        if width(chunk) > max_w:  # 1文節だけで入りきらない場合は文字単位で折り返す
            for ch in chunk:
                if cur and width(cur + [ch]) > max_w and ch[0] not in NO_LINE_START:
                    lines.append(cur)
                    cur = []
                cur.append(ch)
        else:
            cur += chunk
    if cur:
        lines.append(cur)
    return lines


def fit_text(text: str, font_path: str, max_w: int, max_lines: int, size: int, min_size: int):
    chars = parse_marks(text)
    while True:
        font = ImageFont.truetype(font_path, size)
        lines = wrap(chars, font, max_w)
        if len(lines) <= max_lines or size <= min_size:
            break
        size -= 4
    # 行の長さをそろえる（最後の行に1〜2文字だけ残るのを防ぐ）
    widest = max(font.getlength("".join(c for c, _ in ch)) for ch in chunks_of(chars))
    lo, hi = min(max(max_w // 2, math.ceil(widest)), max_w), max_w
    while lo < hi:
        mid = (lo + hi) // 2
        if len(wrap(chars, font, mid)) <= len(lines):
            hi = mid
        else:
            lo = mid + 1
    return font, wrap(chars, font, lo)


def draw_rich_lines(draw: ImageDraw.ImageDraw, lines, font, cx: int, top: int, line_h: int,
                    color, marker: bool = True) -> None:
    for i, line in enumerate(lines):
        s = "".join(c for c, _ in line)
        x = cx - font.getlength(s) / 2
        y = top + i * line_h
        # 強調部分の下に蛍光ペン風のマーカーを引く
        if marker:
            j = 0
            while j < len(line):
                if line[j][1]:
                    k = j
                    while k < len(line) and line[k][1]:
                        k += 1
                    x0 = x + font.getlength(s[:j])
                    x1 = x + font.getlength(s[:k])
                    draw.rounded_rectangle([x0 - 4, y + line_h * 0.52, x1 + 4, y + line_h * 0.92],
                                           radius=8, fill=MARKER)
                    j = k
                else:
                    j += 1
        for j, (c, hl) in enumerate(line):
            draw.text((x + font.getlength(s[:j]), y), c, font=font,
                      fill=HIGHLIGHT if hl else color)


# ---------- 部品の事前描画 ----------

def make_background(w: int, h: int, theme: str):
    top, bottom = (hex_rgb(c) for c in THEMES.get(theme, THEMES["sky"]))
    grad = Image.new("RGBA", (1, h))
    for y in range(h):
        t = y / (h - 1)
        grad.putpixel((0, y), tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3)) + (255,))
    grad = grad.resize((w, h))

    period = 160  # 水玉模様（縦に繰り返し、少しずつ流れる）
    pat = Image.new("RGBA", (w, h + period), (0, 0, 0, 0))
    d = ImageDraw.Draw(pat)
    for row, y in enumerate(range(-period, h + period * 2, period // 2)):
        for x in range(-period, w + period, period):
            ox = x + (period // 2 if row % 2 else 0)
            d.ellipse([ox - 16, y - 16, ox + 16, y + 16], fill=(255, 255, 255, 34))
    return grad, pat, period


def make_header(font_path: str, channel: str, date_label: str, w: int) -> Image.Image:
    font = ImageFont.truetype(font_path, 46)
    small = ImageFont.truetype(font_path, 34)
    img = Image.new("RGBA", (w, 100), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    tw = font.getlength(channel)
    d.rounded_rectangle([60, 10, 60 + tw + 64, 90], radius=40, fill=(255, 255, 255, 235))
    d.text((92, 50), channel, font=font, fill=(255, 90, 60, 255), anchor="lm")
    d.text((w - 60, 50), date_label, font=small, fill=(255, 255, 255, 255), anchor="rm",
           stroke_width=4, stroke_fill=(0, 0, 0, 90))
    return img


def make_hook(font_path: str, hook: str, w: int) -> Image.Image:
    max_w = w - 200
    font, lines = fit_text(hook, font_path, max_w, 2, 92, 60)
    line_h = int(font.size * 1.35)
    ph = line_h * len(lines) + 70
    img = Image.new("RGBA", (w, ph + 20), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([60, 16, w - 60, ph + 16], radius=40, fill=(0, 0, 0, 60))  # 影
    d.rounded_rectangle([60, 0, w - 60, ph], radius=40, fill=(255, 255, 255, 250))
    draw_rich_lines(d, lines, font, w // 2, 35 - int(font.size * 0.12), line_h, TEXT_DARK, marker=False)
    return img


def make_caption(font_path: str, text: str, name: str, color: str, w: int) -> Image.Image:
    max_w = w - 220
    font, lines = fit_text(text, font_path, max_w, 3, 68, 50)
    line_h = int(font.size * 1.45)
    ph = line_h * len(lines) + 90
    img = Image.new("RGBA", (w, ph + 60), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    rgb = hex_rgb(color)
    top = 40
    d.rounded_rectangle([50, top + 12, w - 50, top + ph + 12], radius=36, fill=(0, 0, 0, 55))
    d.rounded_rectangle([50, top, w - 50, top + ph], radius=36, fill=(255, 255, 255, 245),
                        outline=rgb + (255,), width=8)
    draw_rich_lines(d, lines, font, w // 2, top + 50 - int(font.size * 0.12), line_h, TEXT_DARK)
    # 話し手の名札
    nf = ImageFont.truetype(font_path, 40)
    nw = nf.getlength(name)
    d.rounded_rectangle([90, 0, 90 + nw + 60, 74], radius=37, fill=rgb + (255,))
    d.text((120, 37), name, font=nf, fill=(255, 255, 255, 255), anchor="lm")
    return img


def make_emoji_disc(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse([0, 0, size - 1, size - 1], fill=(255, 255, 255, 70))
    d.ellipse([28, 28, size - 29, size - 29], fill=(255, 255, 255, 120))
    return img


def load_character(root: Path, role: str, height: int) -> Image.Image | None:
    for ext in ("png", "webp"):
        p = root / "assets" / "characters" / f"{role}.{ext}"
        if p.exists():
            img = Image.open(p).convert("RGBA")
            return img.resize((int(img.width * height / img.height), height), Image.LANCZOS)
    return None


# ---------- アニメーション ----------

def ease_out_back(t: float) -> float:
    t = min(max(t, 0.0), 1.0)
    c1, c3 = 1.70158, 2.70158
    return 1 + c3 * (t - 1) ** 3 + c1 * (t - 1) ** 2


def scaled(img: Image.Image, s: float) -> Image.Image:
    if abs(s - 1) < 0.005:
        return img
    return img.resize((max(1, int(img.width * s)), max(1, int(img.height * s))), Image.BILINEAR)


def paste_center(frame: Image.Image, img: Image.Image, cx: int, cy: int) -> None:
    frame.alpha_composite(img, (int(cx - img.width / 2), int(cy - img.height / 2)))


def render_video(script: dict, timings: list[dict], wav_path: str, out_path: str, cfg: dict,
                 root: Path, date_label: str, duration: float) -> None:
    v = cfg["video"]
    W, H, fps = v["width"], v["height"], v["fps"]
    font_path = find_font(root)
    voices = cfg["voices"]

    grad, pattern, period = make_background(W, H, script.get("theme", "sky"))
    header = make_header(font_path, cfg["channel"]["name"], date_label, W)
    hook = make_hook(font_path, script["hook"], W)
    disc = make_emoji_disc(620)
    captions, emojis = [], []
    for line in script["lines"]:
        role = voices[line["speaker"]]
        captions.append(make_caption(font_path, line["text"], role["name"], role["color"], W))
        img = emoji_mod.load(line.get("emoji", ""), root / "assets" / "emoji_cache")
        emojis.append(img.resize((420, 420), Image.LANCZOS) if img else None)
    chars = {r: load_character(root, r, 600) for r in ("guest", "host")}
    dim = {r: Image.blend(Image.new("RGBA", img.size, (0, 0, 0, 0)), img, 0.55)
           for r, img in chars.items() if img is not None}

    hook_y = 190
    hook_cy = hook_y + hook.height // 2
    emoji_cy = hook_y + hook.height + 370
    cap_top = emoji_cy + 330

    # セリフごとの表示区間（次のセリフが始まるまで表示し続ける）
    spans = []
    for i, t in enumerate(timings):
        end = timings[i + 1]["start"] if i + 1 < len(timings) else duration + 1
        spans.append((0.0 if i == 0 else t["start"], end, t["end"]))

    ffmpeg = find_ffmpeg()
    bgm = next((p for p in sorted((root / "assets" / "bgm").glob("*"))
                if p.suffix.lower() in (".mp3", ".wav", ".m4a", ".ogg")), None)
    cmd = [ffmpeg, "-y", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{W}x{H}", "-r", str(fps), "-i", "-",
           "-i", wav_path]
    if bgm:
        fade_st = max(duration - 1.5, 0)
        cmd += ["-stream_loop", "-1", "-i", str(bgm), "-filter_complex",
                f"[2:a]volume={v['bgm_volume']},afade=t=out:st={fade_st:.2f}:d=1.5[b];"
                f"[1:a][b]amix=inputs=2:duration=first:normalize=0[a]",
                "-map", "0:v", "-map", "[a]"]
    else:
        cmd += ["-map", "0:v", "-map", "1:a"]
    cmd += ["-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-t", f"{duration:.3f}",
            "-movflags", "+faststart", out_path]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)

    n_frames = math.ceil(duration * fps)
    cur = 0
    try:
        for f in range(n_frames):
            t = f / fps
            while cur + 1 < len(spans) and t >= spans[cur + 1][0]:
                cur += 1
            s_start, _, speak_end = spans[cur]
            since = t - s_start

            frame = grad.copy()
            off = int(t * 40) % period
            frame.alpha_composite(pattern.crop((0, off, W, off + H)))

            # 進行バー
            ImageDraw.Draw(frame).rectangle([0, 0, int(W * t / duration), 14], fill=(255, 255, 255, 230))
            frame.alpha_composite(header, (0, 70))
            paste_center(frame, scaled(hook, 0.7 + 0.3 * ease_out_back(t / 0.45)), W // 2, hook_cy)

            # 絵文字イラスト（切り替わるとポンと出て、ふわふわ浮く）
            em = emojis[cur]
            if em is not None:
                same = cur > 0 and script["lines"][cur].get("emoji") == script["lines"][cur - 1].get("emoji")
                pop = 1.0 if same else ease_out_back(since / 0.35)
                float_y = 12 * math.sin(t * 2.4)
                paste_center(frame, disc, W // 2, emoji_cy)
                paste_center(frame, scaled(em, 0.4 + 0.6 * pop), W // 2, int(emoji_cy + float_y))

            # 立ち絵（置いてある場合のみ）。話している方は明るく、少し跳ねる
            speaker = script["lines"][cur]["speaker"]
            for role, img in chars.items():
                if img is None:
                    continue
                talking = role == speaker and t < speak_end
                x = 20 if role == "guest" else W - img.width - 20
                y = H - img.height + 40 + (int(-10 * abs(math.sin(t * 9))) if talking else 0)
                frame.alpha_composite(img if role == speaker else dim[role], (x, y))

            # 字幕（出始めに少しだけ拡大して出る）
            cap = captions[cur]
            cs = 0.9 + 0.1 * ease_out_back(since / 0.2)
            paste_center(frame, scaled(cap, cs), W // 2, cap_top + cap.height // 2)

            proc.stdin.write(frame.tobytes())
            if f % (fps * 5) == 0:
                print(f"  描画 {t:4.1f}/{duration:.1f}秒")
        proc.stdin.close()
    except BrokenPipeError:
        pass
    if proc.wait() != 0:
        raise RuntimeError("ffmpeg での動画書き出しに失敗しました")
