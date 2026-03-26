# sections/models.py
from django.db import models
from django.conf import settings


class SectionTable(models.Model):
    """
    Таблица для разделов (Посещаемость, Рейнджеры, Ведомости)
    """
    SECTION_TYPE_CHOICES = [
        ('attendance', '📊 Посещаемость'),
        ('rangers', '🤖 Цифровые рейнджеры'),
        ('statements', '📋 Ведомости'),
    ]

    title = models.CharField(max_length=255, verbose_name='Название')
    section_type = models.CharField(
        max_length=50,
        choices=SECTION_TYPE_CHOICES,
        verbose_name='Тип раздела'
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='section_tables',
        verbose_name='Владелец'
    )
    content = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Содержимое (Luckysheet data)'
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Дата обновления')

    class Meta:
        verbose_name = 'Таблица раздела'
        verbose_name_plural = 'Таблицы разделов'
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['section_type', 'owner']),
            models.Index(fields=['owner', '-updated_at']),
        ]

    def __str__(self):
        return f'{self.get_section_type_display()} - {self.title}'

    @property
    def owner_username(self):
        return self.owner.username
