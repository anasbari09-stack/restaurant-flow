from django.db import transaction
from django.utils import timezone
from rest_framework import serializers
from core.models import Server, Table, MenuItem, Customer, Order, OrderItem, Review

DELAY_THRESHOLD_MINUTES = 15


class MenuItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = MenuItem
        fields = ['id', 'name', 'description', 'price', 'category', 'image_url', 'is_featured']


class MenuItemAdminSerializer(serializers.ModelSerializer):
    """Owner-facing menu editing. Separate from the public serializer so the
    customer payload never changes, and so admins can see/set is_available."""
    class Meta:
        model = MenuItem
        fields = ['id', 'name', 'description', 'price', 'category',
                  'is_available', 'is_featured', 'image_url']

    def validate_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError('Name is required.')
        return value

    def validate_price(self, value):
        if value < 0:
            raise serializers.ValidationError('Price must be zero or greater.')
        return value


class ServerAdminSerializer(serializers.ModelSerializer):
    """Owner-facing serveur management. Passcode must be 4 digits and unique
    (the model's unique constraint is enforced by DRF automatically)."""
    class Meta:
        model = Server
        fields = ['id', 'name', 'passcode', 'is_active']

    def validate_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError('Name is required.')
        return value

    def validate_passcode(self, value):
        value = value.strip()
        if not (value.isdigit() and len(value) == 4):
            raise serializers.ValidationError('Passcode must be exactly 4 digits.')
        return value


class TableAdminSerializer(serializers.ModelSerializer):
    """Owner-facing table management. qr_token is read-only (rotation is a
    future, guarded feature). order_count drives the delete guard in the UI.

    Assignment is by the Server FK (the canonical, analytics-stable identity);
    server_name is a read-only display snapshot the view keeps in sync."""
    qr_token    = serializers.UUIDField(read_only=True)
    order_count = serializers.IntegerField(read_only=True)
    server      = serializers.PrimaryKeyRelatedField(
        queryset=Server.objects.all(), allow_null=True, required=False)
    server_name = serializers.CharField(read_only=True)

    class Meta:
        model = Table
        fields = ['id', 'number', 'server', 'server_name', 'qr_token', 'order_count']

    def validate_number(self, value):
        if value < 1:
            raise serializers.ValidationError('Table number must be 1 or greater.')
        return value


class OrderItemStationSerializer(serializers.ModelSerializer):
    name                  = serializers.CharField(source='menu_item.name')
    table_number          = serializers.IntegerField(source='order.table.number')
    order_id              = serializers.IntegerField(source='order.id')
    order_waiting_minutes = serializers.SerializerMethodField()
    is_delayed            = serializers.SerializerMethodField()

    class Meta:
        model  = OrderItem
        fields = ['id', 'name', 'quantity', 'notes', 'status',
                  'table_number', 'order_id', 'order_waiting_minutes', 'is_delayed']

    def get_order_waiting_minutes(self, obj):
        delta = timezone.now() - obj.order.created_at
        return int(delta.total_seconds() // 60)

    def get_is_delayed(self, obj):
        if obj.status not in ('NEW', 'PREPARING'):
            return False
        delta = timezone.now() - obj.order.created_at
        return (delta.total_seconds() / 60) > DELAY_THRESHOLD_MINUTES


class OrderItemDetailSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source='menu_item.name')

    class Meta:
        model = OrderItem
        fields = ['id', 'name', 'quantity', 'notes', 'status']


class OrderDetailSerializer(serializers.ModelSerializer):
    items           = OrderItemDetailSerializer(many=True)
    table_number    = serializers.IntegerField(source='table.number')
    table_token     = serializers.UUIDField(source='table.qr_token')
    restaurant_name = serializers.CharField(source='table.restaurant.name')
    status          = serializers.CharField(read_only=True)
    has_review      = serializers.SerializerMethodField()
    cancel_state    = serializers.SerializerMethodField()

    class Meta:
        model  = Order
        fields = ['id', 'status', 'created_at', 'table_number', 'table_token',
                  'restaurant_name', 'items', 'has_review', 'cancel_state']

    def get_has_review(self, obj):
        try:
            obj.review
            return True
        except Exception:
            return False

    def get_cancel_state(self, obj):
        """Durable cancellation state for the tracking UI:
        canceled (order canceled) / pending (open cancel request) /
        declined (cancel request was resolved without canceling) / none."""
        if obj.status == 'CANCELED':
            return 'canceled'
        cancel_alerts = [a for a in obj.help_alerts.all() if a.kind == 'cancel']
        if any(not a.resolved for a in cancel_alerts):
            return 'pending'
        if cancel_alerts:
            return 'declined'
        return 'none'


