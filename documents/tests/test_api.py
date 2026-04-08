import pytest
from rest_framework import status

from files.models import FilePermission


@pytest.mark.django_db
class TestDocumentsAPI:
    def test_list_documents(self, auth_client, document):
        res = auth_client.get("/api/documents/")
        assert res.status_code == status.HTTP_200_OK
        payload = res.data
        items = (
            payload.get("results", payload) if isinstance(payload, dict) else payload
        )
        assert any(d["id"] == document.id for d in items)

    def test_save_content_owner(self, auth_client, document):
        res = auth_client.post(
            f"/api/documents/{document.id}/save_content/",
            data={"content": {"custom_sheet": {"data": [["A"]]}}},
            content_type="application/json",
        )
        assert res.status_code == status.HTTP_200_OK

    def test_save_content_denied_for_read_share(self, auth_client, user, document):
        from django.contrib.auth import get_user_model

        other = get_user_model().objects.create_user(
            username="doc_other", password="pass"
        )
        FilePermission.objects.create(
            file_type="document", file_id=document.id, user=other, permission="read"
        )

        from rest_framework.authtoken.models import Token
        from rest_framework.test import APIClient

        other_client = APIClient()
        token, _ = Token.objects.get_or_create(user=other)
        other_client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

        res = other_client.post(
            f"/api/documents/{document.id}/save_content/",
            data={"content": {"custom_sheet": {"data": [["X"]]}}},
            content_type="application/json",
        )
        assert res.status_code == status.HTTP_403_FORBIDDEN

    def test_export_xlsx(self, auth_client, document):
        pytest.importorskip("openpyxl")
        document.content = {"custom_sheet": {"data": [["Hello"]]}}
        document.save()
        res = auth_client.get(f"/api/documents/{document.id}/export_xlsx/")
        assert res.status_code == status.HTTP_200_OK
        assert res["Content-Type"].startswith(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        assert len(res.content) > 100

    def test_save_content_rejects_non_object_payload(self, auth_client, document):
        res = auth_client.post(
            f"/api/documents/{document.id}/save_content/",
            data={"content": ["not", "a", "dict"]},
            content_type="application/json",
        )
        assert res.status_code == status.HTTP_400_BAD_REQUEST

    def test_share_document_requires_username(self, auth_client, document):
        res = auth_client.post(
            f"/api/documents/{document.id}/share/",
            data={"permission": "read"},
            content_type="application/json",
        )
        assert res.status_code == status.HTTP_400_BAD_REQUEST

    def test_share_document_rejects_unknown_user(self, auth_client, document):
        res = auth_client.post(
            f"/api/documents/{document.id}/share/",
            data={"username": "ghost_user", "permission": "read"},
            content_type="application/json",
        )
        assert res.status_code == status.HTTP_404_NOT_FOUND

    def test_share_document_rejects_owner(self, auth_client, user, document):
        res = auth_client.post(
            f"/api/documents/{document.id}/share/",
            data={"username": user.username, "permission": "read"},
            content_type="application/json",
        )
        assert res.status_code == status.HTTP_400_BAD_REQUEST

    def test_share_document_updates_existing_permission(self, auth_client, document):
        from django.contrib.auth import get_user_model

        other = get_user_model().objects.create_user(
            username="doc_writer", password="pass"
        )
        FilePermission.objects.create(
            file_type="document", file_id=document.id, user=other, permission="read"
        )

        res = auth_client.post(
            f"/api/documents/{document.id}/share/",
            data={"username": other.username, "permission": "write"},
            content_type="application/json",
        )

        assert res.status_code == status.HTTP_200_OK
        perm = FilePermission.objects.get(
            file_type="document", file_id=document.id, user=other
        )
        assert perm.permission == "write"

    def test_save_content_allows_write_share(self, document):
        from django.contrib.auth import get_user_model
        from rest_framework.authtoken.models import Token
        from rest_framework.test import APIClient

        other = get_user_model().objects.create_user(
            username="doc_editor", password="pass"
        )
        FilePermission.objects.create(
            file_type="document", file_id=document.id, user=other, permission="write"
        )

        other_client = APIClient()
        token, _ = Token.objects.get_or_create(user=other)
        other_client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

        res = other_client.post(
            f"/api/documents/{document.id}/save_content/",
            data={"content": {"custom_sheet": {"data": [["editable"]]}}},
            content_type="application/json",
        )

        assert res.status_code == status.HTTP_200_OK

    def test_save_content_merges_changed_cells(self, auth_client, document):
        document.content = {
            "custom_sheet": {
                "version": 2,
                "activeSheetIndex": 0,
                "sheets": [
                    {
                        "name": "Лист1",
                        "rows": 2,
                        "cols": 2,
                        "data": [["A1", "B1"], ["A2", "B2"]],
                        "styles": {},
                    }
                ],
            }
        }
        document.save(update_fields=["content", "updated_at"])

        res = auth_client.post(
            f"/api/documents/{document.id}/save_content/",
            data={
                "content": {"custom_sheet": {"sheets": []}},
                "changed_cells": [
                    {"sheet_name": "Лист1", "row": 1, "col": 0, "value": "A2-updated"},
                    {"sheet_name": "Лист1", "row": 0, "col": 1, "value": "B1-updated"},
                ],
            },
            content_type="application/json",
        )
        assert res.status_code == status.HTTP_200_OK
        document.refresh_from_db()
        data = document.content["custom_sheet"]["sheets"][0]["data"]
        assert data[1][0] == "A2-updated"
        assert data[0][1] == "B1-updated"

    def test_presence_updates_and_clears(self, auth_client, document):
        up = auth_client.post(
            f"/api/documents/{document.id}/presence/",
            data={"sheet_name": "Лист1", "row": 3, "col": 4, "editing": True},
            content_type="application/json",
        )
        assert up.status_code == status.HTTP_200_OK
        assert any(
            p["row"] == 3 and p["col"] == 4 and p["sheet_name"] == "Лист1"
            for p in up.data["presence"]
        )

        clear = auth_client.post(
            f"/api/documents/{document.id}/presence/",
            data={"editing": False},
            content_type="application/json",
        )
        assert clear.status_code == status.HTTP_200_OK
        assert clear.data["status"] == "cleared"
        assert clear.data["presence"] == []
