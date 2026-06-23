from django.urls import path
from .views import MenuView, OrderCreateView, OrderDetailView

urlpatterns = [
    path('menu/', MenuView.as_view()),
    path('orders/', OrderCreateView.as_view()),
    path('orders/<int:pk>/', OrderDetailView.as_view()),
]
