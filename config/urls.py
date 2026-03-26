# config/urls.py
from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView
from rest_framework.routers import DefaultRouter

from files.views import StorageFileViewSet, StorageFolderViewSet
from documents.views import DocumentViewSet
from sections.views import SectionTableViewSet

router = DefaultRouter()
router.register(r'files', StorageFileViewSet, basename='file')
router.register(r'folders', StorageFolderViewSet, basename='folder')
router.register(r'documents', DocumentViewSet, basename='document')
router.register(r'section-tables', SectionTableViewSet, basename='section-table')

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include(router.urls)),
    path('api/auth/', include('rest_framework.urls')),
    path('api/users/', include('users.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

urlpatterns += [
    re_path(r'^.*$', TemplateView.as_view(template_name='index.html')),
]
