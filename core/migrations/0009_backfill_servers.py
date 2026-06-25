from django.db import migrations


def backfill_servers(apps, schema_editor):
    """Create Server rows from existing free-text server_name values and link
    tables + orders to them. All new FKs are nullable, so this is non-destructive.

    Passcodes are auto-assigned (1001, 1002, ...) for these legacy serveurs;
    the owner can edit them in Django admin afterward.
    """
    Server = apps.get_model('core', 'Server')
    Table = apps.get_model('core', 'Table')
    Order = apps.get_model('core', 'Order')

    table_names = Table.objects.exclude(server_name='').values_list('server_name', flat=True)
    order_names = Order.objects.exclude(server_name='').values_list('server_name', flat=True)
    all_names = sorted(set(table_names) | set(order_names))

    name_to_server = {}
    code = 1001
    for name in all_names:
        server = Server.objects.create(name=name, passcode=str(code), is_active=True)
        name_to_server[name] = server
        code += 1

    for table in Table.objects.exclude(server_name=''):
        server = name_to_server.get(table.server_name)
        if server is not None:
            table.server = server
            table.save(update_fields=['server'])

    for order in Order.objects.exclude(server_name=''):
        server = name_to_server.get(order.server_name)
        if server is not None:
            order.server = server
            order.save(update_fields=['server'])


def unlink_servers(apps, schema_editor):
    """Reverse: unlink FKs and remove the auto-created Server rows.
    server_name snapshots are left intact, so no history is lost."""
    Server = apps.get_model('core', 'Server')
    Table = apps.get_model('core', 'Table')
    Order = apps.get_model('core', 'Order')

    Table.objects.update(server=None)
    Order.objects.update(server=None)
    Server.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0008_server_alter_table_server_name_order_server_and_more'),
    ]

    operations = [
        migrations.RunPython(backfill_servers, unlink_servers),
    ]
