from django.shortcuts import render

# Create your views here.
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from datetime import timedelta

from .models import StorageFile, StorageFolder, FileAccessPermission, FileLock, AuditLog
from .serializers import (
    StorageFileSerializer, StorageFolderSerializer,
    FileAccessPermissionSerializer, FileLockSerializer, AuditLogSerializer
)
from .filters import StorageFileFilter, StorageFolderFilter
from django.db import models

class IsOwnerOrShared(permissions.BasePermission):
    """Разрешение: владелец или есть доступ"""

    def has_object_permission(self, request, view, obj):
        if obj.owner == request.user:
            return True
        return FileAccessPermission.objects.filter(
            file=obj, user=request.user
        ).exists()


class StorageFileViewSet(viewsets.ModelViewSet):
    """ViewSet для файлов (требование: базовые классы DRF)"""
    serializer_class = StorageFileSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrShared]
    filter_backends = [DjangoFilterBackend]
    filterset_class = StorageFileFilter

    def get_queryset(self):
        """Только файлы пользователя + общие (требование: ORM без SQL)"""
        user = self.request.user
        queryset = StorageFile.objects.filter(
            models.Q(owner=user) |
            models.Q(permissions__user=user) |
            models.Q(is_shared=True)
        ).distinct()
        folder_id = self.request.query_params.get('folder', None)
        if folder_id is not None:
            if folder_id == '':
                queryset = queryset.filter(folder__isnull=True)
            else:
                queryset = queryset.filter(folder_id=folder_id)

        return queryset

    def perform_create(self, serializer):
        """Автосохранение владельца при загрузке"""
        serializer.save(owner=self.request.user)

        # Логирование действия
        AuditLog.objects.create(
            user=self.request.user,
            action='upload',
            ip_address=self.get_request_ip(),
            details=f"Uploaded: {serializer.instance.file.name}"
        )

    def perform_destroy(self, instance):
        """Логирование удаления"""
        AuditLog.objects.create(
            user=self.request.user,
            action='delete',
            ip_address=self.get_request_ip(),
            details=f"Deleted: {instance.file.name}"
        )
        instance.delete()

    def get_request_ip(self):
        x_forwarded_for = self.request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0]
        return self.request.META.get('REMOTE_ADDR')

    @action(detail=True, methods=['post'])
    def lock(self, request, pk=None):
        """Блокировка файла для редактирования"""
        file = self.get_object()

        # Проверка: не заблокирован ли уже
        existing_lock = FileLock.objects.filter(
            file=file,
            expires_at__gt=timezone.now()
        ).first()

        if existing_lock and existing_lock.locked_by != request.user:
            return Response(
                {'error': 'Файл заблокирован другим пользователем'},
                status=status.HTTP_409_CONFLICT
            )

        FileLock.objects.update_or_create(
            file=file,
            defaults={
                'locked_by': request.user,
                'expires_at': timezone.now() + timedelta(minutes=30)
            }
        )

        return Response({'status': 'locked', 'expires_at': timezone.now() + timedelta(minutes=30)})

    @action(detail=True, methods=['post'])
    def unlock(self, request, pk=None):
        """Снятие блокировки"""
        file = self.get_object()
        FileLock.objects.filter(file=file, locked_by=request.user).delete()
        return Response({'status': 'unlocked'})

    @action(detail=True, methods=['get'])
    def lock_status(self, request, pk=None):
        """Проверка статуса блокировки"""
        file = self.get_object()
        lock = FileLock.objects.filter(
            file=file,
            expires_at__gt=timezone.now()
        ).first()

        if lock:
            return Response(FileLockSerializer(lock).data)
        return Response({'status': 'unlocked'})


class StorageFolderViewSet(viewsets.ModelViewSet):
    """ViewSet для папок"""
    serializer_class = StorageFolderSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_class = StorageFolderFilter

    def get_queryset(self):
        user = self.request.user
        return StorageFolder.objects.filter(owner=user)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


class FileAccessPermissionViewSet(viewsets.ModelViewSet):
    """ViewSet для управления правами доступа"""
    serializer_class = FileAccessPermissionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        return FileAccessPermission.objects.filter(
            models.Q(file__owner=user) | models.Q(user=user)
        )

    def perform_create(self, serializer):
        file = serializer.validated_data['file']
        if file.owner != self.request.user:
            raise permissions.PermissionDenied('Только владелец может предоставлять доступ')

        serializer.save()

        AuditLog.objects.create(
            user=self.request.user,
            action='share',
            ip_address=self.request.META.get('REMOTE_ADDR'),
            details=f"Shared {file.file.name} with {serializer.validated_data['user'].username}"
        )


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet для просмотра логов (только чтение)"""
    serializer_class = AuditLogSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        return AuditLog.objects.filter(user=user).order_by('-timestamp')
