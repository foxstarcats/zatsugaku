"""VOICEVOX エンジンでセリフごとに音声を作り、1本のWAVと各セリフの開始・終了時刻を返す。"""

from __future__ import annotations

import io
import os
import subprocess
import time
import wave

import requests

LOCAL_ENGINE = os.path.expandvars(r"%LOCALAPPDATA%\Programs\VOICEVOX\vv-engine\run.exe")


class Voicevox:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    def alive(self) -> bool:
        try:
            return requests.get(f"{self.base_url}/version", timeout=3).ok
        except requests.RequestException:
            return False

    def wait_until_ready(self, timeout: float = 300) -> None:
        if not self.alive() and os.name == "nt" and os.path.exists(LOCAL_ENGINE):
            print("  VOICEVOX エンジンを起動しています...")
            subprocess.Popen([LOCAL_ENGINE, "--host", "127.0.0.1", "--port", "50021"],
                             cwd=os.path.dirname(LOCAL_ENGINE),
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.alive():
                return
            time.sleep(2)
        raise RuntimeError(f"VOICEVOX エンジンに接続できません: {self.base_url}")

    def synthesize(self, text: str, speaker: int, speed: float) -> bytes:
        for attempt in range(3):
            try:
                q = requests.post(f"{self.base_url}/audio_query",
                                  params={"text": text, "speaker": speaker}, timeout=60)
                q.raise_for_status()
                query = q.json()
                query["speedScale"] = speed
                query["prePhonemeLength"] = 0.05
                query["postPhonemeLength"] = 0.05
                s = requests.post(f"{self.base_url}/synthesis", params={"speaker": speaker},
                                  json=query, timeout=300)
                s.raise_for_status()
                return s.content
            except requests.RequestException:
                if attempt == 2:
                    raise
                time.sleep(3)
        raise AssertionError("unreachable")


def render_voice(script: dict, cfg: dict, engine_url: str, out_wav: str) -> list[dict]:
    """台本を音声化して out_wav に保存し、各セリフの {start, end}（秒）を返す。"""
    vv = Voicevox(engine_url)
    vv.wait_until_ready()
    voices = cfg["voices"]
    speakers = {"host": voices["host"]["speaker_id"], "guest": voices["guest"]["speaker_id"]}

    lead_in = 0.25  # 動画の最初に少しだけ間を置く
    pcm = bytearray()
    rate = None
    timings = []
    for line in script["lines"]:
        wav_bytes = vv.synthesize(line["speech"], speakers[line["speaker"]], voices["speed"])
        with wave.open(io.BytesIO(wav_bytes)) as w:
            if rate is None:
                rate = w.getframerate()
                pcm += b"\x00\x00" * int(rate * lead_in)
                gap = b"\x00\x00" * int(rate * voices["pause_ms"] / 1000)
            if w.getnchannels() != 1 or w.getsampwidth() != 2 or w.getframerate() != rate:
                raise RuntimeError("想定外の音声形式です")
            start = len(pcm) / 2 / rate
            pcm += w.readframes(w.getnframes())
            timings.append({"start": start, "end": len(pcm) / 2 / rate})
        pcm += gap
    pcm += b"\x00\x00" * int(rate * 0.8)  # 最後の余韻

    with wave.open(out_wav, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(bytes(pcm))
    return timings
