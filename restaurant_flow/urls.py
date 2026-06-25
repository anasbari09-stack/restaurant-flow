from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView
from django.views.decorators.csrf import ensure_csrf_cookie
from api.views import MenuPageView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('api.urls')),
    path('', ensure_csrf_cookie(TemplateView.as_view(template_name='table_hub.html')), name='table_hub'),
    path('menu/', MenuPageView.as_view(), name='menu'),
    path('order/<int:order_id>/', ensure_csrf_cookie(TemplateView.as_view(template_name='order_tracking.html')), name='order_tracking'),
    path('staff/login/', ensure_csrf_cookie(TemplateView.as_view(template_name='staff_login.html')), name='staff_login'),
    path('serveur/login/', ensure_csrf_cookie(TemplateView.as_view(template_name='serveur_login.html')), name='serveur_login'),
    path('serveur/', ensure_csrf_cookie(TemplateView.as_view(template_name='serveur_dashboard.html')), name='serveur_dashboard'),
    path('staff/admin/', ensure_csrf_cookie(TemplateView.as_view(template_name='admin_dashboard.html')), name='admin_dashboard'),
    path('staff/admin/menu/', ensure_csrf_cookie(TemplateView.as_view(template_name='menu_admin.html')), name='menu_admin'),
    path('staff/admin/tables/', ensure_csrf_cookie(TemplateView.as_view(template_name='tables_admin.html')), name='tables_admin'),
    path('staff/<str:role>/', ensure_csrf_cookie(TemplateView.as_view(template_name='staff_dashboard.html')), name='staff_dashboard'),
]
