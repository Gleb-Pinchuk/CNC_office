from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from rest_framework.authtoken.views import ObtainAuthToken
from django.contrib.auth import get_user_model
from .serializers import UserSerializer, UserListSerializer, RegisterSerializer

User = get_user_model()


class RegisterView(generics.CreateAPIView):
    """Регистрация нового пользователя"""
    queryset = User.objects.all()
    serializer_class = RegisterSerializer  # Используйте RegisterSerializer с password2
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        # Создаём токен для авто-входа
        token, _ = Token.objects.get_or_create(user=user)

        return Response({
            'token': token.key,
            'user': UserListSerializer(user).data,
            'message': 'Пользователь успешно зарегистрирован'
        }, status=status.HTTP_201_CREATED)


class LoginView(ObtainAuthToken):
    """Вход пользователя — возвращает токен"""
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        token, _ = Token.objects.get_or_create(user=user)

        return Response({
            'token': token.key,
            'user': UserListSerializer(user).data
        })


class UserProfileView(generics.RetrieveAPIView):
    """Данные текущего пользователя"""
    serializer_class = UserListSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user


class UserListView(generics.ListAPIView):
    """Список пользователей (только для авторизованных)"""
    queryset = User.objects.all()
    serializer_class = UserListSerializer
    permission_classes = [permissions.IsAuthenticated]
