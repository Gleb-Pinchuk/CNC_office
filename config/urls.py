# config/urls.py
from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView
from rest_framework.routers import DefaultRouter
from rest_framework.authtoken.views import obtain_auth_token

from files.views import StorageFileViewSet, StorageFolderViewSet
from documents.views import DocumentViewSet
from sections.views import SectionTableViewSet

# ✅ Регистрация роутеров
router = DefaultRouter()
router.register(r'files', StorageFileViewSet, basename='file')
router.register(r'folders', StorageFolderViewSet, basename='folder')
router.register(r'documents', DocumentViewSet, basename='document')
router.register(r'section-tables', SectionTableViewSet, basename='section-table')

# ✅ Основные URL-паттерны
urlpatterns = [
    path('admin/', admin.site.urls),

    # ✅ API роуты
    path('api/', include(router.urls)),

    # ✅ Пользователи
    path('api/users/', include('users.urls')),

    # ✅ Стандартный DRF токен логин (альтернатива)
    path('api/auth/token/login/', obtain_auth_token, name='token-login'),
    path('api/auth/', include('rest_framework.urls')),
]

# ✅ Статика в режиме отладки
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# ✅ SPA catch-all: отдаём index.html для всех не-API путей
# ⚠️ Должен быть ПОСЛЕДНИМ и БЕЗ условия DEBUG!
urlpatterns += [
    re_path(r'^.*$', TemplateView.as_view(template_name='index.html')),
]
