"""Unit-тесты retry загрузки документов в VK (без сети)."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest
import requests

os.environ.setdefault("VK_TOKEN", "test-token")
os.environ.setdefault("VK_GROUP_ID", "1")
os.environ.setdefault("CNC_BOT_SECRET", "test-secret")


def test_send_document_retries_on_405():
    from vk_student_bot import bot as bot_mod

    bot = object.__new__(bot_mod.StudentBot)
    bot.vk_session = MagicMock()
    api = MagicMock()
    bot.vk_session.get_api.return_value = api
    api.docs.getMessagesUploadServer.side_effect = [
        {"upload_url": "https://pu.vk.com/upload1"},
        {"upload_url": "https://pu.vk.com/upload2"},
    ]
    api.docs.save.return_value = {"doc": {"owner_id": -1, "id": 42}}

    resp_fail = MagicMock()
    resp_fail.status_code = 405

    resp_ok = MagicMock()
    resp_ok.status_code = 200
    resp_ok.json.return_value = {"file": "token"}
    resp_ok.raise_for_status.return_value = None

    with patch.object(bot_mod.requests, "post", side_effect=[resp_fail, resp_ok]) as post:
        with patch.object(bot_mod.time, "sleep"):
            bot.send_document(1, "a.docx", b"data", caption="ok")

    assert post.call_count == 2
    assert api.docs.getMessagesUploadServer.call_count == 2
    bot.vk_session.method.assert_called_once()
