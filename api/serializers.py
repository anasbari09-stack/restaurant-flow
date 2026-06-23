from rest_framework import serializers
from core.models import Table, MenuItem, Customer, Order, OrderItem


class MenuItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = MenuItem
        fields = ['id', 'name', 'description', 'price', 'category']


class OrderItemDetailSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source='menu_item.name')

    class Meta:
        model = OrderItem
        fields = ['id', 'name', 'quantity', 'notes', 'status']


class OrderDetailSerializer(serializers.ModelSerializer):
    items = OrderItemDetailSerializer(many=True)
    table_number = serializers.IntegerField(source='table.number')
    restaurant_name = serializers.CharField(source='table.restaurant.name')
    status = serializers.CharField(read_only=True)  # @property on Order

    class Meta:
        model = Order
        fields = ['id', 'status', 'created_at', 'table_number', 'restaurant_name', 'items']


class OrderItemInputSerializer(serializers.Serializer):
    menu_item_id = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1, default=1)
    notes = serializers.CharField(required=False, allow_blank=True, default='')


class OrderCreateSerializer(serializers.Serializer):
    table = serializers.UUIDField()
    phone = serializers.CharField(required=False, allow_blank=True, default='')
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

    def create(self, validated_data):
        table = validated_data['table']
        phone = validated_data.get('phone', '').strip()
        items_data = validated_data['items']

        customer = None
        if phone:
            customer, _ = Customer.objects.get_or_create(phone=phone)

        order = Order.objects.create(table=table, customer=customer)

        menu_items = {
            item.id: item
            for item in MenuItem.objects.filter(
                id__in=[d['menu_item_id'] for d in items_data]
            )
        }
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
