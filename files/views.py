# files/views.py
import os
import mimetypes
from django.shortcuts import get_object_or_404
from django.utils import timezone
from datetime import timedelta
from django.db import models
from django.contrib.auth import get_user_model
from django.http import FileResponse, HttpResponseBadRequest
from rest_framework import viewsets, permissions, status, parsers
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
        if request.method in permissions.SAFE_METHODS:
            if obj.owner == request.user:
                return True
            return FileAccessPermission.objects.filter(
                file=obj, user=request.user
            ).exists()
        return obj.owner == request.user


class StorageFileViewSet(viewsets.ModelViewSet):
    """ViewSet для файлов"""
    serializer_class = StorageFileSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrShared]
    filter_backends = [DjangoFilterBackend]
    filterset_class = StorageFileFilter
    # ✅ Разрешаем multipart/form-data для загрузки файлов
    parser_classes = [parsers.MultiPartParser, parsers.FormParser, parsers.JSONParser]

    def get_queryset(self):
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
        return queryset.order_by('-uploaded_at')

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

    def _get_file_name(self, file_field):
        """Безопасное получение имени файла"""
        if not file_field or not hasattr(file_field, 'name'):
            return f"File_#{id(file_field) if file_field else 0}"
        try:
            from urllib.parse import unquote
            return unquote(os.path.basename(file_field.name))
        except:
            return os.path.basename(file_field.name)

    def perform_create(self, serializer):
        """✅ Сохранение файла БЕЗ блокировки по MIME-типу"""
        instance = serializer.save(owner=self.request.user)

        # Обновляем метаданные файла
        if instance.file and os.path.exists(instance.file.path):
            instance.size = os.path.getsize(instance.file.path)
            # Определяем MIME type (не блокируем, только определяем)
            mime_type, _ = mimetypes.guess_type(instance.file.path)
            instance.mime_type = mime_type or 'application/octet-stream'
            instance.save(update_fields=['size', 'mime_type'])

        file_name = self._get_file_name(instance.file)
        AuditLog.objects.create(
            user=self.request.user,
            action='upload',
            ip_address=self.get_request_ip(),
            details=f"Загружен файл: {file_name}"
        )

    def perform_destroy(self, instance):
        file_name = self._get_file_name(instance.file)
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

    @action(detail=True, methods=['get'], url_path='download')
    def download(self, request, pk=None):
        """✅ Скачивание файла с правильными заголовками"""
        file_obj = self.get_object()
        file_name = self._get_file_name(file_obj.file)

        AuditLog.objects.create(
            user=request.user,
            action='download',
            ip_address=self.get_request_ip(),
            details=f'Скачан файл: {file_name}'
        )

        if file_obj.file and os.path.exists(file_obj.file.path):
            mime_type, _ = mimetypes.guess_type(file_obj.file.path)
            mime_type = mime_type or 'application/octet-stream'

            response = FileResponse(
                open(file_obj.file.path, 'rb'),
                as_attachment=True,
                filename=file_name,
                content_type=mime_type
            )
            response['Content-Length'] = file_obj.size
            # ✅ Правильное кодирование имени файла для скачивания
            from urllib.parse import quote
            encoded_name = quote(file_name)
            response['Content-Disposition'] = f'attachment; filename*=UTF-8\'\'{encoded_name}'
            return response

        return Response({'detail': 'Файл не найден'}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=True, methods=['post'])
    def lock(self, request, pk=None):
        """Блокировка файла для редактирования"""
        file = self.get_object()
        existing_lock = FileLock.objects.filter(
            file=file, expires_at__gt=timezone.now()
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
        return Response({
            'status': 'locked',
            'expires_at': timezone.now() + timedelta(minutes=30)
        })

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
            file=file, expires_at__gt=timezone.now()
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
            file=file, user=target_user,
            defaults={'permission': permission_type}
        )
        if not created:
            permission.permission = permission_type
            permission.save()

        file_name = self._get_file_name(file.file)
        AuditLog.objects.create(
            user=request.user,
            action='share',
            ip_address=self.get_request_ip(),
            details=f"Предоставлен доступ {permission_type} к файлу {file_name} пользователю {target_user.username}"
        )
        return Response(
            FileAccessPermissionSerializer(permission, context={'request': request}).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK
        )


class StorageFolderViewSet(viewsets.ModelViewSet):
    """ViewSet для папок"""
    serializer_class = StorageFolderSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrShared]
    filter_backends = [DjangoFilterBackend]
    filterset_class = StorageFolderFilter

    def get_queryset(self):
        user = self.request.user
        return StorageFolder.objects.filter(
            models.Q(owner=user) |
            models.Q(permissions__user=user)
        ).distinct().select_related('owner').prefetch_related(
            'permissions', 'permissions__user'
        ).order_by('-created_at')

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


class FileAccessPermissionViewSet(viewsets.ModelViewSet):
    """ViewSet для прав доступа"""
    serializer_class = FileAccessPermissionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return FileAccessPermission.objects.filter(
            models.Q(file__owner=self.request.user) |
            models.Q(user=self.request.user)
        ).select_related('file', 'user')


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet для логов (только чтение)"""
    serializer_class = AuditLogSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['action', 'user']

    def get_queryset(self):
        return AuditLog.objects.filter(
            models.Q(user=self.request.user) |
            models.Q(file__owner=self.request.user) |
            models.Q(file__permissions__user=self.request.user)
        ).distinct().select_related('user').order_by('-timestamp')


class UserSearchViewSet(viewsets.ReadOnlyModelViewSet):
    """Поиск пользователей для предоставления доступа"""
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        query = self.request.query_params.get('q', '')
        if query:
            return User.objects.filter(
                models.Q(username__icontains=query) |
                models.Q(email__icontains=query)
            ).exclude(id=self.request.user.id)[:10]
        return User.objects.none()