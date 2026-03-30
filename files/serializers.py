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


class UserShortSerializer(serializers.ModelSerializer):
    """Краткий сериализатор пользователя для отображения"""

    class Meta:
        model = User
        fields = ['id', 'username', 'email']


class StorageFolderSerializer(serializers.ModelSerializer):
    """Сериализатор папки"""
    owner = serializers.ReadOnlyField(source='owner.username')
    files_count = serializers.SerializerMethodField()

    class Meta:
        model = StorageFolder
        fields = ['id', 'name', 'owner', 'parent', 'created_at', 'files_count']
        read_only_fields = ['id', 'owner', 'created_at', 'files_count']

    def get_files_count(self, obj):
        # If view annotated `files_count`, use it directly to prevent N+1 queries.
        if hasattr(obj, '__dict__') and 'files_count' in obj.__dict__:
            return obj.__dict__['files_count']
        return obj.files.count()


class StorageFileSerializer(serializers.ModelSerializer):
    """Сериализатор файла"""
    owner = serializers.ReadOnlyField(source='owner.username')
    folder_name = serializers.SerializerMethodField()
    size_mb = serializers.SerializerMethodField()
    download_url = serializers.SerializerMethodField()
    file_name = serializers.SerializerMethodField()
    shared_with = serializers.SerializerMethodField()

    class Meta:
        model = StorageFile
        fields = [
            'id', 'owner', 'folder', 'folder_name', 'file', 'file_name',
            'size', 'size_mb', 'mime_type', 'uploaded_at', 'updated_at',
            'is_shared', 'download_url', 'shared_with'
        ]
        read_only_fields = [
            'id', 'owner', 'size', 'mime_type',
            'uploaded_at', 'updated_at', 'download_url', 'file_name', 'shared_with'
        ]

    def get_folder_name(self, obj):
        """Безопасное получение имени папки"""
        if obj.folder:
            return obj.folder.name
        return None

    def get_file_name(self, obj):
        """Извлекаем читаемое имя файла из пути"""
        try:
            if obj.file and hasattr(obj.file, 'name'):
                file_name = os.path.basename(obj.file.name)
                try:
                    from urllib.parse import unquote
                    file_name = unquote(file_name)
                except:
                    pass
                return file_name
        except Exception as e:
            print(f"Error getting file name: {e}")
        return 'Без имени'

    def get_size_mb(self, obj):
        """Конвертируем размер в MB"""
        if obj.size:
            return round(obj.size / (1024 * 1024), 2)
        return 0

    def get_download_url(self, obj):
        """Генерируем полный URL для скачивания"""
        try:
            request = self.context.get('request')
            if request and obj.file:
                return request.build_absolute_uri(obj.file.url)
        except Exception as e:
            print(f"Error getting download URL: {e}")
        return None

    def get_shared_with(self, obj):
        """Возвращает список пользователей, с которыми предоставлен доступ"""
        try:
            permissions = obj.permissions.select_related('user').all()
            return [
                {
                    'id': p.user.id,
                    'username': p.user.username,
                    'permission': p.permission
                }
                for p in permissions
            ]
        except:
            return []

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
        file = validated_data.pop('file', None)
        instance = super().create(validated_data)

        if file:
            instance.file = file
            instance.size = getattr(self, '_file_size', file.size)
            instance.mime_type = getattr(self, '_mime_type', 'application/octet-stream')
            instance.save()

        return instance

    def update(self, instance, validated_data):
        """Обновление файла с авто-заполнением размера и mime_type"""
        file = validated_data.pop('file', None)
        instance = super().update(instance, validated_data)

        if file:
            instance.file = file
            instance.size = getattr(self, '_file_size', file.size)
            instance.mime_type = getattr(self, '_mime_type', 'application/octet-stream')
            instance.save()

        return instance


