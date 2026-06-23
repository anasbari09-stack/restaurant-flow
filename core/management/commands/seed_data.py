from django.core.management.base import BaseCommand
from core.models import Restaurant, Table, MenuItem


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

        for number in range(1, 6):
            Table.objects.get_or_create(restaurant=restaurant, number=number)
        self.stdout.write('Tables 1–5 ready')

        items = [
            ('Margherita Pizza', 'food', '12.99', 'Classic tomato sauce and mozzarella'),
            ('Beef Burger', 'food', '11.50', 'Juicy beef patty with fresh veggies'),
            ('Caesar Salad', 'food', '8.99', 'Romaine, croutons, parmesan'),
            ('Grilled Salmon', 'food', '18.00', 'With lemon butter sauce and greens'),
            ('Lemonade', 'drink', '3.50', 'Freshly squeezed'),
            ('Iced Coffee', 'drink', '4.00', 'Cold brew over ice'),
            ('Orange Juice', 'drink', '3.00', 'Freshly squeezed'),
            ('Mineral Water', 'drink', '2.00', 'Still or sparkling'),
            ('Chocolate Lava Cake', 'dessert', '6.50', 'Warm cake with molten center'),
            ('Vanilla Ice Cream', 'dessert', '4.50', 'Three scoops with toppings'),
            ('Tiramisu', 'dessert', '5.99', 'Classic Italian dessert'),
        ]

        for name, category, price, description in items:
            MenuItem.objects.get_or_create(
                restaurant=restaurant,
                name=name,
                defaults={'category': category, 'price': price, 'description': description},
            )

        self.stdout.write(self.style.SUCCESS('\nSeed complete. Table QR tokens:'))
        for table in Table.objects.filter(restaurant=restaurant).order_by('number'):
            self.stdout.write(f'  Table {table.number}: {table.qr_token}')
        self.stdout.write('\nOpen: http://127.0.0.1:8000/menu/?table=<token>')
