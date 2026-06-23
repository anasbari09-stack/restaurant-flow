from django.db import transaction
from django.db.models import Case, Count, F, When, Value, IntegerField
from rest_framework.authentication import SessionAuthentication
from rest_framework.views import APIView
from rest_framework.response import Response

from core.models import Table, MenuItem, Order, OrderItem, StaffPasscode, Customer
from .serializers import (
    MenuItemSerializer, OrderCreateSerializer, OrderDetailSerializer,
    OrderItemStationSerializer,
)

STATION_TO_CATEGORY = {'kitchen': 'food', 'drinks': 'drink', 'dessert': 'dessert'}
NEXT_STATUS = {'NEW': 'PREPARING', 'PREPARING': 'READY', 'READY': 'SERVED'}


class EnforceCsrfAuthentication(SessionAuthentication):
    """Runs Django's CSRF check for unauthenticated requests.

    DRF wraps APIViews with csrf_exempt, bypassing the middleware check.
    This authenticator re-applies it so anonymous POSTs still require a
    valid CSRF token — without forcing users to log in.
    """
    def authenticate(self, request):
        self.enforce_csrf(request)
        return None


class MenuView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        token = request.query_params.get('table', '').strip()
        if not token:
            return Response({'error': 'table parameter is required.'}, status=400)

        try:
            table = Table.objects.select_related('restaurant').get(qr_token=token)
        except (Table.DoesNotExist, ValueError):
            return Response({'error': 'Invalid table token.'}, status=404)

        items = MenuItem.objects.filter(
            restaurant=table.restaurant, is_available=True
        ).order_by('category', 'name')

        grouped = {}
        for item in items:
            grouped.setdefault(item.category, []).append(MenuItemSerializer(item).data)

        return Response({
            'table': {'id': table.id, 'number': table.number},
            'restaurant': {'name': table.restaurant.name},
            'menu': grouped,
        })


class OrderCreateView(APIView):
    authentication_classes = [EnforceCsrfAuthentication]
    permission_classes = []

    def get(self, request):
        token = request.query_params.get('table', '').strip()
        if not token:
            return Response({'error': 'table parameter is required.'}, status=400)
        try:
            table = Table.objects.get(qr_token=token)
        except (Table.DoesNotExist, ValueError):
            return Response({'error': 'Invalid table token.'}, status=404)

        orders = (
            Order.objects
            .filter(table=table)
            .prefetch_related('items')
            .annotate(item_count=Count('items'))
            .order_by('-created_at')
        )
        active = [
            {
                'id': o.id,
                'status': o.status,
                'created_at': o.created_at,
                'item_count': o.item_count,
            }
            for o in orders
            if o.status != 'SERVED'
        ]
        return Response(active)

    def post(self, request):
        serializer = OrderCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)
        order = serializer.save()
        return Response({'order_id': order.id, 'status': order.status}, status=201)


class OrderDetailView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request, pk):
        try:
            order = (Order.objects
                     .select_related('table__restaurant')
                     .prefetch_related('items__menu_item')
                     .get(pk=pk))
        except Order.DoesNotExist:
            return Response({'error': 'Order not found.'}, status=404)
        return Response(OrderDetailSerializer(order).data)


class StaffLoginView(APIView):
    authentication_classes = [EnforceCsrfAuthentication]
    permission_classes = []

    def post(self, request):
        passcode = str(request.data.get('passcode', '')).strip()
        if not passcode:
            return Response({'error': 'Passcode is required.'}, status=400)
        try:
            staff = StaffPasscode.objects.get(passcode=passcode)
        except StaffPasscode.DoesNotExist:
            return Response({'error': 'Incorrect passcode.'}, status=401)
        request.session['staff_role'] = staff.role
        return Response({'role': staff.role})


class StaffLogoutView(APIView):
    authentication_classes = [EnforceCsrfAuthentication]
    permission_classes = []

    def post(self, request):
        request.session.pop('staff_role', None)
        return Response({'ok': True})


class StaffOrderItemsView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        if not request.session.get('staff_role'):
            return Response({'error': 'Login required.'}, status=401)
        station = request.query_params.get('station', '').strip()
        if station not in STATION_TO_CATEGORY:
            return Response({'error': f'station must be one of {list(STATION_TO_CATEGORY)}.'}, status=400)
        items = (
            OrderItem.objects
            .filter(
                menu_item__category=STATION_TO_CATEGORY[station],
                status__in=['NEW', 'PREPARING', 'READY'],
            )
            .select_related('menu_item', 'order__table')
            .annotate(
                sort_priority=Case(
                    When(status__in=['NEW', 'PREPARING'], then=Value(0)),
                    When(status='READY', then=Value(1)),
                    output_field=IntegerField(),
                )
            )
            .order_by('sort_priority', 'order__created_at')
        )
        return Response(OrderItemStationSerializer(items, many=True).data)


class StaffOrderItemAdvanceView(APIView):
    authentication_classes = [EnforceCsrfAuthentication]
    permission_classes = []

    def patch(self, request, pk):
        if not request.session.get('staff_role'):
            return Response({'error': 'Login required.'}, status=401)
        try:
            item = OrderItem.objects.get(pk=pk)
        except OrderItem.DoesNotExist:
            return Response({'error': 'Item not found.'}, status=404)
        if item.status == 'SERVED':
            return Response({'error': 'Item is already served.'}, status=400)
        item.status = NEXT_STATUS[item.status]
        item.save()

        # Award loyalty points exactly once when all items in the order are SERVED.
        # select_for_update() locks the Order row so concurrent PATCH calls on the
        # same order's final items block here and see loyalty_awarded=True on retry.
        with transaction.atomic():
            locked = Order.objects.select_for_update().get(pk=item.order_id)
            if not locked.loyalty_awarded and locked.customer_id and locked.status == 'SERVED':
                total  = locked.total_amount
                points = int(total // 10)
                Customer.objects.filter(pk=locked.customer_id).update(
                    loyalty_points=F('loyalty_points') + points,
                    total_spent=F('total_spent') + total,
                )
                locked.loyalty_awarded = True
                locked.save(update_fields=['loyalty_awarded'])

        return Response({'id': item.id, 'status': item.status})
