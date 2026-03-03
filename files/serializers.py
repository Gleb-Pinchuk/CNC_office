from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import StorageFolder, StorageFile, FileAccessPermission, FileLock, AuditLog
import mimetypes
import os

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    """Сериализатор пользователя"""

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'date_joined']
        read_only_fields = ['id', 'date_joined']


class StorageFolderSerializer(serializers.ModelSerializer):
    """Сериализатор папки"""
    owner = serializers.ReadOnlyField(source='owner.username')
    files_count = serializers.SerializerMethodField()

    class Meta:
        model = StorageFolder
        fields = ['id', 'name', 'owner', 'parent', 'created_at', 'files_count']
        read_only_fields = ['id', 'owner', 'created_at', 'files_count']

    def get_files_count(self, obj):
        return obj.files.count()


class StorageFileSerializer(serializers.ModelSerializer):
    """Сериализатор файла"""
    owner = serializers.ReadOnlyField(source='owner.username')
    folder_name = serializers.ReadOnlyField(source='folder.name')
    size_mb = serializers.SerializerMethodField()
    download_url = serializers.SerializerMethodField()
    file_name = serializers.SerializerMethodField()

    class Meta:
        model = StorageFile
        fields = [
            'id', 'owner', 'folder', 'folder_name', 'file', 'file_name',
            'size', 'size_mb', 'mime_type', 'uploaded_at', 'updated_at',
            'is_shared', 'download_url'
        ]
        read_only_fields = [
            'id', 'owner', 'size', 'mime_type',
            'uploaded_at', 'updated_at', 'download_url', 'file_name'
        ]

    def get_file_name(self, obj):
        """Извлекаем читаемое имя файла из пути"""
        if obj.file and hasattr(obj.file, 'name'):
            # Получаем последнюю часть пути (имя файла)
            file_name = os.path.basename(obj.file.name)
            # Декодируем URL-encoding если есть
            try:
                from urllib.parse import unquote
                file_name = unquote(file_name)
            except:
                pass
            return file_name
        return ''

    def get_size_mb(self, obj):
        """Конвертируем размер в MB"""
        if obj.size:
            return round(obj.size / (1024 * 1024), 2)
        return 0

    def get_download_url(self, obj):
        """Генерируем полный URL для скачивания"""
        request = self.context.get('request')
        if request and obj.file:
            return request.build_absolute_uri(obj.file.url)
        return None

    def validate_file(self, value):
        """Валидация файла: проверка размера и определение mime_type"""
        if not value:
            raise serializers.ValidationError('Файл не выбран')

        max_size = 100 * 1024 * 1024  # 100MB
        if value.size > max_size:
            raise serializers.ValidationError('Файл слишком большой (макс 100MB)')

        if value.size == 0:
            raise serializers.ValidationError('Пустой файл не может быть загружен')

        # Определяем mime_type по расширению файла
        mime_type = mimetypes.guess_type(value.name)[0] or 'application/octet-stream'

        # Сохраняем во временные атрибуты для использования в create()
        self._file_size = value.size
        self._mime_type = mime_type

        return value

    def create(self, validated_data):
        """Создание файла с авто-заполнением размера и mime_type"""
        # Извлекаем файл из данных
        file = validated_data.pop('file', None)

        # Создаем экземпляр модели с остальными данными
        instance = super().create(validated_data)

        # Если файл был загружен, обновляем размер и mime_type
        if file:
            instance.file = file
            instance.size = getattr(self, '_file_size', file.size)
            instance.mime_type = getattr(self, '_mime_type', 'application/octet-stream')
            instance.save()

        return instance

    def update(self, instance, validated_data):
        """Обновление файла с авто-заполнением размера и mime_type"""
        file = validated_data.pop('file', None)

        # Обновляем остальные поля
        instance = super().update(instance, validated_data)

        # Если новый файл был загружен, обновляем размер и mime_type
        if file:
            instance.file = file
            instance.size = getattr(self, '_file_size', file.size)
            instance.mime_type = getattr(self, '_mime_type', 'application/octet-stream')
            instance.save()

        return instance


class FileAccessPermissionSerializer(serializers.ModelSerializer):
    """Сериализатор прав доступа"""
    user_username = serializers.ReadOnlyField(source='user.username')
    file_name = serializers.ReadOnlyField(source='file.file.name')

    class Meta:
        model = FileAccessPermission
        fields = ['id', 'file', 'file_name', 'user', 'user_username', 'permission', 'granted_at']
        read_only_fields = ['id', 'granted_at']

    def validate_user(self, value):
        """Проверка: нельзя дать доступ самому себе"""
        request = self.context.get('request')
        if request and value == request.user:
            raise serializers.ValidationError('Нельзя предоставить доступ самому себе')
        return value

    def validate_file(self, value):
        """Проверка: только владелец может предоставлять доступ"""
        request = self.context.get('request')
        if request and value.owner != request.user:
            raise serializers.ValidationError('Только владелец файла может предоставлять доступ')
        return value


class FileLockSerializer(serializers.ModelSerializer):
    """Сериализатор блокировки файла"""
    locked_by_username = serializers.ReadOnlyField(source='locked_by.username')
    is_expired = serializers.SerializerMethodField()

    class Meta:
        model = FileLock
        fields = ['id', 'file', 'locked_by', 'locked_by_username', 'locked_at', 'expires_at', 'is_expired']
        read_only_fields = ['id', 'locked_at', 'is_expired']

    def get_is_expired(self, obj):
        from django.utils import timezone
        if obj.expires_at:
            return timezone.now() > obj.expires_at
        return False


class AuditLogSerializer(serializers.ModelSerializer):
    """Сериализатор логов аудита"""
    user_username = serializers.ReadOnlyField(source='user.username')

    class Meta:
        model = AuditLog
        fields = ['id', 'user', 'user_username', 'action', 'timestamp', 'ip_address', 'details']
        read_only_fields = ['id', 'timestamp']
