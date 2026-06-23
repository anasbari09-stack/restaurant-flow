from django.contrib import admin
from .models import Restaurant, Table, MenuItem, Customer, Order, OrderItem, Review, StaffPasscode


@admin.register(Restaurant)
class RestaurantAdmin(admin.ModelAdmin):
    list_display = ['name', 'description']


@admin.register(Table)
class TableAdmin(admin.ModelAdmin):
    list_display = ['restaurant', 'number', 'qr_token']
    list_filter = ['restaurant']
    readonly_fields = ['qr_token']


@admin.register(MenuItem)
class MenuItemAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'price', 'is_available', 'restaurant']
    list_filter = ['category', 'is_available', 'restaurant']
    list_editable = ['price', 'is_available']
    search_fields = ['name']


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ['phone', 'loyalty_points', 'total_spent']
    search_fields = ['phone']


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display    = ['id', 'table', 'customer', 'created_at', 'loyalty_awarded']
    list_filter     = ['table__restaurant']
    readonly_fields = ['created_at', 'loyalty_awarded']


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ['order', 'menu_item', 'quantity', 'status', 'notes']
    list_filter = ['status', 'menu_item__category']
    list_editable = ['status']


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ['order', 'rating', 'created_at']
    readonly_fields = ['created_at']


@admin.register(StaffPasscode)
class StaffPasscodeAdmin(admin.ModelAdmin):
    list_display = ['role', 'passcode']
