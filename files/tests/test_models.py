import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile

from files.models import AuditLog, FilePermission, StorageFile, StorageFolder


@pytest.mark.django_db
class TestStorageFolderModel:
    def test_create_folder(self, user):
        folder = StorageFolder.objects.create(owner=user, name="My Folder")
        assert folder.name == "My Folder"
        assert folder.owner == user

    def test_folder_string_representation(self, user):
        folder = StorageFolder.objects.create(owner=user, name="Docs")
        assert str(folder) == "Docs"


@pytest.mark.django_db
class TestStorageFileModel:
    def test_create_file(self, user, folder):
        content = b"content"
        file = SimpleUploadedFile("doc.pdf", content, content_type="application/pdf")
        storage_file = StorageFile.objects.create(
            owner=user, folder=folder, file=file, size=100, mime_type="application/pdf"
        )
        assert storage_file.file.name
        # StorageFile.save() normalizes size from uploaded file bytes
        assert storage_file.size == len(content)

    def test_file_string_representation(self, user, folder):
        file = SimpleUploadedFile("readme.txt", b"txt", content_type="text/plain")
        storage_file = StorageFile.objects.create(
            owner=user, folder=folder, file=file, size=3
        )
        assert "readme" in str(storage_file).lower()

    def test_size_mb_calculation(self, user, folder):
        file = SimpleUploadedFile(
            "big.bin", b"x" * 1048576, content_type="application/octet-stream"
        )
        storage_file = StorageFile.objects.create(
            owner=user, folder=folder, file=file, size=1048576
        )
        assert storage_file.size == 1048576


@pytest.mark.django_db
class TestFileAccessPermission:
    def test_create_permission(self, user, folder):
        file = SimpleUploadedFile("shared.txt", b"data", content_type="text/plain")
        storage_file = StorageFile.objects.create(
            owner=user, folder=folder, file=file, size=4
        )

        other_user = get_user_model().objects.create_user(
            username="other", password="pass"
        )
        permission = FilePermission.objects.create(
            file_type="storage_file",
            file_id=storage_file.id,
            user=other_user,
            permission="read",
        )
        assert permission.permission == "read"
        assert permission.user == other_user


@pytest.mark.django_db
class TestAuditLog:
    def test_create_log(self, user):
        log = AuditLog.objects.create(user=user, action="upload", details="Test upload")
        assert log.action == "upload"
        assert log.user == user
        assert log.timestamp is not None
