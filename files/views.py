from django.db.models import Count
from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.renderers import JSONRenderer
from django.db.models import Q
from django.utils import timezone
from django.http import FileResponse
import os
from .models import StorageFile, StorageFolder, FilePermission, AuditLog
from .serializers import (
    StorageFileSerializer,
    StorageFolderSerializer,
    FilePermissionSerializer,
    AuditLogSerializer
)


class StorageFileViewSet(viewsets.ModelViewSet):
    """
    CRUD для файлов
    """
    queryset = StorageFile.objects.all()
    serializer_class = StorageFileSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """
        Показываем файлы пользователя + файлы с общим доступом
        """
        user = self.request.user

        # ✅ Получаем ID файлов, к которым есть доступ через FilePermission
        permitted_file_ids = FilePermission.objects.filter(
            file_type='storage_file',
            user=user
        ).values_list('file_id', flat=True)

        return StorageFile.objects.filter(
            Q(owner=user) | Q(id__in=permitted_file_ids)
        ).distinct().order_by('-uploaded_at')

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

    def perform_create(self, serializer):
        file = serializer.save(owner=self.request.user)
        AuditLog.objects.create(
            user=self.request.user,
            action='upload',
            file=file,
            details=f'Загружен файл: {file.file_name}'
        )

    @action(detail=True, methods=['get'], url_path='download')
    def download(self, request, pk=None):
        file = self.get_object()

        if file.owner != request.user and not FilePermission.objects.filter(
                file_type='storage_file',
                file_id=file.id,
                user=request.user
        ).exists():
            return Response(
                {'detail': 'Нет доступа к файлу'},
                status=status.HTTP_403_FORBIDDEN
            )

        AuditLog.objects.create(
            user=request.user,
            action='download',
            file=file,
            details=f'Скачан файл: {file.file_name}'
        )

        try:
            response = FileResponse(
                open(file.file.path, 'rb'),
                as_attachment=True,
                filename=file.file_name
            )
            response['Content-Length'] = file.size
            return response
        except FileNotFoundError:
            return Response(
                {'detail': 'Файл не найден на сервере'},
                status=status.HTTP_404_NOT_FOUND
            )

    @action(detail=True, methods=['post'], url_path='share')
    def share(self, request, pk=None):
        file = self.get_object()

        if file.owner != request.user:
            return Response(
                {'detail': 'Только владелец может предоставлять доступ'},
                status=status.HTTP_403_FORBIDDEN
            )

        username = request.data.get('username')
        permission = request.data.get('permission', 'read')

        if not username:
            return Response(
                {'detail': 'Укажите имя пользователя'},
                status=status.HTTP_400_BAD_REQUEST
            )

        from django.contrib.auth import get_user_model
        User = get_user_model()

        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            return Response(
                {'detail': f'Пользователь {username} не найден'},
                status=status.HTTP_404_NOT_FOUND
            )

        if user == file.owner:
            return Response(
                {'detail': 'Вы уже владелец этого файла'},
                status=status.HTTP_400_BAD_REQUEST
            )

        perm, created = FilePermission.objects.get_or_create(
            file_type='storage_file',
            file_id=file.id,
            user=user,
            defaults={'permission': permission}
        )

        if not created:
            perm.permission = permission
            perm.save()

        AuditLog.objects.create(
            user=request.user,
            action='share',
            file=file,
            details=f'Предоставлен доступ {username} ({permission})'
        )

        return Response({
            'status': 'shared',
            'username': username,
            'permission': permission
        })

    def destroy(self, request, *args, **kwargs):
        file = self.get_object()
        file_name = file.file_name
        self.perform_destroy(file)

        AuditLog.objects.create(
            user=request.user,
            action='delete',
            details=f'Удалён файл: {file_name}'
        )

        return Response(status=status.HTTP_204_NO_CONTENT)


class StorageFolderViewSet(viewsets.ModelViewSet):
    """
    CRUD для папок
    """
    queryset = StorageFolder.objects.all()
    serializer_class = StorageFolderSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Annotate counts to avoid N+1 queries when rendering folders.
        return (
            StorageFolder.objects.filter(owner=self.request.user)
            .annotate(files_count=Count('files'))
            .order_by('-created_at')
        )

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    def destroy(self, request, *args, **kwargs):
        folder = self.get_object()
        folder_name = folder.name
        self.perform_destroy(folder)

        AuditLog.objects.create(
            user=request.user,
            action='delete',
            details=f'Удалена папка: {folder_name}'
        )

        return Response(status=status.HTTP_204_NO_CONTENT)


class FilePermissionViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Просмотр предоставленных доступов (для раздела "Общий доступ")
    """
    serializer_class = FilePermissionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_renderer_classes(self):
        """✅ Возвращаем только JSON рендерер"""
        return [JSONRenderer]

    def get_queryset(self):
        """
        ✅ ИСПРАВЛЕНО: Работает с GenericForeignKey (file_type + file_id)

        Показываем:
        1. Доступы, которые даны этому пользователю
        2. Доступы к объектам, которыми владеет этот пользователь
        """
        user = self.request.user

        # 1️⃣ Доступы, которые даны этому пользователю
        given_to_user = FilePermission.objects.filter(user=user)

        # 2️⃣ Доступы к объектам, которыми владеет этот пользователь
        # (т.к. GenericForeignKey — фильтруем по file_type + file_id)
        from .models import StorageFile
        from documents.models import Document
        from sections.models import SectionTable

        file_ids = list(StorageFile.objects.filter(owner=user).values_list('id', flat=True))
        doc_ids = list(Document.objects.filter(owner=user).values_list('id', flat=True))
        table_ids = list(SectionTable.objects.filter(owner=user).values_list('id', flat=True))

        owned_permissions = FilePermission.objects.filter(
            Q(file_type='storage_file', file_id__in=file_ids) |
            Q(file_type='document', file_id__in=doc_ids) |
            Q(file_type='section_table', file_id__in=table_ids)
        )

        # ✅ Объединяем оба запроса
        return (given_to_user | owned_permissions).select_related('user').distinct().order_by('-created_at')


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Просмотр логов аудита (для раздела "Логи")
    """
    serializer_class = AuditLogSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_renderer_classes(self):
        """✅ Возвращаем только JSON рендерер"""
        return [JSONRenderer]

    def get_queryset(self):
        """
        Показываем логи текущего пользователя
        """
        return AuditLog.objects.filter(user=self.request.user).order_by('-timestamp')
