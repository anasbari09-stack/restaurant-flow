from django.contrib import admin
from .models import Restaurant, Server, Table, MenuItem, Customer, Order, OrderItem, Review, StaffPasscode, HelpAlert


@admin.register(Restaurant)
class RestaurantAdmin(admin.ModelAdmin):
    list_display = ['name', 'description']


@admin.register(Server)
class ServerAdmin(admin.ModelAdmin):
    list_display = ['name', 'passcode', 'is_active']
    list_filter = ['is_active']
    list_editable = ['passcode', 'is_active']
    search_fields = ['name']


@admin.register(Table)
class TableAdmin(admin.ModelAdmin):
    list_display = ['restaurant', 'number', 'server', 'server_name', 'qr_token']
    list_filter = ['restaurant', 'server']
    list_editable = ['server']
    readonly_fields = ['qr_token']


@admin.register(MenuItem)
class MenuItemAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'price', 'is_available', 'is_featured', 'restaurant']
    list_filter = ['category', 'is_available', 'is_featured', 'restaurant']
    list_editable = ['price', 'is_available', 'is_featured']
    search_fields = ['name']


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ['phone', 'loyalty_points', 'total_spent']
    search_fields = ['phone']


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display    = ['id', 'table', 'server', 'server_name', 'customer', 'created_at', 'loyalty_awarded']
    list_filter     = ['table__restaurant', 'server']
    readonly_fields = ['created_at', 'loyalty_awarded']


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ['order', 'menu_item', 'quantity', 'status', 'notes']
    list_filter = ['status', 'menu_item__category']
    list_editable = ['status']


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display    = ['order', 'food_rating', 'service_rating', 'overall_rating',
                       'problem_item', 'short_comment', 'created_at']
    list_filter     = ['problem_item']
    readonly_fields = ['created_at']

    def short_comment(self, obj):
        return obj.comment[:60] + '…' if len(obj.comment) > 60 else obj.comment
    short_comment.short_description = 'Comment'


@admin.register(HelpAlert)
class HelpAlertAdmin(admin.ModelAdmin):
    list_display    = ['id', 'order', 'table', 'created_at', 'resolved']
    list_filter     = ['resolved']
    list_editable   = ['resolved']
    readonly_fields = ['created_at']


@admin.register(StaffPasscode)
class StaffPasscodeAdmin(admin.ModelAdmin):
    list_display = ['role', 'passcode']
