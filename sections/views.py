# sections/views.py
from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import action
from .models import SectionTable
from .serializers import SectionTableSerializer


class SectionTableViewSet(viewsets.ModelViewSet):
    """
    CRUD для таблиц разделов (Посещаемость, Рейнджеры, Ведомости)
    """
    queryset = SectionTable.objects.all()
    serializer_class = SectionTableSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """
        Фильтруем таблицы по section_type из query параметра
        """
        queryset = super().get_queryset()
        section_type = self.request.query_params.get('section_type', None)
        if section_type:
            queryset = queryset.filter(section_type=section_type)
        return queryset

    def perform_create(self, serializer):
        """
        При создании таблицы автоматически устанавливаем owner
        """
        serializer.save(owner=self.request.user)

    @action(detail=True, methods=['post'], url_path='save_content')
    def save_content(self, request, pk=None):
        """
        Сохранение содержимого таблицы (Handsontable data)
        """
        table = self.get_object()
        content = request.data.get('content', {})

        if not isinstance(content, dict):
            return Response(
                {'detail': 'content должен быть объектом'},
                status=status.HTTP_400_BAD_REQUEST
            )

        table.content = content
        table.save()

        return Response({
            'status': 'saved',
            'table_id': table.id,
            'content_keys': list(content.keys())
        })

    @action(detail=True, methods=['post'], url_path='share')
    def share(self, request, pk=None):
        """
        Поделиться таблицей с другим пользователем
        """
        table = self.get_object()
        username = request.data.get('username')
        permission = request.data.get('permission', 'read')

        if not username:
            return Response(
                {'detail': 'Укажите имя пользователя'},
                status=status.HTTP_400_BAD_REQUEST
            )

        from django.contrib.auth import get_user_model
        User = get_user_model()

        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            return Response(
                {'detail': f'Пользователь {username} не найден'},
                status=status.HTTP_404_NOT_FOUND
            )

        # ✅ Проверяем что пользователь не владелец
        if user == table.owner:
            return Response(
                {'detail': 'Вы уже владелец этой таблицы'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # ✅ Создаём или обновляем запись о доступе
        from files.models import FilePermission  # Используем существующую модель
        perm, created = FilePermission.objects.get_or_create(
            file_type='section_table',
            file_id=table.id,
            user=user,
            defaults={'permission': permission}
        )

        if not created:
            perm.permission = permission
            perm.save()

        return Response({
            'status': 'shared',
            'username': username,
            'permission': permission
        })

    @action(detail=False, methods=['get'], url_path='by_section/(?P<section_type>[^/.]+)')
    def by_section(self, request, section_type=None):
        """
        Получить все таблицы для конкретного раздела
        """
        tables = SectionTable.objects.filter(
            section_type=section_type,
            owner=request.user
        )
        serializer = self.get_serializer(tables, many=True)
        return Response(serializer.data)