class FileAccessPermissionSerializer(serializers.ModelSerializer):
    """Сериализатор прав доступа"""
    # Для отображения (read-only)
    user = UserShortSerializer(read_only=True)
    # ИСПРАВЛЕНИЕ: используем SerializerMethodField вместо ReadOnlyField
    file_name = serializers.SerializerMethodField(read_only=True)

    # Для записи (write-only) - принимаем ID пользователя или username
    user_id = serializers.IntegerField(write_only=True, required=False)
    username = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = FileAccessPermission
        fields = [
            'id', 'file', 'file_name', 'user', 'user_id', 'username',
            'permission', 'granted_at'
        ]
        read_only_fields = ['id', 'granted_at', 'user', 'file_name']

    def get_file_name(self, obj):
        """Безопасное получение имени файла для прав доступа"""
        try:
            if obj.file and obj.file.file and hasattr(obj.file.file, 'name'):
                file_name = os.path.basename(obj.file.file.name)
                try:
                    from urllib.parse import unquote
                    file_name = unquote(file_name)
                except:
                    pass
                return file_name
        except Exception as e:
            print(f"Error getting permission file name: {e}")
        return 'Файл'

    def validate_user_id(self, value):
        """Проверка существования пользователя по ID"""
        if not User.objects.filter(id=value).exists():
            raise serializers.ValidationError("Пользователь с таким ID не найден")
        return value

    def validate_username(self, value):
        """Проверка существования пользователя по username"""
        if not User.objects.filter(username=value).exists():
            raise serializers.ValidationError("Пользователь с таким именем не найден")
        return value

    def validate(self, attrs):
        """Дополнительная валидация прав доступа"""
        request = self.context.get('request')

        # Определяем целевого пользователя
        user = None
        if 'user_id' in attrs:
            user = User.objects.get(id=attrs['user_id'])
        elif 'username' in attrs:
            user = User.objects.get(username=attrs['username'])

        if not user:
            raise serializers.ValidationError("Необходимо указать user_id или username")

        # Проверка: нельзя дать доступ самому себе
        if request and user == request.user:
            raise serializers.ValidationError('Нельзя предоставить доступ самому себе')

        # Проверка: только владелец файла может предоставлять доступ
        file = attrs.get('file') or (self.instance.file if self.instance else None)
        if request and file and file.owner != request.user:
            raise serializers.ValidationError('Только владелец файла может предоставлять доступ')

        # Проверка: нельзя дать доступ, если он уже есть
        if file and user:
            if FileAccessPermission.objects.filter(file=file, user=user).exists() and not self.instance:
                raise serializers.ValidationError('Доступ этому пользователю уже предоставлен')

        return attrs

    def create(self, validated_data):
        """Создание прав доступа"""
        try:
            # Извлекаем данные пользователя
            user = None
            if 'user_id' in validated_data:
                user = User.objects.get(id=validated_data.pop('user_id'))
            elif 'username' in validated_data:
                user = User.objects.get(username=validated_data.pop('username'))

            if not user:
                raise serializers.ValidationError("Необходимо указать user_id или username")

            file = validated_data.get('file')
            permission = validated_data.get('permission', 'read')
            request = self.context.get('request')

            # Создаём или обновляем право доступа
            perm, created = FileAccessPermission.objects.get_or_create(
                file=file,
                user=user,
                defaults={'permission': permission}
            )

            if not created:
                perm.permission = permission
                perm.save()

            # Логируем действие
            if request and file:
                try:
                    # ИСПРАВЛЕНИЕ: используем os.path.basename вместо file.file_name
                    file_name = os.path.basename(file.file.name) if file.file else f"File #{file.id}"

                    AuditLog.objects.create(
                        user=request.user,
                        action='share',
                        ip_address=request.META.get('REMOTE_ADDR', ''),
                        details=f"Предоставлен доступ {permission} к файлу {file_name} пользователю {user.username}"
                    )
                except Exception as log_error:
                    print(f"AuditLog error: {log_error}")

            return perm

        except User.DoesNotExist:
            raise serializers.ValidationError("Пользователь не найден")
        except Exception as e:
            print(f"Permission create error: {e}")
            raise serializers.ValidationError(f"Ошибка создания доступа: {str(e)}")

    def update(self, instance, validated_data):
        """Обновление прав доступа"""
        # Удаляем write-only поля
        validated_data.pop('user_id', None)
        validated_data.pop('username', None)

        # Обновляем поле permission
        if 'permission' in validated_data:
            instance.permission = validated_data['permission']
            instance.save()

        return instance


class FileLockSerializer(serializers.ModelSerializer):
    """Сериализатор блокировки файла"""
    locked_by = UserShortSerializer(read_only=True)
    locked_by_username = serializers.ReadOnlyField(source='locked_by.username')
    is_expired = serializers.SerializerMethodField()

    class Meta:
        model = FileLock
        fields = ['id', 'file', 'locked_by', 'locked_by_username', 'locked_at', 'expires_at', 'is_expired']
        read_only_fields = ['id', 'locked_at', 'is_expired', 'locked_by', 'locked_by_username']

    def get_is_expired(self, obj):
        from django.utils import timezone
        if obj.expires_at:
            return timezone.now() > obj.expires_at
        return False


class AuditLogSerializer(serializers.ModelSerializer):
    """Сериализатор логов аудита"""
    user = UserShortSerializer(read_only=True)
    user_username = serializers.ReadOnlyField(source='user.username')

    class Meta:
        model = AuditLog
        fields = ['id', 'user', 'user_username', 'action', 'timestamp', 'ip_address', 'details']
        read_only_fields = ['id', 'timestamp', 'user', 'user_username']
