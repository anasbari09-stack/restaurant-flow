from django.urls import path
from .views import (
    MenuView, OrderCreateView, OrderDetailView,
    StaffLoginView, StaffLogoutView, StaffOrderItemsView, StaffOrderItemAdvanceView,
)

urlpatterns = [
    path('menu/', MenuView.as_view()),
    path('orders/', OrderCreateView.as_view()),
    path('orders/<int:pk>/', OrderDetailView.as_view()),
    path('staff/login/', StaffLoginView.as_view()),
    path('staff/logout/', StaffLogoutView.as_view()),
    path('staff/order-items/', StaffOrderItemsView.as_view()),
    path('staff/order-items/<int:pk>/', StaffOrderItemAdvanceView.as_view()),
]
