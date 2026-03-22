from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import health_check
from files.views import (
    StorageFileViewSet,
    StorageFolderViewSet,
    FileAccessPermissionViewSet,
    AuditLogViewSet,
)
router = DefaultRouter()
router.register(r'files', StorageFileViewSet, basename='file')
router.register(r'folders', StorageFolderViewSet, basename='folder')
router.register(r'permissions', FileAccessPermissionViewSet, basename='permission')
router.register(r'audit-logs', AuditLogViewSet, basename='audit-log')
urlpatterns = [
    path('', include(router.urls)),
    path('users/', include('users.urls')),
    path('health/', health_check, name='health'),
    path('', include('documents.urls')),
]
