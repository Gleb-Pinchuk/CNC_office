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
    def test_export_table_xlsx_returns_attachment(self, client):
        from django.contrib.auth import get_user_model

        owner = get_user_model().objects.create_user(
            username="bot_owner", password="pass"
        )
        table = SectionTable.objects.create(
            owner=owner,
            title="Rangers main",
            section_type="rangers",
            content={"custom_sheet": {"data": [["A1"]], "name": "Sheet1"}},
        )

        response = client.post(
            "/api/bot/gateway/",
            {"action": "export_table_xlsx", "table_id": table.id},
            format="json",
            HTTP_X_CNC_BOT_TOKEN="secret-token",
        )

        assert response.status_code == status.HTTP_200_OK
        assert (
            response["Content-Type"]
            == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        assert "attachment; filename=" in response["Content-Disposition"]
        assert len(response.content) > 100

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

    @override_settings(
        CNC_BOT_API_SECRET="secret-token",
        CNC_BOT_TABLE_OWNER_USERNAME="bot_owner",
        BOT_SHEET_FIO_COL=0,
        BOT_SHEET_GROUP_COL=1,
        BOT_SHEET_STATUS_COL=2,
        BOT_SHEET_REMARK_COL=3,
        BOT_SHEET_SOCIAL_COLS="4",
    )
    def test_list_groups_search_set_student_remark(self, client):
        from django.contrib.auth import get_user_model

        owner = get_user_model().objects.create_user(
            username="bot_owner", password="pass"
        )
        table = SectionTable.objects.create(
            owner=owner,
            title="Test",
            section_type="rangers",
            content={
                "custom_sheet": {
                    "version": 2,
                    "activeSheetIndex": 0,
                    "sheets": [
                        {
                            "name": "Robo",
                            "data": [
                                ["ФИО", "Группа", "Статус", "Замечания", "Соцсети"],
                                ["Иванов Иван", "Г1", "учится", "", "vk.com/id1"],
                            ],
                        }
                    ],
                }
            },
        )
        lg = client.post(
            "/api/bot/gateway/",
            {
                "action": "list_groups",
                "table_id": table.id,
                "sheet_name": "Robo",
            },
            format="json",
            HTTP_X_CNC_BOT_TOKEN="secret-token",
        )
        assert lg.status_code == status.HTTP_200_OK
        assert lg.data["groups"] == ["Г1"]

        sr = client.post(
            "/api/bot/gateway/",
            {
                "action": "search_students",
                "table_id": table.id,
                "sheet_name": "Robo",
                "query": "иван",
            },
            format="json",
            HTTP_X_CNC_BOT_TOKEN="secret-token",
        )
        assert sr.status_code == status.HTTP_200_OK
        assert len(sr.data["students"]) == 1

        lst = client.post(
            "/api/bot/gateway/",
            {
                "action": "list_students",
                "table_id": table.id,
                "sheet_name": "Robo",
                "group": "Г1",
            },
            format="json",
            HTTP_X_CNC_BOT_TOKEN="secret-token",
        )
        assert lst.status_code == status.HTTP_200_OK
        assert len(lst.data["students"]) == 1

        profile = client.post(
            "/api/bot/gateway/",
            {
                "action": "get_student_profile",
                "table_id": table.id,
                "sheet_name": "Robo",
                "student_fio": "Иванов",
            },
            format="json",
            HTTP_X_CNC_BOT_TOKEN="secret-token",
        )
        assert profile.status_code == status.HTTP_200_OK
        assert profile.data["student"]["status"] == "учится"
        assert profile.data["student"]["social_links"][0].startswith("https://")

        rm = client.post(
            "/api/bot/gateway/",
            {
                "action": "set_student_remark",
                "table_id": table.id,
                "sheet_name": "Robo",
                "student_fio": "Иванов",
                "remark_date": "18.04.2026",
                "remark_text": "опоздал",
            },
            format="json",
            HTTP_X_CNC_BOT_TOKEN="secret-token",
        )
        assert rm.status_code == status.HTTP_200_OK
        table.refresh_from_db()
        row = table.content["custom_sheet"]["sheets"][0]["data"][1]
        assert row[3] == "опоздал"

        st = client.post(
            "/api/bot/gateway/",
            {
                "action": "set_student_status",
                "table_id": table.id,
                "sheet_name": "Robo",
                "student_fio": "Иванов",
                "status_value": "отчислен",
            },
            format="json",
            HTTP_X_CNC_BOT_TOKEN="secret-token",
        )
        assert st.status_code == status.HTTP_200_OK
        table.refresh_from_db()
        row = table.content["custom_sheet"]["sheets"][0]["data"][1]
        assert row[2] == "отчислен"

    @override_settings(
        CNC_BOT_API_SECRET="secret-token",
        CNC_BOT_TABLE_OWNER_USERNAME="bot_owner",
        BOT_SHEET_FIO_COL=0,
        BOT_SHEET_GROUP_COL=1,
        BOT_SHEET_STATUS_COL=2,
        BOT_SHEET_REMARK_COL=3,
    )
    def test_set_student_remark_uses_week_column_from_header_date(self, client):
        from django.contrib.auth import get_user_model

        owner = get_user_model().objects.create_user(username="bot_owner", password="pass")
        table = SectionTable.objects.create(
            owner=owner,
            title="Weeks",
            section_type="rangers",
            content={
                "custom_sheet": {
                    "version": 2,
                    "activeSheetIndex": 0,
                    "sheets": [
                        {
                            "name": "Robo",
                            "data": [
                                [
                                    "ФИО",
                                    "Группа",
                                    "Статус",
                                    "Резерв",
                                    "15.04.2026",
                                    "22.04.2026",
                                ],
                                ["Иванов Иван", "Г1", "учится", "", "", ""],
                            ],
                        }
                    ],
                }
            },
        )

        rm = client.post(
            "/api/bot/gateway/",
            {
                "action": "set_student_remark",
                "table_id": table.id,
                "sheet_name": "Robo",
                "student_fio": "Иванов",
                "remark_date": "21.04.2026",
                "remark_text": "замечание недели",
            },
            format="json",
            HTTP_X_CNC_BOT_TOKEN="secret-token",
        )
        assert rm.status_code == status.HTTP_200_OK
        assert rm.data["remark_col"] == 5

        table.refresh_from_db()
        row = table.content["custom_sheet"]["sheets"][0]["data"][1]
        assert row[4] == ""
        assert row[5] == "замечание недели"

        prof = client.post(
            "/api/bot/gateway/",
            {
                "action": "get_student_profile",
                "table_id": table.id,
                "sheet_name": "Robo",
                "student_fio": "Иванов",
                "remark_date": "21.04.2026",
            },
            format="json",
            HTTP_X_CNC_BOT_TOKEN="secret-token",
        )
        assert prof.status_code == status.HTTP_200_OK
        assert prof.data["student"]["remark_col"] == 5

    @override_settings(
        CNC_BOT_API_SECRET="secret-token",
        CNC_BOT_TABLE_OWNER_USERNAME="bot_owner",
        BOT_SHEET_FIO_COL=0,
        BOT_SHEET_GROUP_COL=1,
        BOT_SHEET_STATUS_COL=5,
        BOT_SHEET_REMARK_COL=5,
    )
    def test_set_student_remark_after_last_week_uses_last_date_column(self, client):
        from django.contrib.auth import get_user_model

        owner = get_user_model().objects.create_user(username="bot_owner", password="pass")
        table = SectionTable.objects.create(
            owner=owner,
            title="Weeks",
            section_type="rangers",
            content={
                "custom_sheet": {
                    "version": 2,
                    "activeSheetIndex": 0,
                    "sheets": [
                        {
                            "name": "Robo",
                            "data": [
                                [
                                    "ФИО",
                                    "Группа",
                                    "13.04-19.04",
                                    "20.04-26.04",
                                    "Соцсети",
                                    "Статус учебы",
                                ],
                                ["Иванов Иван", "Г1", "", "", "", "учится"],
                            ],
                        }
                    ],
                }
            },
        )

        rm = client.post(
            "/api/bot/gateway/",
            {
                "action": "set_student_remark",
                "table_id": table.id,
                "sheet_name": "Robo",
                "student_fio": "Иванов",
                "remark_date": "27.04.2026",
                "remark_text": "после доступной недели",
            },
            format="json",
            HTTP_X_CNC_BOT_TOKEN="secret-token",
        )

        assert rm.status_code == status.HTTP_200_OK
        assert rm.data["remark_col"] == 3

        table.refresh_from_db()
        row = table.content["custom_sheet"]["sheets"][0]["data"][1]
        assert row[3] == "после доступной недели"
        assert row[5] == "учится"

    @override_settings(
        CNC_BOT_API_SECRET="secret-token",
        CNC_BOT_TABLE_OWNER_USERNAME="bot_owner",
        BOT_SHEET_FIO_COL=2,
        BOT_SHEET_GROUP_COL=1,
        BOT_SHEET_STATUS_COL=11,
        BOT_SHEET_REMARK_COL=12,
        BOT_SHEET_SOCIAL_COLS="4,5,6",
    )
    def test_student_status_uses_state_header_not_week_column(self, client):
        from django.contrib.auth import get_user_model

        owner = get_user_model().objects.create_user(username="bot_owner", password="pass")
        table = SectionTable.objects.create(
            owner=owner,
            title="Real table",
            section_type="rangers",
            content={
                "custom_sheet": {
                    "version": 2,
                    "activeSheetIndex": 0,
                    "sheets": [
                        {
                            "name": "Robo",
                            "data": [
                                [
                                    "",
                                    "Группа",
                                    "ФИО",
                                    "Номер телефона",
                                    "Телеграм",
                                    "Вконтакте",
                                    "ТикТок",
                                    "Ответственный",
                                    "01.04-05.04",
                                    "06.04-12.04",
                                    "13.04-19.04",
                                    "20.04-24.04",
                                    "Состояние",
                                ],
                                [
                                    "",
                                    "ЧПУ 1",
                                    "Иванов Иван",
                                    "",
                                    "@student_tg",
                                    "vk.com/id1",
                                    "cool.tiktok.nick",
                                    "",
                                    "",
                                    "",
                                    "",
                                    "",
                                    "учится",
                                ],
                            ],
                        }
                    ],
                }
            },
        )

        rm = client.post(
            "/api/bot/gateway/",
            {
                "action": "set_student_remark",
                "table_id": table.id,
                "sheet_name": "Robo",
                "student_fio": "Иванов",
                "remark_date": "28.04.2026",
                "remark_text": "после последней недели",
            },
            format="json",
            HTTP_X_CNC_BOT_TOKEN="secret-token",
        )

        assert rm.status_code == status.HTTP_200_OK
        assert rm.data["remark_col"] == 11

        st = client.post(
            "/api/bot/gateway/",
            {
                "action": "set_student_status",
                "table_id": table.id,
                "sheet_name": "Robo",
                "student_fio": "Иванов",
                "status_value": "отчислен",
            },
            format="json",
            HTTP_X_CNC_BOT_TOKEN="secret-token",
        )

        assert st.status_code == status.HTTP_200_OK
        assert st.data["status_col"] == 12

        table.refresh_from_db()
        row = table.content["custom_sheet"]["sheets"][0]["data"][1]
        assert row[11] == "после последней недели"
        assert row[12] == "отчислен"

    @override_settings(
        CNC_BOT_API_SECRET="secret-token",
        CNC_BOT_TABLE_OWNER_USERNAME="bot_owner",
        BOT_SHEET_FIO_COL=0,
        BOT_SHEET_GROUP_COL=1,
        BOT_SHEET_STATUS_COL=2,
        BOT_SHEET_REMARK_COL=3,
        BOT_SHEET_SOCIAL_COLS="4,5",
    )
    def test_get_student_profile_formats_tg_and_tiktok_links(self, client):
        from django.contrib.auth import get_user_model

        owner = get_user_model().objects.create_user(username="bot_owner", password="pass")
        table = SectionTable.objects.create(
            owner=owner,
            title="Social test",
            section_type="rangers",
            content={
                "custom_sheet": {
                    "version": 2,
                    "activeSheetIndex": 0,
                    "sheets": [
                        {
                            "name": "Robo",
                            "data": [
                                ["ФИО", "Группа", "Статус", "Замечания", "ТГ", "ТикТок"],
                                ["Иванов Иван", "Г1", "учится", "", "student_tg", "cool.tiktok.nick"],
                            ],
                        }
                    ],
                }
            },
        )

        resp = client.post(
            "/api/bot/gateway/",
            {
                "action": "get_student_profile",
                "table_id": table.id,
                "sheet_name": "Robo",
                "student_fio": "Иванов",
            },
            format="json",
            HTTP_X_CNC_BOT_TOKEN="secret-token",
        )
        assert resp.status_code == status.HTTP_200_OK
        social = resp.data["student"]["social_profiles"]
        by_label = {item["label"]: item["url"] for item in social}
        assert by_label["TG"] == "https://t.me/student_tg"
        assert by_label["TikTok"] == "https://www.tiktok.com/@cool.tiktok.nick"

    @override_settings(
        CNC_BOT_API_SECRET="secret-token",
        CNC_BOT_TABLE_OWNER_USERNAME="bot_owner",
        BOT_SHEET_FIO_COL=0,
        BOT_SHEET_GROUP_COL=1,
        BOT_SHEET_STATUS_COL=2,
        BOT_SHEET_REMARK_COL=3,
        BOT_SHEET_SOCIAL_COLS="13,14,15",
    )
    def test_get_student_profile_finds_social_columns_by_header(self, client):
        from django.contrib.auth import get_user_model

        owner = get_user_model().objects.create_user(username="bot_owner", password="pass")
        table = SectionTable.objects.create(
            owner=owner,
            title="Social header test",
            section_type="rangers",
            content={
                "custom_sheet": {
                    "version": 2,
                    "activeSheetIndex": 0,
                    "sheets": [
                        {
                            "name": "Robo",
                            "data": [
                                ["ФИО", "Группа", "Статус", "Замечания", "VK", "ТГ", "ТикТок"],
                                ["Иванов Иван", "Г1", "учится", "", "id1", "student_tg", "cool.tiktok.nick"],
                            ],
                        }
                    ],
                }
            },
        )

        resp = client.post(
            "/api/bot/gateway/",
            {
                "action": "get_student_profile",
                "table_id": table.id,
                "sheet_name": "Robo",
                "student_fio": "Иванов",
            },
            format="json",
            HTTP_X_CNC_BOT_TOKEN="secret-token",
        )

        assert resp.status_code == status.HTTP_200_OK
        social = resp.data["student"]["social_profiles"]
        by_label = {item["label"]: item["url"] for item in social}
        assert by_label["VK"] == "https://vk.com/id1"
        assert by_label["TG"] == "https://t.me/student_tg"
        assert by_label["TikTok"] == "https://www.tiktok.com/@cool.tiktok.nick"
