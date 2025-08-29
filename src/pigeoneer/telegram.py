"""Telegram message handling."""
import json
from typing import Optional
from urllib import parse, request, error

# Maximum length for Telegram messages
MAX_LEN = 4096

def _tg_api(token: str, method: str, data: dict | None = None, timeout: int = 20) -> dict:
    url = f"https://api.telegram.org/bot{token}/{method}"
    try:
        if data:
            enc = parse.urlencode({k: str(v) for k, v in data.items()}).encode("utf-8")
            req = request.Request(url, data=enc, method="POST")
        else:
            req = request.Request(url, method="GET")
        with request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        raise RuntimeError(f"HTTP {e.code}: {body}")
    except Exception as e:
        raise RuntimeError(f"API call failed: {e!r}")

def _send_telegram(text: str, chat_id: str, token: str, parse_mode: Optional[str] = None,
                  disable_preview: Optional[bool] = None, silent: Optional[bool] = None) -> dict:
    data = {"chat_id": chat_id, "text": text}
    if parse_mode:
        pm = parse_mode.upper()
        if pm in {"HTML", "MARKDOWN", "MARKDOWNV2"}:
            data["parse_mode"] = pm
    if disable_preview is not None:
        data["disable_web_page_preview"] = "true" if disable_preview else "false"
    if silent:
        data["disable_notification"] = "true"

    return _tg_api(token, "sendMessage", data)

def send_message(text: str, chat_id: str, token: str, parse_mode: Optional[str] = None,
                disable_preview: Optional[bool] = True, silent: Optional[bool] = None) -> None:
    """Send a message via Telegram, automatically handling message length limits."""
    if len(text) <= MAX_LEN:
        _send_telegram(text, chat_id, token, parse_mode, disable_preview, silent)
        return
    
    # Split long messages
    for i in range(0, len(text), MAX_LEN):
        part = text[i:i+MAX_LEN]
        _send_telegram(part, chat_id, token, parse_mode, disable_preview, silent)
