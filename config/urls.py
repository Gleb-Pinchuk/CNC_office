from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView
from django.views.static import serve

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('api.urls')),
    path('api-auth/', include('rest_framework.urls')),

    path('', TemplateView.as_view(template_name='landing.html'), name='landing'),

    path('app/', TemplateView.as_view(template_name='index.html'), name='app'),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

    frontend_dir = str(settings.BASE_DIR / 'frontend')
    urlpatterns += [
        path('style.css', serve, {'document_root': frontend_dir, 'path': 'style.css'}),
        path('app.js', serve, {'document_root': frontend_dir, 'path': 'app.js'}),
        path('landing.css', serve, {'document_root': frontend_dir, 'path': 'landing.css'}),
        path('landing.js', serve, {'document_root': frontend_dir, 'path': 'landing.js'}),
    ]
