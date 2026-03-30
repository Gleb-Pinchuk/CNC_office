from django.urls import path
from .views import BotGatewayView, BotHealthView

urlpatterns = [
    path('gateway/', BotGatewayView.as_view(), name='bot-gateway'),
    path('health/', BotHealthView.as_view(), name='bot-health'),
]
