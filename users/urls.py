# users/urls.py
from django.urls import path

from .views import LoginView, RegisterView, UserListView, UserProfileView

app_name = "users"

urlpatterns = [
    path("login/", LoginView.as_view(), name="login"),
    path("register/", RegisterView.as_view(), name="register"),
    path("me/", UserProfileView.as_view(), name="profile"),
    path("", UserListView.as_view(), name="list"),
]
