from rest_framework.authentication import SessionAuthentication
from rest_framework.views import APIView
from rest_framework.response import Response

from core.models import Table, MenuItem
from .serializers import MenuItemSerializer, OrderCreateSerializer


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

    def post(self, request):
        serializer = OrderCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)
        order = serializer.save()
        return Response({'order_id': order.id, 'status': order.status}, status=201)
