from decimal import Decimal

from django.db import transaction
from django.middleware.csrf import get_token
from django.shortcuts import render
from django.views import View
from django.db.models import Avg, Case, Count, ExpressionWrapper, F, Q, Sum, When, Value, IntegerField
from django.db.models import DecimalField as DjangoDecimalField
from django.db.models.functions import Coalesce
from django.utils import timezone
from rest_framework.authentication import SessionAuthentication
from rest_framework.views import APIView
from rest_framework.response import Response

from core.models import Restaurant, Server, Table, MenuItem, Order, OrderItem, StaffPasscode, Customer, HelpAlert, Review
from .serializers import (
    MenuItemSerializer, MenuItemAdminSerializer, TableAdminSerializer,
    OrderCreateSerializer, OrderDetailSerializer,
    OrderItemStationSerializer, ReviewCreateSerializer,
)

STATION_TO_CATEGORY = {'kitchen': 'food', 'drinks': 'drink', 'dessert': 'dessert'}
NEXT_STATUS = {'NEW': 'PREPARING', 'PREPARING': 'READY', 'READY': 'SERVED'}


def get_current_server(request):
    """Return the logged-in, still-active Server for this session, or None."""
    server_id = request.session.get('server_id')
    if not server_id:
        return None
    return Server.objects.filter(pk=server_id, is_active=True).first()


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

        # Featured items power the "special offers" carousel and are excluded
        # from the category grid below so they never appear twice on the page.
        grouped = {}
        featured = []
        for item in items:
            data = MenuItemSerializer(item).data
            if item.is_featured:
                featured.append(data)
            else:
                grouped.setdefault(item.category, []).append(data)

        return Response({
            'table': {'id': table.id, 'number': table.number},
            'restaurant': {'name': table.restaurant.name},
            'featured': featured,
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
        # An order with no items is not a real active order — its computed
        # status defaults to 'NEW', so without this guard empty orders would
        # linger forever in the "active orders" list. Exclude them, and the
        # SERVED orders that are already complete.
        active = [
            {
                'id': o.id,
                'status': o.status,
                'created_at': o.created_at,
                'item_count': o.item_count,
            }
            for o in orders
            if o.item_count > 0 and o.status != 'SERVED'
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
                     .select_related('table__restaurant', 'review')
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


class ServerLoginView(APIView):
    """Serveur passcode login. Mirrors StaffLoginView but uses the Server model
    and stores server_id (not staff_role) in the session."""
    authentication_classes = [EnforceCsrfAuthentication]
    permission_classes = []

    def post(self, request):
        passcode = str(request.data.get('passcode', '')).strip()
        if not passcode:
            return Response({'error': 'Passcode is required.'}, status=400)
        try:
            server = Server.objects.get(passcode=passcode, is_active=True)
        except Server.DoesNotExist:
            return Response({'error': 'Incorrect or inactive passcode.'}, status=401)
        request.session['server_id'] = server.id
        return Response({'id': server.id, 'name': server.name})


class ServerLogoutView(APIView):
    authentication_classes = [EnforceCsrfAuthentication]
    permission_classes = []

    def post(self, request):
        request.session.pop('server_id', None)
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


class ReviewCreateView(APIView):
    authentication_classes = [EnforceCsrfAuthentication]
    permission_classes = []

    def post(self, request):
        serializer = ReviewCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)
        review = serializer.save()
        return Response({'id': review.id}, status=201)


class OrderHelpAlertView(APIView):
    authentication_classes = [EnforceCsrfAuthentication]
    permission_classes = []

    def post(self, request, pk):
        try:
            order = Order.objects.get(pk=pk)
        except Order.DoesNotExist:
            return Response({'error': 'Order not found.'}, status=404)
        alert, created = HelpAlert.objects.get_or_create(order=order, resolved=False)
        return Response({'id': alert.id, 'created': created},
                        status=201 if created else 200)


class StaffHelpAlertResolveView(APIView):
    authentication_classes = [EnforceCsrfAuthentication]
    permission_classes = []

    def patch(self, request, pk):
        if not request.session.get('staff_role'):
            return Response({'error': 'Login required.'}, status=401)
        try:
            alert = HelpAlert.objects.get(pk=pk)
        except HelpAlert.DoesNotExist:
            return Response({'error': 'Alert not found.'}, status=404)
        alert.resolved = True
        alert.save(update_fields=['resolved'])
        return Response({'id': alert.id, 'resolved': True})


class AdminStatsView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        if request.session.get('staff_role') != 'admin':
            return Response({'error': 'Admin access required.'}, status=403)

        total_orders = Order.objects.count()

        total_revenue = OrderItem.objects.filter(status='SERVED').aggregate(
            total=Coalesce(
                Sum(ExpressionWrapper(
                    F('quantity') * F('menu_item__price'),
                    output_field=DjangoDecimalField()
                )),
                Decimal('0.00')
            )
        )['total']

        rating_agg = Review.objects.aggregate(
            avg_food=Avg('food_rating'),
            avg_service=Avg('service_rating'),
            avg_overall=Avg('overall_rating'),
        )

        top_items = list(
            MenuItem.objects.annotate(
                total_sold=Coalesce(
                    Sum('order_items__quantity',
                        filter=Q(order_items__status='SERVED')), 0)
            ).filter(total_sold__gt=0).order_by('-total_sold')[:5]
            .values('id', 'name', 'total_sold')
        )

        most_flagged = list(
            MenuItem.objects.annotate(
                flag_count=Count('order_items__problem_reviews')
            ).filter(flag_count__gt=0).order_by('-flag_count')[:5]
            .values('id', 'name', 'flag_count')
        )

        recent_reviews = [
            {
                'order_id': r.order_id,
                'table_number': r.order.table.number,
                'food_rating': r.food_rating,
                'service_rating': r.service_rating,
                'overall_rating': r.overall_rating,
                'comment': r.comment,
                'problem_item_name': r.problem_item.menu_item.name if r.problem_item else None,
                'created_at': r.created_at,
            }
            for r in Review.objects
                .select_related('order__table', 'problem_item__menu_item')
                .order_by('-created_at')[:10]
        ]

        now = timezone.now()
        active_help_alerts = [
            {
                'id': a.id,
                'order_id': a.order_id,
                'table_number': a.order.table.number,
                'minutes_waiting': int((now - a.created_at).total_seconds() // 60),
            }
            for a in HelpAlert.objects.filter(resolved=False)
                               .select_related('order__table')
                               .order_by('created_at')
        ]

        def r1(v):
            return round(v, 1) if v is not None else None

        # Serveur performance: avg service rating grouped by the order's
        # snapshotted server_name (blank = unassigned, excluded).
        server_performance = [
            {
                'server_name':  row['order__server_name'],
                'avg_service':  r1(row['avg_service']),
                'avg_overall':  r1(row['avg_overall']),
                'review_count': row['review_count'],
            }
            for row in (
                Review.objects
                .exclude(order__server_name='')
                .values('order__server_name')
                .annotate(
                    avg_service=Avg('service_rating'),
                    avg_overall=Avg('overall_rating'),
                    review_count=Count('id'),
                )
                .order_by('-avg_service', '-review_count')
            )
        ]

        return Response({
            'total_orders':       total_orders,
            'total_revenue':      str(total_revenue),
            'avg_food_rating':    r1(rating_agg['avg_food']),
            'avg_service_rating': r1(rating_agg['avg_service']),
            'avg_overall_rating': r1(rating_agg['avg_overall']),
            'top_items':          top_items,
            'most_flagged_items': most_flagged,
            'recent_reviews':     recent_reviews,
            'active_help_alerts': active_help_alerts,
            'server_performance': server_performance,
        })


class AdminMenuItemListCreateView(APIView):
    """Admin-only menu management: list all items (incl. unavailable) + create."""
    authentication_classes = [EnforceCsrfAuthentication]
    permission_classes = []

    def get(self, request):
        if request.session.get('staff_role') != 'admin':
            return Response({'error': 'Admin access required.'}, status=403)
        items = MenuItem.objects.all().order_by('category', 'name')
        return Response(MenuItemAdminSerializer(items, many=True).data)

    def post(self, request):
        if request.session.get('staff_role') != 'admin':
            return Response({'error': 'Admin access required.'}, status=403)
        serializer = MenuItemAdminSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)
        restaurant = Restaurant.objects.first()
        if restaurant is None:
            return Response({'error': 'No restaurant configured.'}, status=400)
        item = serializer.save(restaurant=restaurant)
        return Response(MenuItemAdminSerializer(item).data, status=201)


class AdminMenuItemDetailView(APIView):
    """Admin-only update + guarded delete for a single menu item."""
    authentication_classes = [EnforceCsrfAuthentication]
    permission_classes = []

    def patch(self, request, pk):
        if request.session.get('staff_role') != 'admin':
            return Response({'error': 'Admin access required.'}, status=403)
        try:
            item = MenuItem.objects.get(pk=pk)
        except MenuItem.DoesNotExist:
            return Response({'error': 'Item not found.'}, status=404)
        serializer = MenuItemAdminSerializer(item, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)
        serializer.save()
        return Response(serializer.data)

    def delete(self, request, pk):
        if request.session.get('staff_role') != 'admin':
            return Response({'error': 'Admin access required.'}, status=403)
        try:
            item = MenuItem.objects.get(pk=pk)
        except MenuItem.DoesNotExist:
            return Response({'error': 'Item not found.'}, status=404)
        # OrderItem.menu_item is PROTECT — deleting a referenced item would error
        # and would also corrupt sales/stats history. Block it and steer the
        # owner toward marking the item unavailable instead.
        if item.order_items.exists():
            return Response(
                {'error': "This item appears in past orders, so it can't be deleted. "
                          "Turn off its availability instead to hide it from the menu."},
                status=400,
            )
        item.delete()
        return Response(status=204)


class AdminTableListCreateView(APIView):
    """Admin-only table management: list tables (+ order counts) and create."""
    authentication_classes = [EnforceCsrfAuthentication]
    permission_classes = []

    def get(self, request):
        if request.session.get('staff_role') != 'admin':
            return Response({'error': 'Admin access required.'}, status=403)
        tables = (Table.objects
                  .annotate(order_count=Count('orders'))
                  .order_by('number'))
        return Response(TableAdminSerializer(tables, many=True).data)

    def post(self, request):
        if request.session.get('staff_role') != 'admin':
            return Response({'error': 'Admin access required.'}, status=403)
        serializer = TableAdminSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)
        restaurant = Restaurant.objects.first()
        if restaurant is None:
            return Response({'error': 'No restaurant configured.'}, status=400)
        number = serializer.validated_data['number']
        if Table.objects.filter(restaurant=restaurant, number=number).exists():
            return Response({'error': f'Table {number} already exists.'}, status=400)
        table = serializer.save(restaurant=restaurant)
        table.order_count = 0
        return Response(TableAdminSerializer(table).data, status=201)


class AdminTableDetailView(APIView):
    """Admin-only update (server/number) + guarded delete for one table."""
    authentication_classes = [EnforceCsrfAuthentication]
    permission_classes = []

    def patch(self, request, pk):
        if request.session.get('staff_role') != 'admin':
            return Response({'error': 'Admin access required.'}, status=403)
        try:
            table = Table.objects.get(pk=pk)
        except Table.DoesNotExist:
            return Response({'error': 'Table not found.'}, status=404)
        serializer = TableAdminSerializer(table, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)
        # If the number is changing, keep it unique within the restaurant.
        new_number = serializer.validated_data.get('number')
        if new_number is not None and new_number != table.number:
            if Table.objects.filter(restaurant=table.restaurant, number=new_number).exists():
                return Response({'error': f'Table {new_number} already exists.'}, status=400)
        serializer.save()
        table = Table.objects.annotate(order_count=Count('orders')).get(pk=pk)
        return Response(TableAdminSerializer(table).data)

    def delete(self, request, pk):
        if request.session.get('staff_role') != 'admin':
            return Response({'error': 'Admin access required.'}, status=403)
        try:
            table = Table.objects.get(pk=pk)
        except Table.DoesNotExist:
            return Response({'error': 'Table not found.'}, status=404)
        # Order.table is PROTECT — deleting a table with orders would error and
        # lose history. Block it with a clear message.
        if table.orders.exists():
            return Response(
                {'error': "This table has orders, so it can't be deleted."},
                status=400,
            )
        table.delete()
        return Response(status=204)


class MenuPageView(View):
    def get(self, request):
        get_token(request)
        return render(request, 'menu.html')
