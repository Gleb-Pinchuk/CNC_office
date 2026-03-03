import pytest
from django.contrib.auth import get_user_model
from files.models import StorageFile, StorageFolder

User = get_user_model()

@pytest.fixture
def user():
    return User.objects.create_user(username='testuser', password='testpass123')

@pytest.fixture
def auth_client(client, user):
    client.force_login(user)
    client.force_user = user
    return client

@pytest.fixture
def folder(user):
    return StorageFolder.objects.create(owner=user, name='Test Folder')

@pytest.fixture
def test_file(user, folder):
    from django.core.files.uploadedfile import SimpleUploadedFile
    file = SimpleUploadedFile("test.txt", b"file_content", content_type="text/plain")
    return StorageFile.objects.create(
        owner=user,
        folder=folder,
        file=file,
        size=12,
        mime_type='text/plain'
    )
