import os
from django.shortcuts import get_object_or_404
from django.utils import timezone
from datetime import timedelta
from django.db import models
from django.contrib.auth import get_user_model
from django.http import FileResponse
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend

from .models import StorageFile, StorageFolder, FileAccessPermission, FileLock, AuditLog
from .serializers import (
    StorageFileSerializer, StorageFolderSerializer,
    FileAccessPermissionSerializer, FileLockSerializer, AuditLogSerializer,
    UserSerializer
)
from .filters import StorageFileFilter, StorageFolderFilter

User = get_user_model()


class IsOwnerOrShared(permissions.BasePermission):
    """Разрешение: владелец или есть доступ"""

    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        # Разрешаем безопасные методы (GET, HEAD, OPTIONS)
        if request.method in permissions.SAFE_METHODS:
            if obj.owner == request.user:
                return True
            has_permission = FileAccessPermission.objects.filter(
                file=obj,
                user=request.user
            ).exists()
            return has_permission
        # Для изменения (PUT, DELETE) - только владелец
        return obj.owner == request.user


class StorageFileViewSet(viewsets.ModelViewSet):
    """ViewSet для файлов"""
    serializer_class = StorageFileSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrShared]
    filter_backends = [DjangoFilterBackend]
    filterset_class = StorageFileFilter

    def get_queryset(self):
        """Только файлы пользователя + общие"""
        user = self.request.user
        queryset = StorageFile.objects.filter(
            models.Q(owner=user) |
            models.Q(permissions__user=user) |
            models.Q(is_shared=True)
        ).distinct().select_related('owner', 'folder').prefetch_related(
            'permissions', 'permissions__user'
        )
        folder_id = self.request.query_params.get('folder', None)
        if folder_id is not None:
            if folder_id == '':
                queryset = queryset.filter(folder__isnull=True)
            else:
                queryset = queryset.filter(folder_id=folder_id)
        return queryset

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

    def perform_create(self, serializer):
        instance = serializer.save(owner=self.request.user)
        AuditLog.objects.create(
            user=self.request.user,
            action='upload',
            ip_address=self.get_request_ip(),
            details=f"Загружен файл: {instance.file_name}"
        )

    def perform_destroy(self, instance):
        file_name = instance.file_name
        instance.delete()
        AuditLog.objects.create(
            user=self.request.user,
            action='delete',
            ip_address=self.get_request_ip(),
            details=f"Удалён файл: {file_name}"
        )

    def get_request_ip(self):
        x_forwarded_for = self.request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0]
        return self.request.META.get('REMOTE_ADDR')

    # ✅ ЭКШОН ДЛЯ СКАЧИВАНИЯ ФАЙЛА
    @action(detail=True, methods=['get'], url_path='download')
    def download(self, request, pk=None):
        """Скачивание файла с проверкой прав"""
        file_obj = self.get_object()  # ← Проверяет права через permission_classes

        # Логируем скачивание
        AuditLog.objects.create(
            user=request.user,
            action='download',
            ip_address=self.get_request_ip(),
            details=f'Скачан файл: {file_obj.file_name}'
        )

        # Отдаём файл
        if file_obj.file and os.path.exists(file_obj.file.path):
            response = FileResponse(
                open(file_obj.file.path, 'rb'),
                as_attachment=True,
                filename=file_obj.file_name
            )
            # ✅ Добавляем заголовки для CORS
            response['Access-Control-Expose-Headers'] = 'Content-Disposition'
            return response

        return Response(
            {'detail': 'Файл не найден на сервере'},
            status=status.HTTP_404_NOT_FOUND
        )

    @action(detail=True, methods=['post'])
    def lock(self, request, pk=None):
        """Блокировка файла для редактирования"""
        file = self.get_object()
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

    @action(detail=True, methods=['post'])
    def share(self, request, pk=None):
        """Предоставить доступ к файлу"""
        file = self.get_object()
        if file.owner != request.user:
            return Response(
                {'detail': 'Только владелец файла может предоставлять доступ'},
                status=status.HTTP_403_FORBIDDEN
            )
        user_id = request.data.get('user_id')
        username = request.data.get('username')
        permission_type = request.data.get('permission', 'read')
        target_user = None
        if user_id:
            try:
                target_user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                return Response(
                    {'detail': 'Пользователь не найден'},
                    status=status.HTTP_404_NOT_FOUND
                )
        elif username:
            try:
                target_user = User.objects.get(username=username)
            except User.DoesNotExist:
                return Response(
                    {'detail': 'Пользователь не найден'},
                    status=status.HTTP_404_NOT_FOUND
                )
        else:
            return Response(
                {'detail': 'Необходимо указать user_id или username'},
                status=status.HTTP_400_BAD_REQUEST
            )
        if target_user == request.user:
            return Response(
                {'detail': 'Нельзя предоставить доступ самому себе'},
                status=status.HTTP_400_BAD_REQUEST
            )
        permission, created = FileAccessPermission.objects.get_or_create(
            file=file,
            user=target_user,
            defaults={'permission': permission_type}
        )
        if not created:
            permission.permission = permission_type
            permission.save()
        AuditLog.objects.create(
            user=request.user,
            action='share',
            ip_address=self.get_request_ip(),
            details=f"Предоставлен доступ {permission_type} к файлу {file.file_name} пользователю {target_user.username}"
        )
        return Response(
            FileAccessPermissionSerializer(permission, context={'request': request}).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK
        )


class StorageFolderViewSet(viewsets.ModelViewSet):
    """ViewSet для папок"""
    serializer_class = StorageFolderSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_class = StorageFolderFilter

    def get_queryset(self):
        user = self.request.user
        return StorageFolder.objects.filter(owner=user)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

    def perform_create(self, serializer):
        instance = serializer.save(owner=self.request.user)
        AuditLog.objects.create(
            user=self.request.user,
            action='create_folder',
            ip_address=self.get_request_ip(),
            details=f"Создана папка: {instance.name}"
        )

    def get_request_ip(self):
        x_forwarded_for = self.request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0]
        return self.request.META.get('REMOTE_ADDR')


class FileAccessPermissionViewSet(viewsets.ModelViewSet):
    """ViewSet для управления правами доступа"""
    serializer_class = FileAccessPermissionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        return FileAccessPermission.objects.filter(
            models.Q(file__owner=user) | models.Q(user=user)
        ).select_related('file', 'user').order_by('-granted_at')

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

    def perform_create(self, serializer):
        file = serializer.validated_data.get('file')
        if file and file.owner != self.request.user:
            raise permissions.PermissionDenied('Только владелец может предоставлять доступ')
        instance = serializer.save()
        user = serializer.validated_data.get('user')
        username = user.username if user else 'unknown'
        AuditLog.objects.create(
            user=self.request.user,
            action='share',
            ip_address=self.get_request_ip(),
            details=f"Предоставлен доступ к файлу {file.file_name if file else 'unknown'} пользователю {username}"
        )

    def get_request_ip(self):
        x_forwarded_for = self.request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0]
        return self.request.META.get('REMOTE_ADDR')

    @action(detail=False, methods=['get'])
    def search_users(self, request):
        """Поиск пользователей для предоставления доступа"""
        query = request.query_params.get('q', '')
        if len(query) < 2:
            return Response([])
        users = User.objects.filter(
            username__icontains=query
        ).exclude(id=request.user.id)[:10]
        serializer = UserSerializer(users, many=True)
        return Response(serializer.data)


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet для просмотра логов (только чтение)"""
    serializer_class = AuditLogSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        return AuditLog.objects.filter(user=user).order_by('-timestamp')
