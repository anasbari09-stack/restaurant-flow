from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView
from django.views.decorators.csrf import ensure_csrf_cookie

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('api.urls')),
    path('menu/', ensure_csrf_cookie(TemplateView.as_view(template_name='menu.html')), name='menu'),
]