class OrderItemInputSerializer(serializers.Serializer):
    menu_item_id = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1, default=1)
    notes = serializers.CharField(required=False, allow_blank=True, default='')


class OrderCreateSerializer(serializers.Serializer):
    table = serializers.UUIDField()
    phone = serializers.CharField(required=False, allow_blank=True, default='')
    # Optional "append to existing order" target ("Order more items" flow).
    order_id = serializers.IntegerField(required=False, allow_null=True, default=None)
    items = OrderItemInputSerializer(many=True)

    def validate_table(self, value):
        try:
            return Table.objects.select_related('restaurant').get(qr_token=value)
        except Table.DoesNotExist:
            raise serializers.ValidationError('Invalid table token.')

    def validate_items(self, value):
        if not value:
            raise serializers.ValidationError('At least one item is required.')
        ids = [item['menu_item_id'] for item in value]
        available_ids = set(
            MenuItem.objects.filter(id__in=ids, is_available=True).values_list('id', flat=True)
        )
        missing = set(ids) - available_ids
        if missing:
            raise serializers.ValidationError(
                f'Item IDs not found or unavailable: {sorted(missing)}'
            )
        return value

    def validate(self, data):
        # Resolve the append target. It only counts as appendable if the order
        # exists, belongs to the same table, and is not yet fully SERVED.
        # Otherwise we silently fall back to creating a new order (rule: never
        # lose the customer's items, never append to a served order).
        data['append_order'] = None
        order_id = data.get('order_id')
        if order_id is not None:
            order = (Order.objects
                     .filter(pk=order_id, table=data['table'])
                     .prefetch_related('items')
                     .first())
            if order is not None and order.status != 'SERVED':
                data['append_order'] = order
        return data

    def create(self, validated_data):
        table = validated_data['table']
        phone = validated_data.get('phone', '').strip()
        items_data = validated_data['items']
        append_order = validated_data.get('append_order')

        menu_items = {
            item.id: item
            for item in MenuItem.objects.filter(
                id__in=[d['menu_item_id'] for d in items_data]
            )
        }

        with transaction.atomic():
            if append_order is not None:
                order = append_order
            else:
                customer = None
                if phone:
                    customer, _ = Customer.objects.get_or_create(phone=phone)
                # Attribute the order to a serveur. Assisted orders (placed by a
                # logged-in serveur) pass acting_server via context; customer
                # self-orders fall back to the table's assigned server. The FK is
                # the stable identity; server_name is the immutable snapshot so
                # later reassignment never re-attributes historical orders.
                acting_server = self.context.get('acting_server')
                server = acting_server or table.server
                order = Order.objects.create(
                    table=table, customer=customer,
                    server=server,
                    server_name=server.name if server else table.server_name,
                )

            OrderItem.objects.bulk_create([
                OrderItem(
                    order=order,
                    menu_item=menu_items[d['menu_item_id']],
                    quantity=d['quantity'],
                    notes=d.get('notes', ''),
                )
                for d in items_data
            ])

        return order


class ReviewCreateSerializer(serializers.Serializer):
    order_id        = serializers.IntegerField()
    food_rating     = serializers.IntegerField(min_value=1, max_value=5)
    service_rating  = serializers.IntegerField(min_value=1, max_value=5)
    overall_rating  = serializers.IntegerField(min_value=1, max_value=5)
    problem_item_id = serializers.IntegerField(required=False, allow_null=True, default=None)
    comment         = serializers.CharField(required=False, allow_blank=True, default='')

    def validate(self, data):
        try:
            order = Order.objects.prefetch_related('items').get(pk=data['order_id'])
        except Order.DoesNotExist:
            raise serializers.ValidationError({'order_id': 'Order not found.'})
        if order.status != 'SERVED':
            raise serializers.ValidationError(
                {'order_id': 'Order must be fully served before reviewing.'})
        try:
            order.review
            raise serializers.ValidationError(
                {'order_id': 'A review already exists for this order.'})
        except Review.DoesNotExist:
            pass
        data['order'] = order

        problem_item_id = data.get('problem_item_id')
        if problem_item_id is not None:
            try:
                problem_item = OrderItem.objects.get(pk=problem_item_id, order=order)
            except OrderItem.DoesNotExist:
                raise serializers.ValidationError({
                    'problem_item_id': (
                        'That item does not belong to this order, or does not exist.'
                    )
                })
            data['problem_item'] = problem_item
        else:
            data['problem_item'] = None

        return data

    def create(self, validated_data):
        return Review.objects.create(
            order=validated_data['order'],
            food_rating=validated_data['food_rating'],
            service_rating=validated_data['service_rating'],
            overall_rating=validated_data['overall_rating'],
            problem_item=validated_data['problem_item'],
            comment=validated_data.get('comment', ''),
        )
