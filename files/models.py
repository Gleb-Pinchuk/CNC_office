# files/models.py
from django.db import models
from django.conf import settings
import os


def file_upload_path(instance, filename):
    """
    Путь для загрузки файлов: user_id/year/month/filename
    """
    return f'files/{instance.owner.id}/{timezone.now().strftime("%Y/%m")}/{filename}'


class StorageFile(models.Model):
    """
    Файл в хранилище
    """
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='storage_files',
        verbose_name='Владелец'
    )
    file = models.FileField(
        upload_to=file_upload_path,
        verbose_name='Файл'
    )
    file_name = models.CharField(
        max_length=255,
        verbose_name='Имя файла'
    )
    mime_type = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='MIME тип'
    )
    size = models.BigIntegerField(
        default=0,
        verbose_name='Размер (байты)'
    )
    folder = models.ForeignKey(
        'StorageFolder',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='files',
        verbose_name='Папка'
    )
    uploaded_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата загрузки'
    )

    class Meta:
        verbose_name = 'Файл'
        verbose_name_plural = 'Файлы'
        ordering = ['-uploaded_at']
        indexes = [
            models.Index(fields=['owner', '-uploaded_at']),
            models.Index(fields=['folder', '-uploaded_at']),
        ]

    def __str__(self):
        return self.file_name

    def save(self, *args, **kwargs):
        """
        Автоматически заполняем mime_type и size
        """
        if self.file:
            self.file_name = os.path.basename(self.file.name)
            self.size = self.file.size

            # Определяем mime_type
            import mimetypes
            self.mime_type = mimetypes.guess_type(self.file_name)[0] or 'application/octet-stream'

        super().save(*args, **kwargs)

    @property
    def size_mb(self):
        """
        Размер в МБ для отображения
        """
        return round(self.size / 1024 / 1024, 2)


class StorageFolder(models.Model):
    """
    Папка для файлов
    """
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='storage_folders',
        verbose_name='Владелец'
    )
    name = models.CharField(
        max_length=255,
        verbose_name='Название'
    )
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='children',
        verbose_name='Родительская папка'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата создания'
    )

    class Meta:
        verbose_name = 'Папка'
        verbose_name_plural = 'Папки'
        ordering = ['name']
        unique_together = ['owner', 'name', 'parent']
        indexes = [
            models.Index(fields=['owner', 'parent']),
        ]

    def __str__(self):
        return self.name

    @property
    def files_count(self):
        """
        Количество файлов в папке
        """
        return self.files.count()


class FilePermission(models.Model):
    """
    Доступ к файлу/таблице для другого пользователя
    """
    PERMISSION_CHOICES = [
        ('read', '👁️ Только чтение'),
        ('write', '✏️ Чтение и запись'),
    ]

    FILE_TYPE_CHOICES = [
        ('storage_file', 'Файл'),
        ('section_table', 'Таблица раздела'),
    ]

    file_type = models.CharField(
        max_length=20,
        choices=FILE_TYPE_CHOICES,
        verbose_name='Тип объекта'
    )
    file_id = models.IntegerField(
        verbose_name='ID объекта'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='file_permissions',
        verbose_name='Пользователь'
    )
    permission = models.CharField(
        max_length=10,
        choices=PERMISSION_CHOICES,
        default='read',
        verbose_name='Разрешение'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата предоставления'
    )

    class Meta:
        verbose_name = 'Разрешение'
        verbose_name_plural = 'Разрешения'
        unique_together = ['file_type', 'file_id', 'user']
        indexes = [
            models.Index(fields=['file_type', 'file_id', 'user']),
            models.Index(fields=['user', 'file_type']),
        ]

    def __str__(self):
        return f'{self.user.username} - {self.get_permission_display()} - {self.file_type} #{self.file_id}'

    @property
    def file_name(self):
        """
        Получаем имя файла для отображения
        """
        if self.file_type == 'storage_file':
            try:
                return StorageFile.objects.get(id=self.file_id).file_name
            except StorageFile.DoesNotExist:
                return f'Файл #{self.file_id}'
        elif self.file_type == 'section_table':
            try:
                from sections.models import SectionTable
                return SectionTable.objects.get(id=self.file_id).title
            except:
                return f'Таблица #{self.file_id}'
        return f'{self.file_type} #{self.file_id}'


class AuditLog(models.Model):
    """
    Лог аудита действий пользователя
    """
    ACTION_CHOICES = [
        ('upload', '📤 Загрузка'),
        ('download', '⬇️ Скачивание'),
        ('delete', '🗑️ Удаление'),
        ('share', '🔗 Предоставление доступа'),
        ('login', '🔑 Вход'),
        ('logout', '🚪 Выход'),
        ('create', '➕ Создание'),
        ('update', '✏️ Обновление'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='audit_logs',
        verbose_name='Пользователь'
    )
    action = models.CharField(
        max_length=20,
        choices=ACTION_CHOICES,
        verbose_name='Действие'
    )
    file = models.ForeignKey(
        StorageFile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs',
        verbose_name='Файл'
    )
    details = models.TextField(
        blank=True,
        verbose_name='Детали'
    )
    timestamp = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Время'
    )
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name='IP адрес'
    )

    class Meta:
        verbose_name = 'Лог аудита'
        verbose_name_plural = 'Логи аудита'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user', '-timestamp']),
            models.Index(fields=['action', '-timestamp']),
        ]

    def __str__(self):
        return f'{self.user.username} - {self.get_action_display()} - {self.timestamp}'

    def save(self, *args, **kwargs):
        """
        Автоматически заполняем IP адрес из request если есть
        """
        if not self.ip_address:
            # Пытаемся получить IP из контекста (если вызывается из view)
            import inspect
            frame = inspect.currentframe()
            try:
                while frame:
                    if 'request' in frame.f_locals:
                        request = frame.f_locals['request']
                        self.ip_address = request.META.get('REMOTE_ADDR')
                        break
                    frame = frame.f_back
            finally:
                del frame

        super().save(*args, **kwargs)
