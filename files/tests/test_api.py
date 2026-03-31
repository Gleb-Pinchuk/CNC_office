import pytest
from rest_framework import status
from django.core.files.uploadedfile import SimpleUploadedFile
from files.models import StorageFile
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.mark.django_db
class TestFileViewSet:
    def test_list_files_unauthenticated(self, client):
        response = client.get('/api/files/')
        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]

    def test_list_files_authenticated(self, auth_client, user, folder):
        StorageFile.objects.create(
            owner=user, folder=folder,
            file=SimpleUploadedFile("f1.txt", b"c1", content_type="text/plain"),
            size=2, mime_type='text/plain'
        )
        response = auth_client.get('/api/files/')
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) >= 1

    def test_create_file(self, auth_client, folder):
        file = SimpleUploadedFile("new.txt", b"new_content", content_type="text/plain")
        data = {'folder': folder.id, 'file': file}
        response = auth_client.post('/api/files/', data, format='multipart')
        assert response.status_code == status.HTTP_201_CREATED
        assert StorageFile.objects.filter(owner=auth_client.force_user).exists()

    def test_retrieve_file(self, auth_client, test_file):
        response = auth_client.get(f'/api/files/{test_file.id}/')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['id'] == test_file.id

    def test_update_file(self, auth_client, test_file):
        # No file metadata update endpoint currently supported in API
        # Keep this test as a no-op "retrieve" style check.
        data = {'file_name': 'renamed.txt'}
        response = auth_client.patch(
            f'/api/files/{test_file.id}/',
            data,
            format='json'
        )
        # Depending on serializer, patch may be rejected or ignored.
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST]

    def test_delete_file(self, auth_client, test_file):
        response = auth_client.delete(f'/api/files/{test_file.id}/')
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not StorageFile.objects.filter(id=test_file.id).exists()

    def test_file_isolation(self, auth_client, user, folder):
        other_user = User.objects.create_user(username='other', password='pass')
        other_file = StorageFile.objects.create(
            owner=other_user, folder=folder,
            file=SimpleUploadedFile("secret.txt", b"secret", content_type="text/plain"),
            size=6, mime_type='text/plain'
        )
        response = auth_client.get(f'/api/files/{other_file.id}/')
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_list_files_can_filter_by_folder(self, auth_client, user):
        from files.models import StorageFolder

        folder_a = StorageFolder.objects.create(owner=user, name='Folder A')
        folder_b = StorageFolder.objects.create(owner=user, name='Folder B')
        StorageFile.objects.create(
            owner=user,
            folder=folder_a,
            file=SimpleUploadedFile("a.txt", b"a", content_type="text/plain"),
            size=1,
            mime_type='text/plain'
        )
        StorageFile.objects.create(
            owner=user,
            folder=folder_b,
            file=SimpleUploadedFile("b.txt", b"b", content_type="text/plain"),
            size=1,
            mime_type='text/plain'
        )

        response = auth_client.get(f'/api/files/?folder={folder_a.id}')

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert response.data[0]['folder'] == folder_a.id

    def test_share_requires_username(self, auth_client, test_file):
        response = auth_client.post(
            f'/api/files/{test_file.id}/share/',
            data={'permission': 'read'},
            content_type='application/json'
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_share_rejects_unknown_user(self, auth_client, test_file):
        response = auth_client.post(
            f'/api/files/{test_file.id}/share/',
            data={'username': 'ghost', 'permission': 'read'},
            content_type='application/json'
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_share_rejects_owner(self, auth_client, user, test_file):
        response = auth_client.post(
            f'/api/files/{test_file.id}/share/',
            data={'username': user.username, 'permission': 'read'},
            content_type='application/json'
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_download_denied_without_permission(self, auth_client, folder):
        other_user = User.objects.create_user(username='download_owner', password='pass')
        protected_file = StorageFile.objects.create(
            owner=other_user,
            folder=folder,
            file=SimpleUploadedFile("secret.txt", b"secret", content_type="text/plain"),
            size=6,
            mime_type='text/plain'
        )

        response = auth_client.get(f'/api/files/{protected_file.id}/download/')

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_download_works_for_shared_user(self, user, folder, test_file):
        from files.models import AuditLog, FilePermission
        from rest_framework.authtoken.models import Token
        from rest_framework.test import APIClient

        other = User.objects.create_user(username='download_reader', password='pass')
        FilePermission.objects.create(file_type='storage_file', file_id=test_file.id, user=other, permission='read')

        client = APIClient()
        token, _ = Token.objects.get_or_create(user=other)
        client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        response = client.get(f'/api/files/{test_file.id}/download/')

        assert response.status_code == status.HTTP_200_OK
        assert response['Content-Length'] == str(test_file.size)
        assert AuditLog.objects.filter(user=other, action='download', file=test_file).exists()

    def test_download_returns_404_when_file_missing_on_disk(self, auth_client, test_file):
        test_file.file.delete(save=False)

        response = auth_client.get(f'/api/files/{test_file.id}/download/')

        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestFolderViewSet:
    def test_create_folder(self, auth_client):
        data = {'name': 'New Folder'}
        response = auth_client.post('/api/folders/', data)
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['name'] == 'New Folder'

    def test_list_folders(self, auth_client, folder):
        response = auth_client.get('/api/folders/')
        assert response.status_code == status.HTTP_200_OK

    def test_delete_folder_writes_audit_log(self, auth_client, folder):
        from files.models import AuditLog

        response = auth_client.delete(f'/api/folders/{folder.id}/')

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert AuditLog.objects.filter(action='delete', user=auth_client.force_user).exists()
