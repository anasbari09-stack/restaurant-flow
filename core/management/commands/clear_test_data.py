"""
Local demo/test data cleanup.

Deletes orders (and, by cascade, their order items, reviews, and help alerts)
so that tables can be emptied and removed. This NEVER deletes menu items,
tables, restaurants, or staff passcodes, and it does NOT change the production
PROTECT guard on Order.table — it simply removes the orders that the guard
protects against, which is safe to do deliberately from the command line.

Safety model:
  * Dry-run by default: prints what WOULD be deleted and exits without changes.
  * Requires --yes to actually delete.
  * --customers is an extra, explicit opt-in for loyalty/customer rows.

Examples:
  python manage.py clear_test_data                  # dry run, deletes nothing
  python manage.py clear_test_data --yes            # delete ALL orders (+cascade)
  python manage.py clear_test_data --yes --table 1  # only orders at table 1
  python manage.py clear_test_data --yes --customers
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import Order, OrderItem, Review, HelpAlert, Customer


class Command(BaseCommand):
    help = ("Delete local demo/test orders (+ cascaded items/reviews/help alerts). "
            "Keeps menu items and tables. Dry-run unless --yes is passed.")

    def add_arguments(self, parser):
        parser.add_argument('--yes', action='store_true',
                            help='Actually perform the deletion (default is a dry run).')
        parser.add_argument('--customers', action='store_true',
                            help='Also delete Customer (loyalty) records. Off by default.')
        parser.add_argument('--table', type=int, default=None,
                            help='Limit to orders for this table NUMBER (default: all tables).')

    def handle(self, *args, **opts):
        orders = Order.objects.all()
        scope = 'ALL tables'
        if opts['table'] is not None:
            orders = orders.filter(table__number=opts['table'])
            scope = f'table {opts["table"]}'

        order_ids   = list(orders.values_list('id', flat=True))
        n_orders    = len(order_ids)
        n_items     = OrderItem.objects.filter(order_id__in=order_ids).count()
        n_reviews   = Review.objects.filter(order_id__in=order_ids).count()
        n_alerts    = HelpAlert.objects.filter(order_id__in=order_ids).count()
        n_customers = Customer.objects.count()

        self.stdout.write(f'Scope: orders for {scope}')
        self.stdout.write(f'  Orders to delete:        {n_orders}')
        self.stdout.write(f'  Order items (cascade):   {n_items}')
        self.stdout.write(f'  Reviews (cascade):       {n_reviews}')
        self.stdout.write(f'  Help alerts (cascade):   {n_alerts}')
        if opts['customers']:
            self.stdout.write(f'  Customers to delete:     {n_customers} (ALL customers)')
        self.stdout.write('  KEEPING: menu items, tables, restaurants, staff passcodes.')

        if not opts['yes']:
            self.stdout.write(self.style.WARNING(
                '\nDRY RUN — nothing was deleted. Re-run with --yes to apply.'))
            return

        if n_orders == 0 and not (opts['customers'] and n_customers):
            self.stdout.write(self.style.SUCCESS('\nNothing to delete.'))
            return

        with transaction.atomic():
            # Deleting orders cascades to OrderItem, Review, and HelpAlert.
            orders.delete()
            if opts['customers']:
                Customer.objects.all().delete()

        self.stdout.write(self.style.SUCCESS(
            f'\nDeleted {n_orders} order(s) for {scope} '
            f'(+ {n_items} items, {n_reviews} reviews, {n_alerts} help alerts).'))
        if opts['customers']:
            self.stdout.write(self.style.SUCCESS(f'Deleted {n_customers} customer(s).'))
        self.stdout.write('Tables and menu items are intact — you can now delete '
                          'empty tables from Table Management.')
