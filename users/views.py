from rest_framework import generics, permissions
from rest_framework.response import Response
from rest_framework import status
from rest_framework.views import APIView
from django.contrib.auth import get_user_model
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from .serializers import UserSerializer, UserListSerializer

User = get_user_model()


@method_decorator(csrf_exempt, name='dispatch')
class RegisterView(APIView):
    """
    Регистрация нового пользователя

    Примечание: CSRF отключен для публичной регистрации,
    так как у новых пользователей ещё нет CSRF токена.
    Для авторизованных операций (вход, файлы) CSRF обязателен.
    """
    permission_classes = []  # Публичный доступ
    authentication_classes = []  # Не требуем аутентификацию

    def post(self, request):
        # Валидация данных
        serializer = UserSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )

        # Создание пользователя
        try:
            user = serializer.save()

            return Response({
                'user': UserListSerializer(user).data,
                'message': 'Пользователь успешно зарегистрирован'
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response(
                {'detail': f'Ошибка создания пользователя: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class UserListView(generics.ListAPIView):
    """
    Список пользователей

    Доступно только для авторизованных пользователей.
    CSRF защита включена.
    """
    queryset = User.objects.all()
    serializer_class = UserListSerializer
    permission_classes = [permissions.IsAuthenticated]
