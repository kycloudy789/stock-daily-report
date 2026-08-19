"""通过 PushPlus 把简报发送到微信。"""

from __future__ import annotations

import html
import logging
import time
from typing import Dict

import requests

from .config import require_pushplus_token

LOGGER = logging.getLogger(__name__)
MAX_PUSH_CHARS = 19000
CSS_MARKS = ("<!-- CSS_START -->", "<!-- CSS_END -->")
BODY_MARKS = ("<!-- BODY_START -->", "<!-- BODY_END -->")
# 首次失败后等待 5 秒重试，第二次失败后等待 15 秒，最多共尝试 3 次。
RETRY_DELAYS = (5.0, 15.0)


def _slice_marked(source: str, marks) -> str:
    start, end = marks
    begin = source.find(start)
    if begin < 0:
        return ""
    begin += len(start)
    finish = source.find(end, begin)
    if finish < 0:
        return ""
    return source[begin:finish]


def _push_content(html_content: str, url: str) -> str:
    """从整份 HTML 中提取可直接在微信 H5 页面展示的正文。"""
    css = _slice_marked(html_content, CSS_MARKS)
    body = _slice_marked(html_content, BODY_MARKS)
    if not css or not body:
        return ""
    backup_link = ""
    if url:
        backup_link = (
            f'<p style="text-align:center;margin-top:14px;">'
            f'<a href="{html.escape(url)}" style="color:#0b3b5c;font-size:13px;">'
            "网页版存档链接</a></p>"
        )
    return f"{css}{body}{backup_link}"


def send_pushplus(token: str, title: str, content: str, topic: str = "") -> bool:
    """调用 PushPlus 接口发送微信消息。"""
    last_error: Exception | None = None
    for attempt in range(len(RETRY_DELAYS) + 1):
        try:
            payload: Dict = {
                "token": token,
                "title": title,
                "content": content,
                "template": "html",
            }
            if topic:
                payload["topic"] = topic
            resp = requests.post(
                "https://www.pushplus.plus/send",
                json=payload,
                timeout=20,
            )
            resp.raise_for_status()
            data = resp.json()
            if data.get("code") != 200:
                raise RuntimeError(f"PushPlus 返回失败：{data}")
            return True
        except Exception as exc:
            last_error = exc
            LOGGER.warning("PushPlus 发送第 %d 次失败：%s", attempt + 1, exc)
            if attempt < len(RETRY_DELAYS):
                time.sleep(RETRY_DELAYS[attempt])
    if last_error is not None:
        raise last_error
    return False


def send_daily_report(cfg: Dict, url: str, summary: str, target_date, html_content: str = "") -> bool:
    """发送微信消息；有完整 HTML 时直接展示整份报告，否则退回链接加摘要。"""
    try:
        token = require_pushplus_token(cfg)
    except RuntimeError as exc:
        LOGGER.error("未发送微信消息：%s", exc)
        return False

    content = _push_content(html_content, url)
    if not content or len(content) > MAX_PUSH_CHARS:
        link = ""
        if url:
            link = (
                f'<a href="{html.escape(url)}" style="font-size:16px;font-weight:bold;">'
                "点击查看今日股市与基金简报</a><br><br>"
            )
        body = summary.replace("\n", "<br>")
        content = (
            f"{link}{body}<br><br>"
            "<span style='color:#888;font-size:12px;'>建议仅供参考，不构成投资建议。</span>"
        )
    title = f"{target_date.isoformat()} 股市简报"
    try:
        send_pushplus(token, title, content, topic=str(cfg.get("PushPlus 群组编码") or ""))
        return True
    except Exception as exc:
        LOGGER.error("微信推送失败：%s", exc)
        return False
