from django.urls import path
from .views import (
    MenuView, OrderCreateView, OrderDetailView,
    StaffLoginView, StaffLogoutView, StaffOrderItemsView, StaffOrderItemAdvanceView,
    ReviewCreateView, OrderHelpAlertView, StaffHelpAlertResolveView, AdminStatsView,
    AdminMenuItemListCreateView, AdminMenuItemDetailView,
    AdminTableListCreateView, AdminTableDetailView,
)

urlpatterns = [
    path('menu/', MenuView.as_view()),
    path('orders/', OrderCreateView.as_view()),
    path('orders/<int:pk>/', OrderDetailView.as_view()),
    path('orders/<int:pk>/help/', OrderHelpAlertView.as_view()),
    path('staff/login/', StaffLoginView.as_view()),
    path('staff/logout/', StaffLogoutView.as_view()),
    path('staff/order-items/', StaffOrderItemsView.as_view()),
    path('staff/order-items/<int:pk>/', StaffOrderItemAdvanceView.as_view()),
    path('staff/help-alerts/<int:pk>/resolve/', StaffHelpAlertResolveView.as_view()),
    path('reviews/', ReviewCreateView.as_view()),
    path('admin/stats/', AdminStatsView.as_view()),
    path('admin/menu-items/', AdminMenuItemListCreateView.as_view()),
    path('admin/menu-items/<int:pk>/', AdminMenuItemDetailView.as_view()),
    path('admin/tables/', AdminTableListCreateView.as_view()),
    path('admin/tables/<int:pk>/', AdminTableDetailView.as_view()),
]
