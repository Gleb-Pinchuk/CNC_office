from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import FileExtensionValidator

User = get_user_model()


class StorageFolder(models.Model):
    """Папка в хранилище (поддерживает вложенность, разделы как top-level)"""
    TYPE_CHOICES = [
        ('section', 'Раздел (Synology-like: home/public/shares)'),
        ('folder', 'Обычная папка'),
    ]

    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='owned_folders')
    parent = models.ForeignKey('self', null=True, blank=True, on_delete=models.CASCADE, related_name='child_folders')
    name = models.CharField(max_length=255)
    folder_type = models.CharField(max_length=10, choices=TYPE_CHOICES,
                                   default='folder')  # Новое: разделы (parent=None + type='section')
    created_at = models.DateTimeField(auto_now_add=True)
    permissions = models.JSONField(default=dict,
                                   blank=True)  # {'read': [user_ids], 'write': [user_ids], 'public': bool}

    class Meta:
        verbose_name = 'Папка/Раздел'
        verbose_name_plural = 'Папки/Разделы'
        unique_together = ('parent', 'name')  # Уникальность в пределах родителя (owner не обязателен для shared)

    def __str__(self):
        level = self.get_path_depth()  # Рекурсивный путь для UI
        return f"{'  ' * level}{self.name} ({self.get_folder_type_display()})"

    def get_path_depth(self):
        depth = 0
        folder = self
        while folder.parent:
            depth += 1
            folder = folder.parent
        return depth


class StorageFile(models.Model):
    """Файл в хранилище (связь с папкой/разделом)"""
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='owned_files')
    folder = models.ForeignKey(StorageFolder, null=True, blank=True, on_delete=models.CASCADE, related_name='files')
    file = models.FileField(
        upload_to='user_files/%Y/%m/%d/',
        validators=[FileExtensionValidator(allowed_extensions=['pdf', 'docx', 'xlsx', 'csv', 'txt', 'png', 'jpg'])]
        # Ограничим типы
    )
    size = models.BigIntegerField(default=0)
    mime_type = models.CharField(max_length=100, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_shared = models.BooleanField(default=False)
    share_token = models.CharField(max_length=64, blank=True, unique=True)  # Для публичных ссылок

    class Meta:
        verbose_name = 'Файл'
        verbose_name_plural = 'Файлы'
        indexes = [
            models.Index(fields=['owner', 'uploaded_at']),
            models.Index(fields=['folder', 'is_shared']),
        ]

    def __str__(self):
        return self.file.name


class StorageSheet(models.Model):
    """Real-time таблица (spreadsheet как Google Sheets/Synology Office)"""
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sheets')
    folder = models.ForeignKey(StorageFolder, null=True, blank=True, on_delete=models.CASCADE, related_name='sheets')
    name = models.CharField(max_length=255)
    rows = models.IntegerField(default=10)
    cols = models.IntegerField(default=10)
    data = models.JSONField(default=list)  # [{'r':0,'c':0,'v':'value'}, ...] или grid: [[cells],...]
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    version = models.IntegerField(default=0)  # Для optimistic locking real-time

    class Meta:
        verbose_name = 'Таблица (Sheet)'
        verbose_name_plural = 'Таблицы (Sheets)'

    def __str__(self):
        return self.name


class FileAccessPermission(models.Model):
    """Права доступа к файлам/папкам/таблицам"""
    PERMISSION_CHOICES = [
        ('read', 'Только чтение'),
        ('write', 'Чтение и запись'),
        ('admin', 'Полный доступ'),
    ]
    # Расширим на folder/sheet
    content_type = models.CharField(max_length=20, choices=[('file', 'File'), ('folder', 'Folder'), ('sheet', 'Sheet')])
    content_id = models.PositiveIntegerField()  # ID content (file/folder/sheet)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='permissions')
    permission = models.CharField(max_length=10, choices=PERMISSION_CHOICES)
    granted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Право доступа'
        verbose_name_plural = 'Права доступа'
        unique_together = ('content_type', 'content_id', 'user')

    def __str__(self):
        return f"{self.user.username} -> {self.content_type}:{self.content_id} ({self.permission})"


class FileLock(models.Model):
    """Блокировка для real-time (файлы/таблицы)"""
    content_type = models.CharField(max_length=20, choices=[('file', 'File'), ('sheet', 'Sheet')])
    content_id = models.PositiveIntegerField()
    locked_by = models.ForeignKey(User, on_delete=models.CASCADE)
    locked_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)  # TTL для unlock

    class Meta:
        verbose_name = 'Блокировка'
        verbose_name_plural = 'Блокировки'

    def __str__(self):
        return f"{self.content_type}:{self.content_id} locked by {self.locked_by.username}"


class AuditLog(models.Model):
    """Журнал действий"""
    ACTION_CHOICES = [
        ('upload', 'Загрузка файла'),
        ('download', 'Скачивание'),
        ('delete', 'Удаление'),
        ('create_folder', 'Создание папки'),
        ('share', 'Доступ'),
        ('edit_sheet', 'Редактирование таблицы'),
        ('login', 'Вход'),
        ('logout', 'Выход'),
    ]
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='audit_logs')
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    target_type = models.CharField(max_length=20, default='')  # file/folder/sheet
    target_id = models.PositiveIntegerField(null=True, blank=True)
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
        return f"{self.user.username if self.user else 'Anon'} - {self.action} - {self.timestamp}"
