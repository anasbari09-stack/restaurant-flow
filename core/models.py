import uuid
from django.db import models


class Restaurant(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name


class Table(models.Model):
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name='tables')
    number = models.PositiveIntegerField()
    qr_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)

    class Meta:
        unique_together = [('restaurant', 'number')]

    def __str__(self):
        return f'{self.restaurant.name} — Table {self.number}'


class MenuItem(models.Model):
    CATEGORY_CHOICES = [
        ('food', 'Food'),
        ('drink', 'Drink'),
        ('dessert', 'Dessert'),
    ]
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name='menu_items')
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=8, decimal_places=2)
    category = models.CharField(max_length=10, choices=CATEGORY_CHOICES)
    is_available = models.BooleanField(default=True)

    class Meta:
        ordering = ['category', 'name']

    def __str__(self):
        return f'{self.name} ({self.get_category_display()})'


class Customer(models.Model):
    phone          = models.CharField(max_length=20, unique=True)
    loyalty_points = models.PositiveIntegerField(default=0)
    total_spent    = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    def __str__(self):
        return self.phone


class Order(models.Model):
    table = models.ForeignKey(Table, on_delete=models.PROTECT, related_name='orders')
    customer = models.ForeignKey(
        Customer, on_delete=models.SET_NULL, null=True, blank=True, related_name='orders'
    )
    created_at      = models.DateTimeField(auto_now_add=True)
    loyalty_awarded = models.BooleanField(default=False)

    @property
    def total_amount(self):
        return sum(i.menu_item.price * i.quantity
                   for i in self.items.select_related('menu_item').all())

    @property
    def status(self):
        statuses = set(self.items.values_list('status', flat=True))
        if not statuses:
            return 'NEW'
        if statuses == {'SERVED'}:
            return 'SERVED'
        if 'READY' in statuses:
            return 'READY'
        if 'PREPARING' in statuses:
            return 'PREPARING'
        return 'NEW'

    def __str__(self):
        return f'Order #{self.pk} — {self.table}'


class OrderItem(models.Model):
    STATUS_CHOICES = [
        ('NEW', 'New'),
        ('PREPARING', 'Preparing'),
        ('READY', 'Ready'),
        ('SERVED', 'Served'),
    ]
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    menu_item = models.ForeignKey(MenuItem, on_delete=models.PROTECT, related_name='order_items')
    quantity = models.PositiveIntegerField(default=1)
    notes = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='NEW')

    def __str__(self):
        return f'{self.quantity}× {self.menu_item.name} [{self.status}]'


class StaffPasscode(models.Model):
    ROLE_CHOICES = [
        ('kitchen', 'Kitchen'),
        ('drinks', 'Drinks'),
        ('dessert', 'Dessert'),
        ('admin', 'Admin'),
    ]
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, unique=True)
    passcode = models.CharField(max_length=4, unique=True)

    def __str__(self):
        return f'{self.role} ({self.passcode})'


class Review(models.Model):
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='review')
    rating = models.PositiveSmallIntegerField()
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Review for Order #{self.order_id} — {self.rating}/5'
