import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('godown', '0008_loadingrequestimage'),
        ('sylvia', '0012_dealer_sylvia_deal_organiz_a99fec_idx_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='godownlocation',
            name='organization',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.PROTECT,
                to='sylvia.organization',
                help_text='Organization this record belongs to',
            ),
        ),
        migrations.AddField(
            model_name='orderintransit',
            name='organization',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.PROTECT,
                to='sylvia.organization',
                help_text='Organization this record belongs to',
            ),
        ),
        migrations.AddField(
            model_name='godowninventory',
            name='organization',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.PROTECT,
                to='sylvia.organization',
                help_text='Organization this record belongs to',
            ),
        ),
        migrations.AddField(
            model_name='crossoverrecord',
            name='organization',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.PROTECT,
                to='sylvia.organization',
                help_text='Organization this record belongs to',
            ),
        ),
        migrations.AddField(
            model_name='loadingrequest',
            name='organization',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.PROTECT,
                to='sylvia.organization',
                help_text='Organization this record belongs to',
            ),
        ),
        migrations.AddField(
            model_name='loadingrequestimage',
            name='organization',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.PROTECT,
                to='sylvia.organization',
                help_text='Organization this record belongs to',
            ),
        ),
        migrations.AddField(
            model_name='deliverychallan',
            name='organization',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.PROTECT,
                to='sylvia.organization',
                help_text='Organization this record belongs to',
            ),
        ),
        migrations.AddField(
            model_name='deliverychallanitem',
            name='organization',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.PROTECT,
                to='sylvia.organization',
                help_text='Organization this record belongs to',
            ),
        ),
        migrations.AddField(
            model_name='challanitembatchmapping',
            name='organization',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.PROTECT,
                to='sylvia.organization',
                help_text='Organization this record belongs to',
            ),
        ),
        migrations.AddField(
            model_name='notificationlog',
            name='organization',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.PROTECT,
                to='sylvia.organization',
                help_text='Organization this record belongs to',
            ),
        ),
        migrations.AddField(
            model_name='notificationrecipient',
            name='organization',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.PROTECT,
                to='sylvia.organization',
                help_text='Organization this record belongs to',
            ),
        ),
        migrations.AddField(
            model_name='godowninventoryledger',
            name='organization',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.PROTECT,
                to='sylvia.organization',
                help_text='Organization this record belongs to',
            ),
        ),
        migrations.AddField(
            model_name='ledgerbatchmapping',
            name='organization',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.PROTECT,
                to='sylvia.organization',
                help_text='Organization this record belongs to',
            ),
        ),
        migrations.AddField(
            model_name='godowndailybalance',
            name='organization',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.PROTECT,
                to='sylvia.organization',
                help_text='Organization this record belongs to',
            ),
        ),
        migrations.AddField(
            model_name='inventoryvariance',
            name='organization',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.PROTECT,
                to='sylvia.organization',
                help_text='Organization this record belongs to',
            ),
        ),
    ]
