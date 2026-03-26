# documents/views.py
from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import action
from .models import Document
from .serializers import DocumentSerializer


class DocumentViewSet(viewsets.ModelViewSet):
    """
    CRUD для документов (Таблицы Luckysheet и Текст)
    """
    queryset = Document.objects.all()
    serializer_class = DocumentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """
        Показываем документы пользователя
        """
        return Document.objects.filter(owner=self.request.user).order_by('-updated_at')

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

    def perform_create(self, serializer):
        """
        При создании документа устанавливаем owner
        """
        serializer.save(owner=self.request.user)

    @action(detail=True, methods=['post'], url_path='save_content')
    def save_content(self, request, pk=None):
        """
        Сохранение содержимого документа (Luckysheet data)
        """
        doc = self.get_object()
        content = request.data.get('content', {})

        if not isinstance(content, dict):
            return Response(
                {'detail': 'content должен быть объектом'},
                status=status.HTTP_400_BAD_REQUEST
            )

        doc.content = content
        doc.save(update_fields=['content', 'updated_at'])

        return Response({
            'status': 'saved',
            'document_id': doc.id,
            'content_keys': list(content.keys())
        })

    @action(detail=True, methods=['post'], url_path='share')
    def share(self, request, pk=None):
        """
        Поделиться документом с другим пользователем
        """
        doc = self.get_object()

        if doc.owner != request.user:
            return Response(
                {'detail': 'Только владелец может предоставлять доступ'},
                status=status.HTTP_403_FORBIDDEN
            )

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

        if user == doc.owner:
            return Response(
                {'detail': 'Вы уже владелец этого документа'},
                status=status.HTTP_400_BAD_REQUEST
            )

        from files.models import FilePermission
        perm, created = FilePermission.objects.get_or_create(
            file_type='document',
            file_id=doc.id,
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
