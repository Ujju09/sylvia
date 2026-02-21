"""
Data migration: assign all existing godown records to the first active organization.

This ensures existing data is associated with an organization before we make
the organization field non-nullable in the next migration.
"""
from django.db import migrations


GODOWN_MODELS = [
    'godownlocation',
    'orderintransit',
    'godowninventory',
    'crossoverrecord',
    'loadingrequest',
    'loadingrequestimage',
    'deliverychallan',
    'deliverychallanitem',
    'challanitembatchmapping',
    'notificationlog',
    'notificationrecipient',
    'godowninventoryledger',
    'ledgerbatchmapping',
    'godowndailybalance',
    'inventoryvariance',
]


def assign_default_organization(apps, schema_editor):
    Organization = apps.get_model('sylvia', 'Organization')
    default_org = Organization.objects.filter(is_active=True).order_by('created_at').first()
    if default_org is None:
        # No organization exists yet — nothing to assign
        return
    for model_name in GODOWN_MODELS:
        Model = apps.get_model('godown', model_name)
        Model.objects.filter(organization__isnull=True).update(organization=default_org)


def reverse_assign_default_organization(apps, schema_editor):
    # Reversing: set all organization fields back to null
    for model_name in GODOWN_MODELS:
        Model = apps.get_model('godown', model_name)
        Model.objects.update(organization=None)


class Migration(migrations.Migration):

    dependencies = [
        ('godown', '0009_add_organization_nullable'),
        ('sylvia', '0012_dealer_sylvia_deal_organiz_a99fec_idx_and_more'),
    ]

    operations = [
        migrations.RunPython(
            assign_default_organization,
            reverse_code=reverse_assign_default_organization,
        ),
    ]
