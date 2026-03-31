import pytest
from rest_framework import status


@pytest.mark.django_db
class TestUserViews:
    def test_register_returns_token_and_user(self, client):
        response = client.post(
            "/api/users/register/",
            {
                "username": "new_user",
                "email": "new_user@example.com",
                "password": "StrongPass123!",
                "password2": "StrongPass123!",
            },
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["user"]["username"] == "new_user"
        assert response.data["token"]

    def test_register_rejects_password_mismatch(self, client):
        response = client.post(
            "/api/users/register/",
            {
                "username": "bad_user",
                "email": "bad_user@example.com",
                "password": "StrongPass123!",
                "password2": "WrongPass123!",
            },
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "password2" in response.data

    def test_login_returns_existing_token(self, client, user):
        user.set_password("testpass123")
        user.save(update_fields=["password"])

        response = client.post(
            "/api/users/login/",
            {"username": user.username, "password": "testpass123"},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["user"]["username"] == user.username
        assert response.data["token"]

    def test_profile_requires_authentication(self, client):
        response = client.get("/api/users/me/")
        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]

    def test_profile_returns_current_user(self, auth_client, user):
        response = auth_client.get("/api/users/me/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["username"] == user.username

    def test_user_list_requires_authentication(self, client):
        response = client.get("/api/users/")
        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]

    def test_user_list_returns_authenticated_users(self, auth_client, user):
        response = auth_client.get("/api/users/")
        assert response.status_code == status.HTTP_200_OK
        assert any(item["username"] == user.username for item in response.data)
