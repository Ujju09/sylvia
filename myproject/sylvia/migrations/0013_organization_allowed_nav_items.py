from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sylvia', '0012_dealer_sylvia_deal_organiz_a99fec_idx_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='organization',
            name='allowed_nav_items',
            field=models.JSONField(
                blank=True,
                default=list,
                help_text=(
                    'List of sidebar nav items this organisation can access. '
                    'Empty list means all items are visible. '
                    'Valid values: home, intelligence, partnerships, insights, '
                    'begin_journey, fleet_drivers, partners, warehouse'
                ),
            ),
        ),
    ]
