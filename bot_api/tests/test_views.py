import pytest
from django.test import override_settings
from rest_framework import status

from sections.models import SectionTable


@pytest.mark.django_db
class TestBotApiViews:
    @override_settings(
        CNC_BOT_API_SECRET="secret-token", CNC_BOT_TABLE_OWNER_USERNAME="bot_owner"
    )
    def test_health_requires_valid_secret(self, client):
        denied = client.get("/api/bot/health/")
        ok = client.get("/api/bot/health/", HTTP_X_CNC_BOT_TOKEN="secret-token")

        assert denied.status_code == status.HTTP_403_FORBIDDEN
        assert ok.status_code == status.HTTP_200_OK
        assert ok.data["ok"] is True

    @override_settings(
        CNC_BOT_API_SECRET="secret-token", CNC_BOT_TABLE_OWNER_USERNAME="missing_owner"
    )
    def test_gateway_returns_503_when_owner_not_configured(self, client):
        response = client.post(
            "/api/bot/gateway/",
            {"action": "lookup_table"},
            format="json",
            HTTP_X_CNC_BOT_TOKEN="secret-token",
        )

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE

    @override_settings(
        CNC_BOT_API_SECRET="secret-token", CNC_BOT_TABLE_OWNER_USERNAME="bot_owner"
    )
    def test_lookup_table_returns_matching_sheet_names(self, client):
        from django.contrib.auth import get_user_model

        owner = get_user_model().objects.create_user(
            username="bot_owner", password="pass"
        )
        SectionTable.objects.create(
            owner=owner,
            title="Rangers main",
            section_type="rangers",
            content={
                "custom_sheet": {
                    "version": 2,
                    "activeSheetIndex": 1,
                    "sheets": [
                        {"name": "Alpha", "data": [["A"]]},
                        {"name": "Bravo", "data": [["B"]]},
                    ],
                }
            },
        )

        response = client.post(
            "/api/bot/gateway/",
            {"action": "lookup_table", "title_contains": "main"},
            format="json",
            HTTP_X_CNC_BOT_TOKEN="secret-token",
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["sheet_names"] == ["Alpha", "Bravo"]
        assert response.data["active_sheet_index"] == 1

    @override_settings(
        CNC_BOT_API_SECRET="secret-token", CNC_BOT_TABLE_OWNER_USERNAME="bot_owner"
    )
    def test_list_and_get_sheet_data(self, client):
        from django.contrib.auth import get_user_model

        owner = get_user_model().objects.create_user(
            username="bot_owner", password="pass"
        )
        table = SectionTable.objects.create(
            owner=owner,
            title="Attendance",
            section_type="attendance",
            content={"custom_sheet": {"data": [["Name", "Score"]], "name": "Sheet A"}},
        )

        list_response = client.post(
            "/api/bot/gateway/",
            {"action": "list_sheets", "table_id": table.id},
            format="json",
            HTTP_X_CNC_BOT_TOKEN="secret-token",
        )
        data_response = client.post(
            "/api/bot/gateway/",
            {"action": "get_sheet_data", "table_id": table.id, "sheet_name": "Sheet A"},
            format="json",
            HTTP_X_CNC_BOT_TOKEN="secret-token",
        )

        assert list_response.status_code == status.HTTP_200_OK
        assert list_response.data["sheet_names"] == ["Sheet A"]
        assert data_response.status_code == status.HTTP_200_OK
        assert data_response.data["data"] == [["Name", "Score"]]

    @override_settings(
        CNC_BOT_API_SECRET="secret-token", CNC_BOT_TABLE_OWNER_USERNAME="bot_owner"
    )
    def test_set_cell_updates_table_content(self, client):
        from django.contrib.auth import get_user_model

        owner = get_user_model().objects.create_user(
            username="bot_owner", password="pass"
        )
        table = SectionTable.objects.create(
            owner=owner,
            title="Attendance",
            section_type="attendance",
            content={"custom_sheet": {"data": [["Name"]], "name": "Sheet A"}},
        )

        response = client.post(
            "/api/bot/gateway/",
            {
                "action": "set_cell",
                "table_id": table.id,
                "sheet_name": "Sheet A",
                "row": 1,
                "col": 1,
                "value": "42",
            },
            format="json",
            HTTP_X_CNC_BOT_TOKEN="secret-token",
        )

        assert response.status_code == status.HTTP_200_OK
        table.refresh_from_db()
        assert table.content["custom_sheet"]["data"][1][1] == "42"
        assert table.needs_nextcloud_push is True

    @override_settings(
        CNC_BOT_API_SECRET="secret-token", CNC_BOT_TABLE_OWNER_USERNAME="bot_owner"
    )
    def test_set_cell_rejects_invalid_coordinates(self, client):
        from django.contrib.auth import get_user_model

        owner = get_user_model().objects.create_user(
            username="bot_owner", password="pass"
        )
        table = SectionTable.objects.create(
            owner=owner, title="Attendance", section_type="attendance", content={}
        )

        response = client.post(
            "/api/bot/gateway/",
            {
                "action": "set_cell",
                "table_id": table.id,
                "sheet_name": "Sheet A",
                "row": "bad",
                "col": 0,
            },
            format="json",
            HTTP_X_CNC_BOT_TOKEN="secret-token",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @override_settings(
        CNC_BOT_API_SECRET="secret-token", CNC_BOT_TABLE_OWNER_USERNAME="bot_owner"
    )
    def test_gateway_rejects_unknown_action(self, client):
        from django.contrib.auth import get_user_model

        get_user_model().objects.create_user(username="bot_owner", password="pass")

        response = client.post(
            "/api/bot/gateway/",
            {"action": "unknown"},
            format="json",
            HTTP_X_CNC_BOT_TOKEN="secret-token",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
