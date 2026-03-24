from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class Document(models.Model):
    """Онлайн-документ (таблица)"""
    DOC_TYPES = [
        ('spreadsheet', 'Таблица'),
        ('text', 'Текст'),
        ('presentation', 'Презентация'),
    ]

    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='documents')
    title = models.CharField(max_length=255)
    doc_type = models.CharField(max_length=20, choices=DOC_TYPES, default='spreadsheet')
    content = models.JSONField(default=dict, blank=True)  # Данные таблицы
    folder = models.ForeignKey('files.StorageFolder', on_delete=models.SET_NULL, null=True, blank=True,
                               related_name='documents')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_shared = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'Документ'
        verbose_name_plural = 'Документы'
        ordering = ['-updated_at']

    def __str__(self):
        return f'{self.title} ({self.get_doc_type_display()})'


class DocumentEdit(models.Model):
    """История редактирования документа"""
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='edits')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    changes = models.JSONField()  # Что изменилось
    edited_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Редактирование'
        verbose_name_plural = 'Редактирования'
        ordering = ['-edited_at']


class DocumentPermission(models.Model):
    """Доступ к документу"""
    PERMISSION_TYPES = [
        ('read', 'Чтение'),
        ('write', 'Запись'),
        ('admin', 'Администратор'),
    ]

    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='permissions')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    permission = models.CharField(max_length=10, choices=PERMISSION_TYPES, default='read')
    granted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Доступ к документу'
        verbose_name_plural = 'Доступы к документам'
        unique_together = ('document', 'user')
