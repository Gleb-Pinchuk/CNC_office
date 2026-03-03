from django.db import models

# Create your models here.
from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class StorageFolder(models.Model):
    """Папка в хранилище (поддерживает вложенность)"""
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='folders')
    parent = models.ForeignKey('self', null=True, blank=True, on_delete=models.CASCADE, related_name='children')
    name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Папка'
        verbose_name_plural = 'Папки'
        unique_together = ('owner', 'parent', 'name')  # Уникальность имени в пределах папки

    def __str__(self):
        return self.name


class StorageFile(models.Model):
    """Файл в хранилище"""
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='files')
    folder = models.ForeignKey(StorageFolder, null=True, blank=True, on_delete=models.CASCADE, related_name='files')
    file = models.FileField(upload_to='user_files/%Y/%m/%d/')
    size = models.BigIntegerField(default=0)
    mime_type = models.CharField(max_length=100, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_shared = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'Файл'
        verbose_name_plural = 'Файлы'
        indexes = [
            models.Index(fields=['owner', 'uploaded_at']),
            models.Index(fields=['is_shared']),
        ]

    def __str__(self):
        return self.file.name


class FileAccessPermission(models.Model):
    """Права доступа к файлам (для мультиаккаунта)"""
    PERMISSION_CHOICES = [
        ('read', 'Только чтение'),
        ('write', 'Чтение и запись'),
        ('admin', 'Полный доступ'),
    ]

    file = models.ForeignKey(StorageFile, on_delete=models.CASCADE, related_name='permissions')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='file_permissions')
    permission = models.CharField(max_length=10, choices=PERMISSION_CHOICES)
    granted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Право доступа'
        verbose_name_plural = 'Права доступа'
        unique_together = ('file', 'user')  # Один пользователь - одна запись на файл

    def __str__(self):
        return f"{self.user.username} -> {self.file.file.name} ({self.permission})"


class FileLock(models.Model):
    """Блокировка файла для редактирования (имитация real-time)"""
    file = models.ForeignKey(StorageFile, on_delete=models.CASCADE, related_name='locks')
    locked_by = models.ForeignKey(User, on_delete=models.CASCADE)
    locked_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Блокировка файла'
        verbose_name_plural = 'Блокировки файлов'

    def __str__(self):
        return f"{self.file.file.name} locked by {self.locked_by.username}"


class AuditLog(models.Model):
    """Журнал действий (требование безопасности)"""
    ACTION_CHOICES = [
        ('upload', 'Загрузка файла'),
        ('download', 'Скачивание файла'),
        ('delete', 'Удаление файла'),
        ('share', 'Предоставление доступа'),
        ('login', 'Вход в систему'),
        ('logout', 'Выход из системы'),
    ]

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    timestamp = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    details = models.TextField(blank=True)

    class Meta:
        verbose_name = 'Лог аудита'
        verbose_name_plural = 'Логи аудита'
        indexes = [
            models.Index(fields=['user', 'timestamp']),
            models.Index(fields=['action', 'timestamp']),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.action} - {self.timestamp}"
