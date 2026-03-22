from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import DocumentViewSet, DocumentPermissionViewSet

router = DefaultRouter()
router.register(r'documents', DocumentViewSet, basename='document')
router.register(r'document-permissions', DocumentPermissionViewSet, basename='document-permission')

urlpatterns = [
    path('', include(router.urls)),
]
