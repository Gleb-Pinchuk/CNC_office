from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db import models
from django.utils import timezone
from .models import Document, DocumentPermission
from .serializers import DocumentSerializer, DocumentListSerializer, DocumentPermissionSerializer


class IsOwnerOrHasPermission(permissions.BasePermission):
    """Доступ: владелец или есть разрешение"""

    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            if obj.owner == request.user:
                return True
            return DocumentPermission.objects.filter(
                document=obj, user=request.user
            ).exists()
        # Для записи - только владелец или write permission
        if obj.owner == request.user:
            return True
        perm = DocumentPermission.objects.filter(
            document=obj, user=request.user, permission='write'
        ).first()
        return perm is not None


class DocumentViewSet(viewsets.ModelViewSet):
    """ViewSet для документов"""
    serializer_class = DocumentSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrHasPermission]

    def get_queryset(self):
        user = self.request.user
        return Document.objects.filter(
            models.Q(owner=user) |
            models.Q(permissions__user=user) |
            models.Q(is_shared=True)
        ).distinct().select_related('owner', 'folder').prefetch_related('permissions')

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    @action(detail=True, methods=['post'])
    def save_content(self, request, pk=None):
        """Сохранение изменений в документе"""
        doc = self.get_object()
        content = request.data.get('content')

        if content is None:
            return Response({'detail': 'content required'}, status=400)

        # Проверяем права на запись
        if doc.owner != request.user:
            perm = DocumentPermission.objects.filter(
                document=doc, user=request.user, permission='write'
            ).first()
            if not perm:
                return Response({'detail': 'Нет прав на запись'}, status=403)

        doc.content = content
        doc.save()

        return Response({'status': 'saved', 'updated_at': doc.updated_at})

    @action(detail=True, methods=['post'])
    def share(self, request, pk=None):
        """Предоставить доступ к документу"""
        doc = self.get_object()

        if doc.owner != request.user:
            return Response({'detail': 'Только владелец может предоставлять доступ'}, status=403)

        username = request.data.get('username')
        permission_type = request.data.get('permission', 'read')

        from django.contrib.auth import get_user_model
        User = get_user_model()

        try:
            target_user = User.objects.get(username=username)
        except User.DoesNotExist:
            return Response({'detail': 'Пользователь не найден'}, status=404)

        if target_user == request.user:
            return Response({'detail': 'Нельзя предоставить доступ самому себе'}, status=400)

        perm, created = DocumentPermission.objects.get_or_create(
            document=doc, user=target_user,
            defaults={'permission': permission_type}
        )

        if not created:
            perm.permission = permission_type
            perm.save()

        return Response(
            DocumentPermissionSerializer(perm).data,
            status=201 if created else 200
        )


class DocumentPermissionViewSet(viewsets.ModelViewSet):
    """ViewSet для управления доступом к документам"""
    serializer_class = DocumentPermissionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        return DocumentPermission.objects.filter(
            models.Q(document__owner=user) | models.Q(user=user)
        ).select_related('document', 'user').order_by('-granted_at')
