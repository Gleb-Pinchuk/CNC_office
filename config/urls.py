# config/urls.py
from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView
from django.views.static import serve
from rest_framework.routers import DefaultRouter
from rest_framework.authtoken.views import obtain_auth_token

from files.views import StorageFileViewSet, StorageFolderViewSet, FilePermissionViewSet, AuditLogViewSet
from documents.views import DocumentViewSet
from sections.views import SectionTableViewSet

router = DefaultRouter()
router.register(r'files', StorageFileViewSet, basename='file')
router.register(r'folders', StorageFolderViewSet, basename='folder')
router.register(r'documents', DocumentViewSet, basename='document')
router.register(r'section-tables', SectionTableViewSet, basename='section-table')
router.register(r'permissions', FilePermissionViewSet, basename='permission')
router.register(r'audit-logs', AuditLogViewSet, basename='audit-log')

urlpatterns = [
    path('admin/', admin.site.urls),

    path('api/', include(router.urls)),
    path('api/bot/', include('bot_api.urls')),
    path('api/users/', include('users.urls')),
    path('api/auth/token/login/', obtain_auth_token, name='token-login'),
    path('api/auth/', include('rest_framework.urls')),

    path('static/<path:path>', serve, {'document_root': settings.STATIC_ROOT}),
    path('media/<path:path>', serve, {'document_root': settings.MEDIA_ROOT}),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

urlpatterns += [
    re_path(r'^(?!api/|static/|media/|admin/|favicon\.ico).*$', TemplateView.as_view(template_name='index.html')),
]
