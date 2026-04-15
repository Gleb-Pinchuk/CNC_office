import pytest
from django.test import override_settings

from bot_api.nextcloud import NextcloudEventWriter, NextcloudWriteError


@override_settings(
    NEXTCLOUD_BOT_WRITE_ENABLED=True,
    NEXTCLOUD_BOT_WRITE_STRICT=False,
    NEXTCLOUD_BASE_URL="https://cloud.example.com",
    NEXTCLOUD_USERNAME="bot-user",
    NEXTCLOUD_APP_PASSWORD="app-pass",
    NEXTCLOUD_BOT_ROOT="CNC_office/vk_bot",
)
def test_writer_builds_nextcloud_event_path(monkeypatch):
    writer = NextcloudEventWriter()
    seen = {}

    def fake_ensure_dirs(parts):
        seen["parts"] = parts

    def fake_put_json(rel_path, payload):
        seen["rel_path"] = rel_path
        seen["payload"] = payload

    monkeypatch.setattr(writer, "_ensure_dirs", fake_ensure_dirs)
    monkeypatch.setattr(writer, "_put_json", fake_put_json)

    writer.safe_write_set_cell_event(
        {
            "event": "set_cell",
            "table_id": 123,
            "sheet_name": "Sheet A",
            "row": 1,
            "col": 2,
            "value": "ok",
        }
    )

    assert seen["parts"][0] == "CNC_office/vk_bot"
    assert seen["payload"]["table_id"] == 123
    assert seen["rel_path"].startswith("CNC_office/vk_bot/")
    assert seen["rel_path"].endswith(".json")


@override_settings(NEXTCLOUD_BOT_WRITE_ENABLED=True, NEXTCLOUD_BOT_WRITE_STRICT=False)
def test_safe_write_is_non_blocking_by_default(monkeypatch):
    writer = NextcloudEventWriter()

    def fail(payload):
        raise NextcloudWriteError("boom")

    monkeypatch.setattr(writer, "write_set_cell_event", fail)
    writer.safe_write_set_cell_event({"event": "set_cell"})


@override_settings(NEXTCLOUD_BOT_WRITE_ENABLED=True, NEXTCLOUD_BOT_WRITE_STRICT=True)
def test_safe_write_raises_in_strict_mode(monkeypatch):
    writer = NextcloudEventWriter()

    def fail(payload):
        raise NextcloudWriteError("boom")

    monkeypatch.setattr(writer, "write_set_cell_event", fail)
    with pytest.raises(NextcloudWriteError):
        writer.safe_write_set_cell_event({"event": "set_cell"})
