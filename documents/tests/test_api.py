import pytest
from rest_framework import status

from files.models import FilePermission


@pytest.mark.django_db
class TestDocumentsAPI:
    def test_list_documents(self, auth_client, document):
        res = auth_client.get('/api/documents/')
        assert res.status_code == status.HTTP_200_OK
        payload = res.data
        items = payload.get('results', payload) if isinstance(payload, dict) else payload
        assert any(d['id'] == document.id for d in items)

    def test_save_content_owner(self, auth_client, document):
        res = auth_client.post(
            f'/api/documents/{document.id}/save_content/',
            data={'content': {'custom_sheet': {'data': [['A']]} }},
            content_type='application/json',
        )
        assert res.status_code == status.HTTP_200_OK

    def test_save_content_denied_for_read_share(self, auth_client, user, document):
        from django.contrib.auth import get_user_model

        other = get_user_model().objects.create_user(username='doc_other', password='pass')
        FilePermission.objects.create(file_type='document', file_id=document.id, user=other, permission='read')

        from rest_framework.test import APIClient
        from rest_framework.authtoken.models import Token

        other_client = APIClient()
        token, _ = Token.objects.get_or_create(user=other)
        other_client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        res = other_client.post(
            f'/api/documents/{document.id}/save_content/',
            data={'content': {'custom_sheet': {'data': [['X']]} }},
            content_type='application/json',
        )
        assert res.status_code == status.HTTP_403_FORBIDDEN

    def test_export_xlsx(self, auth_client, document):
        document.content = {'custom_sheet': {'data': [['Hello']]} }
        document.save()
        res = auth_client.get(f'/api/documents/{document.id}/export_xlsx/')
        assert res.status_code == status.HTTP_200_OK
        assert res['Content-Type'].startswith('application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        assert len(res.content) > 100

