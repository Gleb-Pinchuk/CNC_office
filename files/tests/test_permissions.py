import pytest
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from files.models import FilePermission

User = get_user_model()


@pytest.mark.django_db
class TestFilePermissions:
    def test_owner_can_share_read_and_revoke(self, auth_client, test_file):
        other = User.objects.create_user(username="other_user", password="pass")

        # share read
        res = auth_client.post(
            f"/api/files/{test_file.id}/share/",
            data={"username": other.username, "permission": "read"},
            content_type="application/json",
        )
        assert res.status_code == status.HTTP_200_OK
        assert FilePermission.objects.filter(
            file_type="storage_file",
            file_id=test_file.id,
            user=other,
            permission="read",
        ).exists()

        # list permissions includes managed one for owner
        res_list = auth_client.get("/api/permissions/")
        assert res_list.status_code == status.HTTP_200_OK
        payload = res_list.data
        items = (
            payload.get("results", payload) if isinstance(payload, dict) else payload
        )
        perm_id = None
        for item in items:
            if (
                item["file_type"] == "storage_file"
                and item["file_id"] == test_file.id
                and item["user"]["username"] == other.username
            ):
                perm_id = item["id"]
                assert item["can_manage"] is True
                break
        assert perm_id is not None

        # revoke
        res_del = auth_client.delete(f"/api/permissions/{perm_id}/")
        assert res_del.status_code == status.HTTP_204_NO_CONTENT
        assert not FilePermission.objects.filter(id=perm_id).exists()

    def test_owner_can_toggle_write(self, auth_client, test_file):
        other = User.objects.create_user(username="other2", password="pass")
        auth_client.post(
            f"/api/files/{test_file.id}/share/",
            data={"username": other.username, "permission": "read"},
            content_type="application/json",
        )
        perm = FilePermission.objects.get(
            file_type="storage_file", file_id=test_file.id, user=other
        )

        res = auth_client.patch(
            f"/api/permissions/{perm.id}/",
            data={"permission": "write"},
            content_type="application/json",
        )
        assert res.status_code == status.HTTP_200_OK
        perm.refresh_from_db()
        assert perm.permission == "write"

    def test_non_owner_cannot_manage(self, auth_client, user, test_file):
        other = User.objects.create_user(username="other3", password="pass")
        # owner shares to other
        auth_client.post(
            f"/api/files/{test_file.id}/share/",
            data={"username": other.username, "permission": "read"},
            content_type="application/json",
        )
        perm = FilePermission.objects.get(
            file_type="storage_file", file_id=test_file.id, user=other
        )

        # other cannot patch/delete
        other_client = APIClient()
        other_token, _ = Token.objects.get_or_create(user=other)
        other_client.credentials(HTTP_AUTHORIZATION=f"Token {other_token.key}")
        res_patch = other_client.patch(
            f"/api/permissions/{perm.id}/",
            data={"permission": "write"},
            content_type="application/json",
        )
        assert res_patch.status_code == status.HTTP_403_FORBIDDEN
        res_del = other_client.delete(f"/api/permissions/{perm.id}/")
        assert res_del.status_code == status.HTTP_403_FORBIDDEN
