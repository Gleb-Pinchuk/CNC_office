# files/models.py
import os
from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()


class StorageFolder(models.Model):
    """Папка для хранения файлов"""
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='folders')
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='subfolders')
    name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Папка'
        verbose_name_plural = 'Папки'
        unique_together = ('owner', 'parent', 'name')
        ordering = ['name']

    def __str__(self):
        return self.name

    @property
    def files_count(self):
        return self.files.count()


class StorageFile(models.Model):
    """
    Файл в хранилище
    ✅ БЕЗ FileExtensionValidator — принимаем ВСЕ типы файлов
    """
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='files')
    folder = models.ForeignKey(StorageFolder, on_delete=models.SET_NULL, null=True, blank=True, related_name='files')
    # ✅ УБРАЛИ validators=[FileExtensionValidator(...)] — теперь любые файлы
    file = models.FileField(upload_to='user_files/%Y/%m/%d/')
    file_name = models.CharField(max_length=255, blank=True)
    size = models.BigIntegerField(default=0)
    size_mb = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    mime_type = models.CharField(max_length=255, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_shared = models.BooleanField(default=False)
    description = models.TextField(blank=True)

    class Meta:
        verbose_name = 'Файл'
        verbose_name_plural = 'Файлы'
        ordering = ['-uploaded_at']
        indexes = [
            models.Index(fields=['owner', 'uploaded_at']),
            models.Index(fields=['is_shared']),
        ]

    def __str__(self):
        return self.file_name or os.path.basename(self.file.name)

    def save(self, *args, **kwargs):
        # Автоматическое определение размера и MIME типа
        if self.file:
            try:
                self.size = self.file.size
                self.size_mb = round(self.size / (1024 * 1024), 2)
            except:
                pass

        # Сохраняем имя файла
        if self.file and not self.file_name:
            self.file_name = os.path.basename(self.file.name)

        # Определяем MIME type
        if self.file and not self.mime_type:
            import mimetypes
            self.mime_type, _ = mimetypes.guess_type(self.file.path)

        super().save(*args, **kwargs)


class FileAccessPermission(models.Model):
    """Доступ к файлу для других пользователей"""
    file = models.ForeignKey(StorageFile, on_delete=models.CASCADE, related_name='permissions')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='file_permissions')
    permission = models.CharField(
        max_length=10,
        choices=[('read', 'Чтение'), ('write', 'Запись')],
        default='read'
    )
    granted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Доступ к файлу'
        verbose_name_plural = 'Доступы к файлам'
        unique_together = ('file', 'user')
        ordering = ['-granted_at']

    def __str__(self):
        return f'{self.user.username} -> {self.file} ({self.permission})'


class FileLock(models.Model):
    """Блокировка файла для редактирования"""
    file = models.ForeignKey(StorageFile, on_delete=models.CASCADE, related_name='locks')
    locked_by = models.ForeignKey(User, on_delete=models.CASCADE)
    locked_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = 'Блокировка файла'
        verbose_name_plural = 'Блокировки файлов'
        ordering = ['-locked_at']

    def __str__(self):
        return f'{self.file} locked by {self.locked_by}'

    def is_expired(self):
        return timezone.now() > self.expires_at


class AuditLog(models.Model):
    """Журнал аудита действий"""
    ACTIONS = [
        ('upload', 'Загрузка файла'),
        ('download', 'Скачивание файла'),
        ('delete', 'Удаление файла'),
        ('share', 'Предоставление доступа'),
        ('unshare', 'Отзыв доступа'),
        ('login', 'Вход в систему'),
        ('logout', 'Выход из системы'),
        ('create_folder', 'Создание папки'),
        ('delete_folder', 'Удаление папки'),
        ('move', 'Перемещение файла'),
        ('rename', 'Переименование'),
    ]

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='audit_logs')
    action = models.CharField(max_length=20, choices=ACTIONS)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    details = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Журнал аудита'
        verbose_name_plural = 'Журналы аудита'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user', 'timestamp']),
            models.Index(fields=['action', 'timestamp']),
        ]

    def __str__(self):
        return f'{self.user} - {self.get_action_display()} - {self.timestamp}'
