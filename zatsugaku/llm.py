"""Claude を呼び出して構造化JSONを受け取る（ポッドキャスト版と同じ仕組み）。

config.yaml の llm.backend で切り替える:
  claude_code … Claude のサブスクリプションで Claude Code CLI を使う（追加費用なし）
  api         … Claude API キーを使う（従量課金）
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile


def call_json(llm: dict, effort: str, system: str, user: str, schema: dict) -> dict:
    if llm.get("backend", "claude_code") == "api":
        return _call_api(llm["api_model"], effort, system, user, schema)
    last_error = None
    for _ in range(2):  # 一時的な失敗に備えて1回だけ再試行
        try:
            return _call_cli(llm["cli_model"], effort, system, user, schema)
        except (RuntimeError, json.JSONDecodeError, subprocess.TimeoutExpired) as e:
            print(f"  [再試行] {e}")
            last_error = e
    raise RuntimeError(f"Claude の呼び出しに失敗しました: {last_error}")


def _call_cli(model: str, effort: str, system: str, user: str, schema: dict) -> dict:
    exe = shutil.which("claude")
    if not exe:
        raise SystemExit("claude コマンドが見つかりません（npm install -g @anthropic-ai/claude-code）")
    cmd = [exe, "-p", "--output-format", "json", "--tools", "", "--no-session-persistence",
           "--model", model, "--effort", effort,
           "--json-schema", json.dumps(schema), "--system-prompt", system]
    # 空のAPIキーがあるとサブスクリプション認証より優先されてしまうため除く
    env = {k: v for k, v in os.environ.items()
           if not (k in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN") and not v)}
    # Claude Code の画面内から実行したときに、そのセッション用の設定を引き継がないようにする
    if "CLAUDE_CODE_ENTRYPOINT" in env:
        env = {k: v for k, v in env.items()
               if not k.startswith(("CLAUDECODE", "CLAUDE_CODE_", "CLAUDE_AGENT_SDK", "ANTHROPIC_BASE_URL"))}
    # プロジェクトの設定や CLAUDE.md を読み込まないよう、空のフォルダで実行する
    with tempfile.TemporaryDirectory() as cwd:
        proc = subprocess.run(cmd, input=user, capture_output=True, text=True,
                              encoding="utf-8", cwd=cwd, env=env, timeout=900)
    try:
        out = json.loads(proc.stdout)
    except json.JSONDecodeError:
        raise RuntimeError(f"CLI の出力を読めません: {proc.stdout[:300]} {proc.stderr[:300]}")
    if out.get("is_error"):
        raise RuntimeError(f"CLI エラー: {out.get('result')}")
    data = out.get("structured_output")
    if data is None:
        text = out.get("result", "")
        data = json.loads(text[text.find("{"): text.rfind("}") + 1])
    print(f"  model={model} {out.get('duration_ms', 0) / 1000:.0f}s")
    return data


def _call_api(model: str, effort: str, system: str, user: str, schema: dict) -> dict:
    import anthropic

    client = anthropic.Anthropic()
    with client.messages.stream(
        model=model,
        max_tokens=16000,
        system=system,
        output_config={"effort": effort, "format": {"type": "json_schema", "schema": schema}},
        messages=[{"role": "user", "content": user}],
    ) as stream:
        message = stream.get_final_message()
    if message.stop_reason == "refusal":
        raise RuntimeError("Claude がリクエストを拒否しました")
    if message.stop_reason == "max_tokens":
        raise RuntimeError("出力が長すぎて途中で切れました")
    text = "".join(b.text for b in message.content if b.type == "text")
    u = message.usage
    print(f"  tokens: in={u.input_tokens} out={u.output_tokens} model={message.model}")
    return json.loads(text)
