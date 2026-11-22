"""Claude で今日の雑学を選んで台本を書き、別の視点で事実確認する。"""

from __future__ import annotations

from .llm import call_json

THEMES = ["sky", "sunset", "mint", "grape", "lemon", "night", "sakura", "ocean"]

SCRIPT_SCHEMA = {
    "type": "object",
    "properties": {
        "topic": {"type": "string"},
        "hook": {"type": "string"},
        "title": {"type": "string"},
        "description": {"type": "string"},
        "hashtags": {"type": "array", "items": {"type": "string"}},
        "theme": {"type": "string", "enum": THEMES},
        "basis": {"type": "string"},
        "lines": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "speaker": {"type": "string", "enum": ["host", "guest"]},
                    "text": {"type": "string"},
                    "speech": {"type": "string"},
                    "emoji": {"type": "string"},
                },
                "required": ["speaker", "text", "speech", "emoji"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["topic", "hook", "title", "description", "hashtags", "theme", "basis", "lines"],
    "additionalProperties": False,
}

CHECK_SCHEMA = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": ["ok", "reject"]},
        "reason": {"type": "string"},
    },
    "required": ["verdict", "reason"],
    "additionalProperties": False,
}


def write_script(cfg: dict, genre: str, avoid: list[str], extra_avoid: list[str] | None = None) -> dict:
    host = cfg["voices"]["host"]["name"]
    guest = cfg["voices"]["guest"]["name"]
    seconds = cfg["video"]["target_seconds"]
    chars = int(seconds * 7)  # 話速1.2で1秒あたり約7文字

    system = f"""あなたは人気の雑学ショート動画チャンネル「{cfg['channel']['name']}」の構成作家です。
縦長の{seconds}秒動画で、2人のキャラクターが掛け合いで雑学を1つ紹介する台本を書きます。

登場人物:
- guest = {guest}: 聞き役。冒頭で視聴者の興味を引く質問を投げ、驚きやツッコミを入れる。語尾は「〜のだ」「〜なのだ」。
- host = {host}: 解説役。答えと理由を分かりやすく説明する。丁寧語で、ときどき「〜ですわ」「〜ですのよ」とお嬢様口調が混じる。

雑学の選び方（最重要）:
- 「へぇ！」と言いたくなる意外性があり、誰かに話したくなるもの
- 図鑑・辞典・公的機関の資料などで確認できる、確かな事実だけを選ぶ。俗説・諸説あるもの・都市伝説・よく誤って広まっている話（例: 「人は脳の10%しか使っていない」「金魚の記憶は3秒」）は選ばない
- 数字は確かなものだけを使い、あいまいなら「約」「〜ほど」と幅を持たせる
- 子どもから大人まで見られる内容にする（怖すぎる話・下品な話・政治や宗教の論争は避ける）

台本の構成（全体で5〜7セリフ）:
1. guest が「〜って知ってるのだ？」のような質問で始める（最初の2秒で興味を引く）
2. host が答え（意外な事実）をズバリ言う
3. guest が驚く・ツッコむ（短く）
4. host が理由やしくみを説明する（1〜2セリフ）
5. 最後に guest か host が、オチや「明日誰かに話したくなる」一言で締める（チャンネル登録の呼びかけはしない）

各セリフの書き方:
- text: 画面に出す字幕。1セリフ40文字以内。一番大事な言葉を [[ ]] で1か所だけ囲む。字幕の改行位置を決めるため、意味の切れ目（文節）ごとに「|」を入れる（例: 実は|タコの心臓は|[[3つ]]も|ありますの）。絵文字・URL・マークダウンは入れない
- speech: 音声合成で読み上げる文。text と同じ内容から [[ ]] と | を外し、英字・記号・読み間違えやすい漢字や数字の読みを、ひらがな・カタカナにする（例: DNA→ディーエヌエー、3つ→みっつ、一日→いちにち）
- emoji: そのセリフの内容を表す絵文字を1つだけ（国旗以外の、よく使われる絵文字）
- 読み上げ全体で日本語およそ{chars}文字（約{seconds}秒）

その他の項目:
- topic: 雑学の内容を1文で（重複チェック用。例: タコには心臓が3つある）
- hook: 画面上部に大きく出す見出し。16文字以内で「？」で終わる疑問形（例: タコの心臓はいくつ？）
- title: 投稿用のタイトル（30文字以内、結論を少しだけ伏せて気になる形に）
- description: 投稿用の説明文（2文程度）
- hashtags: この雑学に合うハッシュタグを3つ（「#」付き）
- theme: 内容に合う配色（sky/sunset/mint/grape/lemon/night/sakura/ocean）
- basis: この雑学が事実だと言える根拠（どんな分野の通説・資料に基づくか）を2〜3文で"""

    avoid_all = list(avoid) + list(extra_avoid or [])
    avoid_text = "\n".join(f"- {t}" for t in avoid_all[-300:]) or "（まだありません）"
    user = f"""今日のジャンル: {genre}

これまでに紹介した雑学（同じもの・よく似たものは避けてください）:
{avoid_text}

今日の台本を1本書いてください。"""

    script = call_json(cfg["llm"], cfg["llm"]["effort"], system, user, SCRIPT_SCHEMA)
    script["lines"] = [l for l in script["lines"] if l["text"].strip() and l["speech"].strip()]
    return script


def fact_check(cfg: dict, script: dict) -> dict:
    system = """あなたは厳格なファクトチェッカーです。
雑学ショート動画の台本を読み、内容が確かな事実か判定します。
- 俗説・都市伝説・諸説ある話を断定している、数字が誤っている・大げさ、などがあれば reject
- 細部の言い回しや演出の誇張（キャラクターの驚きなど）は問題にしない
- 確信が持てない場合も reject にする（誤った雑学を公開するほうが害が大きいため）
reason には判定の理由を日本語で簡潔に書く。"""
    body = "\n".join(f"{l['speaker']}: {l['text']}" for l in script["lines"])
    user = f"""雑学: {script['topic']}
作者が挙げた根拠: {script['basis']}

台本:
{body}"""
    return call_json(cfg["llm"], "medium", system, user, CHECK_SCHEMA)
