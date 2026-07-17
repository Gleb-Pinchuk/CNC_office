import pytest
from django.contrib.auth import get_user_model
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from files.models import StorageFile, StorageFolder
from sections.models import SectionTable

User = get_user_model()


@pytest.fixture
def user():
    return User.objects.create_user(username="testuser", password="testpass123")


@pytest.fixture
def auth_client(client, user):
    api_client = APIClient()
    token, _ = Token.objects.get_or_create(user=user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
    # keep compatibility with existing tests that access force_user
    api_client.force_user = user
    return api_client


@pytest.fixture
def folder(user):
    return StorageFolder.objects.create(owner=user, name="Test Folder")


@pytest.fixture
def test_file(user, folder):
    from django.core.files.uploadedfile import SimpleUploadedFile

    file = SimpleUploadedFile("test.txt", b"file_content", content_type="text/plain")
    return StorageFile.objects.create(
        owner=user, folder=folder, file=file, size=12, mime_type="text/plain"
    )


@pytest.fixture
def document(user):
    pytest.importorskip("documents")
    from documents.models import Document

    return Document.objects.create(
        owner=user, title="Doc1", doc_type="spreadsheet", content={}
    )


@pytest.fixture
def section_table(user):
    return SectionTable.objects.create(
        owner=user, title="Table1", section_type="attendance", content={}
    )
