from django.urls import include, path
from rest_framework.routers import DefaultRouter

from files.views import (
    AuditLogViewSet,
    FileAccessPermissionViewSet,
    StorageFileViewSet,
    StorageFolderViewSet,
)

from .views import health_check

router = DefaultRouter()
router.register(r"files", StorageFileViewSet, basename="file")
router.register(r"folders", StorageFolderViewSet, basename="folder")
router.register(r"permissions", FileAccessPermissionViewSet, basename="permission")
router.register(r"audit-logs", AuditLogViewSet, basename="audit-log")
urlpatterns = [
    path("", include(router.urls)),
    path("users/", include("users.urls")),
    path("health/", health_check, name="health"),
    path("", include("documents.urls")),
]
