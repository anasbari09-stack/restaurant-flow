from django.core.management.base import BaseCommand
from core.models import Restaurant, Table, MenuItem, StaffPasscode, Order


class Command(BaseCommand):
    help = 'Seed database with a sample restaurant, tables, and menu items'

    def handle(self, *args, **options):
        restaurant, created = Restaurant.objects.get_or_create(
            name='La Casa',
            defaults={'description': 'A cozy restaurant with great food and drinks'},
        )
        if created:
            self.stdout.write(f'Created restaurant: {restaurant.name}')
        else:
            self.stdout.write(f'Using existing restaurant: {restaurant.name}')

        # Assign a serveur to each table so the serveur-performance chart has
        # data. Idempotent: only fills a blank server_name, never overwrites.
        servers = {1: 'Sara', 2: 'Youssef', 3: 'Sara', 4: 'Mehdi', 5: 'Youssef'}
        for number in range(1, 6):
            table, _ = Table.objects.get_or_create(restaurant=restaurant, number=number)
            if not table.server_name:
                table.server_name = servers[number]
                table.save(update_fields=['server_name'])
        self.stdout.write('Tables 1–5 ready (serveurs assigned)')

        # Backfill existing orders that predate the snapshot field, so historical
        # reviews light up the serveur chart. Only touches blank snapshots.
        backfilled = 0
        for order in Order.objects.filter(server_name='').select_related('table'):
            if order.table.server_name:
                order.server_name = order.table.server_name
                order.save(update_fields=['server_name'])
                backfilled += 1
        if backfilled:
            self.stdout.write(f'Backfilled server_name on {backfilled} existing orders')

        IMG = 'https://images.unsplash.com/photo-{}?w=800&q=80'
        # (name, category, price, description, image photo-id, is_featured)
        # Image IDs were each downloaded and visually confirmed to match the dish.
        items = [
            ('Margherita Pizza', 'food', '12.99', 'Classic tomato sauce, fresh mozzarella and basil', '1574071318508-1cdbab80d002', True),
            ('Beef Burger', 'food', '11.50', 'Juicy double beef patty, house sauce and fresh veggies', '1568901346375-23c9450c58cd', True),
            ('Caesar Salad', 'food', '8.99', 'Crisp romaine, croutons and shaved parmesan', '1550304943-4f24f54ddde9', False),
            ('Grilled Salmon', 'food', '18.00', 'Seared salmon over greens with lemon butter sauce', '1467003909585-2f8a72700288', True),
            ('Lemonade', 'drink', '3.50', 'Freshly squeezed with mint', '1621263764928-df1444c5e859', False),
            ('Iced Coffee', 'drink', '4.00', 'Cold brew over ice', '1461023058943-07fcbe16d735', False),
            ('Orange Juice', 'drink', '3.00', 'Freshly squeezed', '1600271886742-f049cd451bba', False),
            ('Mineral Water', 'drink', '2.00', 'Still or sparkling', '1523362628745-0c100150b504', False),
            ('Chocolate Lava Cake', 'dessert', '6.50', 'Warm cake with a molten chocolate center and ice cream', '1624353365286-3f8d62daad51', True),
            ('Vanilla Ice Cream', 'dessert', '4.50', 'Creamy scoops with toppings', '1497034825429-c343d7c6a68f', False),
            ('Tiramisu', 'dessert', '5.99', 'Classic Italian coffee-soaked dessert', '1571877227200-a0d98ea607e9', False),
        ]

        for name, category, price, description, photo_id, is_featured in items:
            MenuItem.objects.update_or_create(
                restaurant=restaurant,
                name=name,
                defaults={
                    'category': category,
                    'price': price,
                    'description': description,
                    'image_url': IMG.format(photo_id),
                    'is_featured': is_featured,
                },
            )

        passcodes = [
            ('kitchen', '1111'),
            ('drinks',  '2222'),
            ('dessert', '3333'),
            ('admin',   '4444'),
        ]
        for role, code in passcodes:
            StaffPasscode.objects.get_or_create(role=role, defaults={'passcode': code})
        self.stdout.write('Staff passcodes ready (kitchen=1111, drinks=2222, dessert=3333, admin=4444)')

        self.stdout.write(self.style.SUCCESS('\nSeed complete. Table QR tokens:'))
        for table in Table.objects.filter(restaurant=restaurant).order_by('number'):
            self.stdout.write(f'  Table {table.number}: {table.qr_token}')
        self.stdout.write('\nOpen: http://127.0.0.1:8000/menu/?table=<token>')
        self.stdout.write('Staff login: http://127.0.0.1:8000/staff/login/')
