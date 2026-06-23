from django.urls import path
from .views import MenuView, OrderCreateView

urlpatterns = [
    path('menu/', MenuView.as_view()),
    path('orders/', OrderCreateView.as_view()),
]
