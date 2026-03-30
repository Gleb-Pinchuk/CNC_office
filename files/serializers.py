from rest_framework import serializers

from .models import StorageFile, StorageFolder, FilePermission, AuditLog
from users.serializers import UserListSerializer


class StorageFileSerializer(serializers.ModelSerializer):
    """
    Сериализатор для файлов
    """
    owner = UserListSerializer(read_only=True)
    owner_username = serializers.ReadOnlyField(source='owner.username')
    size_mb = serializers.ReadOnlyField()

    class Meta:
        model = StorageFile
        fields = [
            'id',
            'file',
            'file_name',
            'mime_type',
            'size',
            'size_mb',
            'owner',
            'owner_username',
            'folder',
            'uploaded_at',
        ]
        read_only_fields = ['owner', 'size', 'size_mb', 'mime_type', 'uploaded_at']


class StorageFolderSerializer(serializers.ModelSerializer):
    """
    Сериализатор для папок
    """
    owner = UserListSerializer(read_only=True)
    owner_username = serializers.ReadOnlyField(source='owner.username')
    files_count = serializers.SerializerMethodField()

    class Meta:
        model = StorageFolder
        fields = [
            'id',
            'name',
            'owner',
            'owner_username',
            'parent',
            'files_count',
            'created_at',
        ]
        read_only_fields = ['owner', 'files_count', 'created_at']

    def get_files_count(self, obj):
        # Prefer annotated value from queryset to avoid N+1 DB queries.
        if hasattr(obj, '__dict__') and 'files_count' in obj.__dict__:
            return obj.__dict__['files_count']
        # Fallback for safety.
        try:
            return obj.files.count()
        except Exception:
            return 0


class FilePermissionSerializer(serializers.ModelSerializer):
    """
    Сериализатор для разрешений доступа
    """
    user = UserListSerializer(read_only=True)
    file_name = serializers.ReadOnlyField()

    class Meta:
        model = FilePermission
        fields = [
            'id',
            'file_type',
            'file_id',
            'file_name',
            'user',
            'permission',
            'created_at',
        ]
        read_only_fields = ['file_name', 'created_at']


class AuditLogSerializer(serializers.ModelSerializer):
    """
    Сериализатор для логов аудита
    """
    user = UserListSerializer(read_only=True)
    user_username = serializers.ReadOnlyField(source='user.username')
    file = StorageFileSerializer(read_only=True)

    class Meta:
        model = AuditLog
        fields = [
            'id',
            'user',
            'user_username',
            'action',
            'file',
            'details',
            'timestamp',
            'ip_address',
        ]
        read_only_fields = ['user', 'timestamp', 'ip_address']
