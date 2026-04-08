import pytest
from rest_framework import status

from files.models import FilePermission


@pytest.mark.django_db
class TestSectionTablesAPI:
    def test_filter_by_section_type(self, auth_client, section_table):
        res = auth_client.get("/api/section-tables/?section_type=attendance")
        assert res.status_code == status.HTTP_200_OK
        payload = res.data
        items = (
            payload.get("results", payload) if isinstance(payload, dict) else payload
        )
        assert any(t["id"] == section_table.id for t in items)

    def test_save_content_owner(self, auth_client, section_table):
        res = auth_client.post(
            f"/api/section-tables/{section_table.id}/save_content/",
            data={"content": {"custom_sheet": {"data": [["A"]]}}},
            content_type="application/json",
        )
        assert res.status_code == status.HTTP_200_OK

    def test_save_content_denied_for_read_share(self, section_table):
        from django.contrib.auth import get_user_model
        from rest_framework.authtoken.models import Token
        from rest_framework.test import APIClient

        other = get_user_model().objects.create_user(
            username="tbl_other", password="pass"
        )
        FilePermission.objects.create(
            file_type="section_table",
            file_id=section_table.id,
            user=other,
            permission="read",
        )

        other_client = APIClient()
        token, _ = Token.objects.get_or_create(user=other)
        other_client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

        res = other_client.post(
            f"/api/section-tables/{section_table.id}/save_content/",
            data={"content": {"custom_sheet": {"data": [["X"]]}}},
            content_type="application/json",
        )
        assert res.status_code == status.HTTP_403_FORBIDDEN

    def test_export_xlsx(self, auth_client, section_table):
        pytest.importorskip("openpyxl")
        section_table.content = {"custom_sheet": {"data": [["Hello"]]}}
        section_table.save()
        res = auth_client.get(f"/api/section-tables/{section_table.id}/export_xlsx/")
        assert res.status_code == status.HTTP_200_OK
        assert res["Content-Type"].startswith(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        assert len(res.content) > 100

    def test_create_table_uses_section_type_from_request(self, auth_client):
        res = auth_client.post(
            "/api/section-tables/",
            data={
                "title": "New Rangers Table",
                "section_type": "rangers",
                "content": {},
            },
            format="json",
        )

        assert res.status_code == status.HTTP_201_CREATED
        assert res.data["section_type"] == "rangers"

    def test_save_content_rejects_non_object_payload(self, auth_client, section_table):
        res = auth_client.post(
            f"/api/section-tables/{section_table.id}/save_content/",
            data={"content": ["bad"]},
            content_type="application/json",
        )
        assert res.status_code == status.HTTP_400_BAD_REQUEST

    def test_share_table_requires_username(self, auth_client, section_table):
        res = auth_client.post(
            f"/api/section-tables/{section_table.id}/share/",
            data={"permission": "read"},
            content_type="application/json",
        )
        assert res.status_code == status.HTTP_400_BAD_REQUEST

    def test_share_table_updates_existing_permission(self, auth_client, section_table):
        from django.contrib.auth import get_user_model

        other = get_user_model().objects.create_user(
            username="table_reader", password="pass"
        )
        FilePermission.objects.create(
            file_type="section_table",
            file_id=section_table.id,
            user=other,
            permission="read",
        )

        res = auth_client.post(
            f"/api/section-tables/{section_table.id}/share/",
            data={"username": other.username, "permission": "write"},
            content_type="application/json",
        )

        assert res.status_code == status.HTTP_200_OK
        perm = FilePermission.objects.get(
            file_type="section_table", file_id=section_table.id, user=other
        )
        assert perm.permission == "write"

    def test_save_content_allows_write_share(self, section_table):
        from django.contrib.auth import get_user_model
        from rest_framework.authtoken.models import Token
        from rest_framework.test import APIClient

        other = get_user_model().objects.create_user(
            username="table_editor", password="pass"
        )
        FilePermission.objects.create(
            file_type="section_table",
            file_id=section_table.id,
            user=other,
            permission="write",
        )

        other_client = APIClient()
        token, _ = Token.objects.get_or_create(user=other)
        other_client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

        res = other_client.post(
            f"/api/section-tables/{section_table.id}/save_content/",
            data={"content": {"custom_sheet": {"data": [["editable"]]}}},
            content_type="application/json",
        )

        assert res.status_code == status.HTTP_200_OK

    def test_by_section_returns_only_current_users_tables(
        self, auth_client, user, section_table
    ):
        from django.contrib.auth import get_user_model

        from sections.models import SectionTable

        other = get_user_model().objects.create_user(
            username="other_owner", password="pass"
        )
        SectionTable.objects.create(
            owner=other, title="Other table", section_type="attendance", content={}
        )

        res = auth_client.get(
            f"/api/section-tables/by_section/{section_table.section_type}/"
        )

        assert res.status_code == status.HTTP_200_OK
        assert [item["id"] for item in res.data] == [section_table.id]

    def test_save_content_merges_changed_cells(self, auth_client, section_table):
        section_table.content = {
            "custom_sheet": {
                "version": 2,
                "activeSheetIndex": 0,
                "sheets": [
                    {
                        "name": "Лист1",
                        "rows": 2,
                        "cols": 2,
                        "data": [["X1", "Y1"], ["X2", "Y2"]],
                        "styles": {},
                    }
                ],
            }
        }
        section_table.save(update_fields=["content", "updated_at"])

        res = auth_client.post(
            f"/api/section-tables/{section_table.id}/save_content/",
            data={
                "content": {"custom_sheet": {"sheets": []}},
                "changed_cells": [
                    {"sheet_name": "Лист1", "row": 1, "col": 1, "value": "Y2-updated"},
                    {"sheet_name": "Лист1", "row": 0, "col": 0, "value": "X1-updated"},
                ],
            },
            content_type="application/json",
        )
        assert res.status_code == status.HTTP_200_OK
        section_table.refresh_from_db()
        data = section_table.content["custom_sheet"]["sheets"][0]["data"]
        assert data[1][1] == "Y2-updated"
        assert data[0][0] == "X1-updated"

    def test_presence_updates_and_clears(self, auth_client, section_table):
        up = auth_client.post(
            f"/api/section-tables/{section_table.id}/presence/",
            data={"sheet_name": "Лист1", "row": 2, "col": 1, "editing": True},
            content_type="application/json",
        )
        assert up.status_code == status.HTTP_200_OK
        assert any(
            p["row"] == 2 and p["col"] == 1 and p["sheet_name"] == "Лист1"
            for p in up.data["presence"]
        )

        clear = auth_client.post(
            f"/api/section-tables/{section_table.id}/presence/",
            data={"editing": False},
            content_type="application/json",
        )
        assert clear.status_code == status.HTTP_200_OK
        assert clear.data["status"] == "cleared"
        assert clear.data["presence"] == []
