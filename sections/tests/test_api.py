import pytest
from rest_framework import status

from files.models import FilePermission


@pytest.mark.django_db
class TestSectionTablesAPI:
    def test_filter_by_section_type(self, auth_client, section_table):
        res = auth_client.get('/api/section-tables/?section_type=attendance')
        assert res.status_code == status.HTTP_200_OK
        payload = res.data
        items = payload.get('results', payload) if isinstance(payload, dict) else payload
        assert any(t['id'] == section_table.id for t in items)

    def test_save_content_owner(self, auth_client, section_table):
        res = auth_client.post(
            f'/api/section-tables/{section_table.id}/save_content/',
            data={'content': {'custom_sheet': {'data': [['A']]} }},
            content_type='application/json',
        )
        assert res.status_code == status.HTTP_200_OK

    def test_save_content_denied_for_read_share(self, section_table):
        from django.contrib.auth import get_user_model
        from rest_framework.test import APIClient
        from rest_framework.authtoken.models import Token

        other = get_user_model().objects.create_user(username='tbl_other', password='pass')
        FilePermission.objects.create(file_type='section_table', file_id=section_table.id, user=other, permission='read')

        other_client = APIClient()
        token, _ = Token.objects.get_or_create(user=other)
        other_client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        res = other_client.post(
            f'/api/section-tables/{section_table.id}/save_content/',
            data={'content': {'custom_sheet': {'data': [['X']]} }},
            content_type='application/json',
        )
        assert res.status_code == status.HTTP_403_FORBIDDEN

    def test_export_xlsx(self, auth_client, section_table):
        section_table.content = {'custom_sheet': {'data': [['Hello']]} }
        section_table.save()
        res = auth_client.get(f'/api/section-tables/{section_table.id}/export_xlsx/')
        assert res.status_code == status.HTTP_200_OK
        assert res['Content-Type'].startswith('application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        assert len(res.content) > 100

