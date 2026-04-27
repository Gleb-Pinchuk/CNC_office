# users/views.py
from django.contrib.auth import get_user_model
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework import generics, permissions, status
from rest_framework.authentication import SessionAuthentication
from rest_framework.authtoken.models import Token
from rest_framework.authtoken.serializers import AuthTokenSerializer  # ✅ ИМПОРТ
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import RegisterSerializer, UserListSerializer

User = get_user_model()


@method_decorator(csrf_exempt, name="dispatch")
class RegisterView(generics.CreateAPIView):
    """Регистрация нового пользователя"""

    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        token, _ = Token.objects.get_or_create(user=user)
        return Response(
            {
                "token": token.key,
                "user": UserListSerializer(user).data,
                "message": "Пользователь успешно зарегистрирован",
            },
            status=status.HTTP_201_CREATED,
        )


@method_decorator(csrf_exempt, name="dispatch")
class LoginView(generics.GenericAPIView):  # ✅ НЕ ObtainAuthToken
    """Вход пользователя — возвращает токен"""

    permission_classes = [permissions.AllowAny]
    authentication_classes = []
    serializer_class = AuthTokenSerializer  # ✅ СТАНДАРТНЫЙ СЕРИАЛИЗАТОР

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        token, _ = Token.objects.get_or_create(user=user)
        return Response({"token": token.key, "user": UserListSerializer(user).data})


@method_decorator(csrf_exempt, name="dispatch")
class UserProfileView(generics.RetrieveAPIView):
    """Данные текущего пользователя"""

    serializer_class = UserListSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user


class UserListView(generics.ListAPIView):
    """Список пользователей"""

    queryset = User.objects.all()
    serializer_class = UserListSerializer
    permission_classes = [permissions.IsAuthenticated]


class SessionToTokenView(APIView):
    """
    После входа через OIDC (сессия) выдать DRF Token для API.
    POST с cookie сессии и заголовком X-CSRFToken (стандарт Django + DRF SessionAuthentication).
    """

    permission_classes = [permissions.IsAuthenticated]
    authentication_classes = [SessionAuthentication]

    def post(self, request, *args, **kwargs):
        token, _ = Token.objects.get_or_create(user=request.user)
        return Response(
            {"token": token.key, "user": UserListSerializer(request.user).data}
        )
