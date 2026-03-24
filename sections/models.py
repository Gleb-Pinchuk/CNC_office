from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class SectionTable(models.Model):
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='section_tables')
    section_type = models.CharField(max_length=20, choices=[
        ('attendance', 'Посещаемость'),
        ('rangers', 'Цифровые рейнджеры'),
        ('statements', 'Ведомости'),
    ])
    title = models.CharField(max_length=255, default='Без названия')
    content = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_shared = models.BooleanField(default=False)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return f'{self.get_section_type_display()}: {self.title}'
    