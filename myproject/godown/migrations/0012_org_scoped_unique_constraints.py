"""
Replace global unique constraints with organization-scoped unique_together constraints.
This allows different organizations to use the same codes/IDs independently.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('godown', '0011_make_organization_required'),
        ('sylvia', '0012_dealer_sylvia_deal_organiz_a99fec_idx_and_more'),
    ]

    operations = [
        # GodownLocation: drop unique on code, add org-scoped unique_together
        migrations.AlterField(
            model_name='godownlocation',
            name='code',
            field=models.CharField(
                max_length=20,
                help_text='Unique code for the godown (unique within organization)',
            ),
        ),
        migrations.AlterUniqueTogether(
            name='godownlocation',
            unique_together={('organization', 'code')},
        ),

        # OrderInTransit: drop unique on eway_bill_number, add org-scoped unique_together
        migrations.AlterField(
            model_name='orderintransit',
            name='eway_bill_number',
            field=models.CharField(
                max_length=15,
                help_text='E-way bill number for the shipment (unique within organization)',
            ),
        ),
        migrations.AlterUniqueTogether(
            name='orderintransit',
            unique_together={('organization', 'eway_bill_number')},
        ),

        # GodownInventory: drop unique on batch_id, add org-scoped unique_together
        migrations.AlterField(
            model_name='godowninventory',
            name='batch_id',
            field=models.CharField(
                max_length=50,
                editable=False,
                help_text='Auto-generated FIFO batch identifier (unique within organization)',
            ),
        ),
        migrations.AlterUniqueTogether(
            name='godowninventory',
            unique_together={('organization', 'batch_id')},
        ),

        # CrossoverRecord: drop unique on crossover_id, add org-scoped unique_together
        migrations.AlterField(
            model_name='crossoverrecord',
            name='crossover_id',
            field=models.CharField(
                max_length=50,
                editable=False,
                help_text='Auto-generated crossover identifier (unique within organization)',
            ),
        ),
        migrations.AlterUniqueTogether(
            name='crossoverrecord',
            unique_together={('organization', 'crossover_id')},
        ),

        # LoadingRequest: drop unique on loading_request_id, add org-scoped unique_together
        migrations.AlterField(
            model_name='loadingrequest',
            name='loading_request_id',
            field=models.CharField(
                max_length=50,
                editable=False,
                help_text='Auto-generated loading request identifier (unique within organization)',
            ),
        ),
        migrations.AlterUniqueTogether(
            name='loadingrequest',
            unique_together={('organization', 'loading_request_id')},
        ),

        # DeliveryChallan: drop unique on challan_number, add org-scoped unique_together
        migrations.AlterField(
            model_name='deliverychallan',
            name='challan_number',
            field=models.CharField(
                max_length=50,
                editable=False,
                help_text='Auto-generated delivery challan number (unique within organization)',
            ),
        ),
        migrations.AlterUniqueTogether(
            name='deliverychallan',
            unique_together={('organization', 'challan_number')},
        ),

        # GodownInventoryLedger: drop unique on transaction_id, add org-scoped unique_together
        migrations.AlterField(
            model_name='godowninventoryledger',
            name='transaction_id',
            field=models.CharField(
                max_length=50,
                editable=False,
                help_text='Auto-generated unique transaction identifier (unique within organization)',
            ),
        ),
        migrations.AlterUniqueTogether(
            name='godowninventoryledger',
            unique_together={('organization', 'transaction_id')},
        ),

        # InventoryVariance: drop unique on variance_id, add org-scoped unique_together
        migrations.AlterField(
            model_name='inventoryvariance',
            name='variance_id',
            field=models.CharField(
                max_length=50,
                editable=False,
                help_text='Auto-generated variance identifier (unique within organization)',
            ),
        ),
        migrations.AlterUniqueTogether(
            name='inventoryvariance',
            unique_together={('organization', 'variance_id')},
        ),

        # Add index on organization + created_at for all models
        migrations.AddIndex(
            model_name='godownlocation',
            index=models.Index(fields=['organization', '-created_at'], name='godown_godo_organiz_crat_idx'),
        ),
        migrations.AddIndex(
            model_name='orderintransit',
            index=models.Index(fields=['organization', '-created_at'], name='godown_orde_organiz_crat_idx'),
        ),
        migrations.AddIndex(
            model_name='godowninventory',
            index=models.Index(fields=['organization', '-created_at'], name='godown_inv_organiz_crat_idx'),
        ),
        migrations.AddIndex(
            model_name='crossoverrecord',
            index=models.Index(fields=['organization', '-created_at'], name='godown_xover_organiz_crat_idx'),
        ),
        migrations.AddIndex(
            model_name='loadingrequest',
            index=models.Index(fields=['organization', '-created_at'], name='godown_lr_organiz_crat_idx'),
        ),
        migrations.AddIndex(
            model_name='loadingrequestimage',
            index=models.Index(fields=['organization', '-created_at'], name='godown_lrimg_organiz_crat_idx'),
        ),
        migrations.AddIndex(
            model_name='deliverychallan',
            index=models.Index(fields=['organization', '-created_at'], name='godown_dc_organiz_crat_idx'),
        ),
        migrations.AddIndex(
            model_name='deliverychallanitem',
            index=models.Index(fields=['organization', '-created_at'], name='godown_dci_organiz_crat_idx'),
        ),
        migrations.AddIndex(
            model_name='challanitembatchmapping',
            index=models.Index(fields=['organization', '-created_at'], name='godown_cibm_organiz_crat_idx'),
        ),
        migrations.AddIndex(
            model_name='notificationlog',
            index=models.Index(fields=['organization', '-created_at'], name='godown_nlog_organiz_crat_idx'),
        ),
        migrations.AddIndex(
            model_name='notificationrecipient',
            index=models.Index(fields=['organization', '-created_at'], name='godown_nrec_organiz_crat_idx'),
        ),
        migrations.AddIndex(
            model_name='godowninventoryledger',
            index=models.Index(fields=['organization', '-created_at'], name='godown_led_organiz_crat_idx'),
        ),
        migrations.AddIndex(
            model_name='ledgerbatchmapping',
            index=models.Index(fields=['organization', '-created_at'], name='godown_lbm_organiz_crat_idx'),
        ),
        migrations.AddIndex(
            model_name='godowndailybalance',
            index=models.Index(fields=['organization', '-created_at'], name='godown_dbal_organiz_crat_idx'),
        ),
        migrations.AddIndex(
            model_name='inventoryvariance',
            index=models.Index(fields=['organization', '-created_at'], name='godown_ivar_organiz_crat_idx'),
        ),
    ]
