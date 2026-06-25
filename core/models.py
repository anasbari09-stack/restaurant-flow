import uuid
from django.db import models


class Restaurant(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name


class Server(models.Model):
    """A waiter/serveur with a simple passcode login.

    Kept intentionally lightweight (no password hashing) — same trust level as
    StaffPasscode, suitable for a single-restaurant MVP on a staff device.
    """
    name = models.CharField(max_length=100)
    passcode = models.CharField(max_length=4, unique=True)
    is_active = models.BooleanField(
        default=True,
        help_text="Deactivate instead of deleting so order history stays attributed.",
    )

    def __str__(self):
        return self.name


class Table(models.Model):
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name='tables')
    number = models.PositiveIntegerField()
    qr_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    server = models.ForeignKey(
        Server, on_delete=models.SET_NULL, null=True, blank=True, related_name='tables',
        help_text="Serveur currently assigned to this table.",
    )
    server_name = models.CharField(
        max_length=100, blank=True,
        help_text="Display snapshot of the assigned serveur's name; kept in sync with server.",
    )

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
    is_featured = models.BooleanField(
        default=False,
        help_text="Show this item in the Today's Picks / special offers carousel.",
    )
    image_url = models.URLField(blank=True)

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
    # server (FK) is the stable serveur identity for analytics — survives renames
    # and deactivation (SET_NULL). server_name is the immutable snapshot taken at
    # order-creation time and the display fallback when the FK is null (legacy or
    # customer self-orders), so reassigning a table never re-attributes history.
    server          = models.ForeignKey(
        Server, on_delete=models.SET_NULL, null=True, blank=True, related_name='orders',
    )
    server_name     = models.CharField(max_length=100, blank=True)

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


class HelpAlert(models.Model):
    KIND_CHOICES = [
        ('call', 'Call serveur / help'),
        ('cancel', 'Cancellation request'),
    ]
    # A help alert can be raised against an order (from the tracking page) or
    # against just a table (from the Table Hub, before any order exists). At
    # least one of order/table is set; the view derives the table from whichever.
    order      = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='help_alerts',
                                   null=True, blank=True)
    table      = models.ForeignKey(Table, on_delete=models.CASCADE, related_name='help_alerts',
                                   null=True, blank=True)
    kind       = models.CharField(max_length=10, choices=KIND_CHOICES, default='call')
    created_at = models.DateTimeField(auto_now_add=True)
    resolved   = models.BooleanField(default=False)

    @property
    def resolved_table(self):
        """The table this alert belongs to, whether raised via order or table."""
        if self.table_id:
            return self.table
        if self.order_id:
            return self.order.table
        return None

    def __str__(self):
        return f'HelpAlert #{self.pk} (resolved={self.resolved})'


class Review(models.Model):
    order          = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='review')
    food_rating    = models.PositiveSmallIntegerField(default=3)
    service_rating = models.PositiveSmallIntegerField(default=3)
    overall_rating = models.PositiveSmallIntegerField(default=3)
    problem_item   = models.ForeignKey(
        OrderItem, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='problem_reviews',
    )
    comment        = models.TextField(blank=True)
    created_at     = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Review for Order #{self.order_id} — {self.overall_rating}/5'
