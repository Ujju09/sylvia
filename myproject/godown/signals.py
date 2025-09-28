"""
Django signals for automatic ledger entry creation.
Ensures every inventory movement is tracked in the GodownInventoryLedger.
"""

import logging
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db import transaction

from .models import (
    OrderInTransit, LoadingRequest, CrossoverRecord, DeliveryChallan,
    GodownInventoryLedger, GodownInventory, LedgerBatchMapping, GodownDailyBalance,
    InventoryVariance
)


User = get_user_model()
logger = logging.getLogger(__name__)


@receiver(post_save, sender=OrderInTransit)
def create_inward_ledger_entry(sender, instance, created, **kwargs):
    """
    Create ledger entry when OrderInTransit arrives and good bags are confirmed.
    Works with both new records created with ARRIVED status and status updates.
    """
    logger.debug(f"OrderInTransit signal fired for {instance.eway_bill_number}: created={created}, status={instance.status}, good_bags={instance.good_bags}")
    
    # Create entry for both new records with ARRIVED status and status updates to ARRIVED
    should_create_entry = (
        instance.status == 'ARRIVED' and 
        instance.good_bags > 0 and
        (created or not created)  # Handle both creation and updates
    )
    
    if should_create_entry:
        # Check if ledger entry already exists to prevent duplicates
        existing_entry = GodownInventoryLedger.objects.filter(
            source_order_transit=instance,
            transaction_type='INWARD_RECEIPT'
        ).first()
        
        logger.debug(f"Checking for existing ledger entry for OrderInTransit {instance.eway_bill_number}: found={bool(existing_entry)}")
        
        if not existing_entry:
            try:
                with transaction.atomic():
                    logger.debug(f"Creating ledger entries for OrderInTransit {instance.eway_bill_number}")
                    
                    # Calculate balance before creating entry
                    previous_balance = _get_previous_balance(instance.godown, instance.product)
                    new_balance = previous_balance + instance.good_bags
                    
                    # Create ledger entry for good bags received
                    ledger_entry = GodownInventoryLedger.objects.create(
                        transaction_type='INWARD_RECEIPT',
                        godown=instance.godown,
                        product=instance.product,
                        inward_quantity=instance.good_bags,
                        outward_quantity=0,
                        balance_after_transaction=new_balance,
                        source_order_transit=instance,
                        condition_at_transaction='GOOD',
                        quality_notes=instance.arrival_notes or '',
                        is_system_generated=True,
                        entry_status='SYSTEM_GENERATED',
                        created_by=instance.created_by,
                        transaction_notes=f'Automatic entry from OrderInTransit arrival: {instance.eway_bill_number}'
                    )
                    
                    logger.info(f"Created GOOD ledger entry for OrderInTransit {instance.eway_bill_number}: {instance.good_bags} bags, balance: {new_balance}")
                    
                    # If there are damaged bags, create a separate entry
                    if instance.damaged_bags > 0:
                        damaged_balance = new_balance + instance.damaged_bags
                        damaged_entry = GodownInventoryLedger.objects.create(
                            transaction_type='INWARD_RECEIPT',
                            godown=instance.godown,
                            product=instance.product,
                            inward_quantity=instance.damaged_bags,
                            outward_quantity=0,
                            balance_after_transaction=damaged_balance,
                            source_order_transit=instance,
                            condition_at_transaction='DAMAGED',
                            quality_notes=f'Damaged bags from transit: {instance.arrival_notes}',
                            is_system_generated=True,
                            entry_status='SYSTEM_GENERATED',
                            created_by=instance.created_by,
                            transaction_notes=f'Damaged bags entry from OrderInTransit: {instance.eway_bill_number}'
                        )
                        
                        logger.info(f"Created DAMAGED ledger entry for OrderInTransit {instance.eway_bill_number}: {instance.damaged_bags} bags, balance: {damaged_balance}")
                        
            except Exception as e:
                logger.error(f"Error creating ledger entries for OrderInTransit {instance.eway_bill_number}: {str(e)}", exc_info=True)
                raise
        else:
            logger.debug(f"Ledger entry already exists for OrderInTransit {instance.eway_bill_number}, skipping creation")
    else:
        logger.debug(f"OrderInTransit signal conditions not met for {instance.eway_bill_number}: status={instance.status}, good_bags={instance.good_bags}")


@receiver(post_save, sender=LoadingRequest)
def create_outward_ledger_entry(sender, instance, created, **kwargs):
    """
    Create ledger entry when LoadingRequest is created or updated with loaded_bags > 0.
    Works with both new records created with loaded_bags and updates with loaded_bags.
    """
    logger.debug(f"LoadingRequest signal fired for {instance.loading_request_id}: created={created}, loaded_bags={instance.loaded_bags}")
    
    # Create entry for both new records with loaded_bags > 0 and updates with loaded_bags > 0
    should_create_entry = (
        instance.loaded_bags > 0 and
        (created or not created)  # Handle both creation and updates
    )
    
    if should_create_entry:
        # Check if ledger entry already exists to prevent duplicates
        existing_entry = GodownInventoryLedger.objects.filter(
            source_loading_request=instance,
            transaction_type='OUTWARD_LOADING'
        ).first()
        
        logger.debug(f"Checking for existing ledger entry for LoadingRequest {instance.loading_request_id}: found={bool(existing_entry)}")
        
        if not existing_entry:
            try:
                with transaction.atomic():
                    logger.debug(f"Creating ledger entry for LoadingRequest {instance.loading_request_id}")
                    
                    # Calculate balance before creating entry
                    previous_balance = _get_previous_balance(instance.godown, instance.product)
                    new_balance = previous_balance - instance.loaded_bags
                    
                    ledger_entry = GodownInventoryLedger.objects.create(
                        transaction_type='OUTWARD_LOADING',
                        godown=instance.godown,
                        product=instance.product,
                        inward_quantity=0,
                        outward_quantity=instance.loaded_bags,
                        balance_after_transaction=new_balance,
                        source_loading_request=instance,
                        condition_at_transaction='GOOD',
                        quality_notes=instance.loading_notes or '',
                        is_system_generated=True,
                        entry_status='SYSTEM_GENERATED',
                        created_by=instance.created_by,
                        authorized_by=instance.supervised_by,
                        transaction_notes=f'Automatic entry from LoadingRequest: {instance.loading_request_id}'
                    )
                    
                    logger.info(f"Created OUTWARD_LOADING ledger entry for LoadingRequest {instance.loading_request_id}: {instance.loaded_bags} bags, balance: {new_balance}")
                    
                    # Note: Batch linking not required for LoadingRequest as per requirements
                    
            except Exception as e:
                logger.error(f"Error creating ledger entry for LoadingRequest {instance.loading_request_id}: {str(e)}", exc_info=True)
                raise
        else:
            logger.debug(f"Ledger entry already exists for LoadingRequest {instance.loading_request_id}, skipping creation")
    else:
        logger.debug(f"LoadingRequest signal conditions not met for {instance.loading_request_id}: loaded_bags={instance.loaded_bags}")


@receiver(post_save, sender=CrossoverRecord)
def create_crossover_ledger_entry(sender, instance, created, **kwargs):
    """
    Create ledger entry when CrossoverRecord is approved.
    Works with both new records created with approved_date and approval updates.
    """
    logger.debug(f"CrossoverRecord signal fired for {instance.crossover_id}: created={created}, actual_transferred_bags={instance.actual_transferred_bags}, approved_date={instance.approved_date}")
    
    # Create entry for both new records with approved_date and approval updates
    should_create_entry = (
        instance.actual_transferred_bags > 0 and 
        instance.approved_date and
        (created or not created)  # Handle both creation and updates
    )
    
    if should_create_entry:
        # Check if ledger entry already exists to prevent duplicates
        existing_entry = GodownInventoryLedger.objects.filter(
            source_crossover=instance,
            transaction_type='OUTWARD_CROSSOVER'
        ).first()
        
        logger.debug(f"Checking for existing ledger entry for CrossoverRecord {instance.crossover_id}: found={bool(existing_entry)}")
        
        if not existing_entry:
            try:
                with transaction.atomic():
                    logger.debug(f"Creating ledger entry for CrossoverRecord {instance.crossover_id}")
                    
                    # Calculate balance before creating entry
                    previous_balance = _get_previous_balance(
                        instance.source_order_transit.godown, 
                        instance.product
                    )
                    new_balance = previous_balance - instance.actual_transferred_bags
                    
                    ledger_entry = GodownInventoryLedger.objects.create(
                        transaction_type='OUTWARD_CROSSOVER',
                        godown=instance.source_order_transit.godown,
                        product=instance.product,
                        inward_quantity=0,
                        outward_quantity=instance.actual_transferred_bags,
                        balance_after_transaction=new_balance,
                        source_crossover=instance,
                        condition_at_transaction='GOOD',
                        quality_notes=instance.crossover_notes or '',
                        is_system_generated=True,
                        entry_status='SYSTEM_GENERATED',
                        created_by=instance.created_by,
                        authorized_by=instance.supervised_by,
                        transaction_notes=f'Automatic entry from CrossoverRecord: {instance.crossover_id}'
                    )
                    
                    logger.info(f"Created OUTWARD_CROSSOVER ledger entry for CrossoverRecord {instance.crossover_id}: {instance.actual_transferred_bags} bags, balance: {new_balance}")
                    
                    # Link to inventory batches (FIFO consumption)
                    _link_outward_transaction_to_batches(ledger_entry, instance.actual_transferred_bags)
                    logger.debug(f"Linked crossover transaction to inventory batches for {instance.crossover_id}")
                    
            except Exception as e:
                logger.error(f"Error creating ledger entry for CrossoverRecord {instance.crossover_id}: {str(e)}", exc_info=True)
                raise
        else:
            logger.debug(f"Ledger entry already exists for CrossoverRecord {instance.crossover_id}, skipping creation")
    else:
        logger.debug(f"CrossoverRecord signal conditions not met for {instance.crossover_id}: actual_transferred_bags={instance.actual_transferred_bags}, approved_date={instance.approved_date}")


@receiver(post_save, sender=GodownInventory)
def create_inventory_ledger_entry(sender, instance, created, **kwargs):
    """
    Create ledger entry when GodownInventory is created.
    This handles direct inventory entries not linked to OrderInTransit.
    """
    logger.debug(f"GodownInventory signal fired for {instance.batch_id}: created={created}, total_bags_received={instance.total_bags_received}")
    
    # Only create entry for new inventory records
    if created and instance.total_bags_received > 0:
        # Check if this inventory is linked to OrderInTransit (handled by OrderInTransit signal)
        if instance.order_in_transit:
            logger.debug(f"GodownInventory {instance.batch_id} is linked to OrderInTransit, skipping signal (handled by OrderInTransit signal)")
            return
        
        # Check if ledger entry already exists to prevent duplicates
        existing_entry = GodownInventoryLedger.objects.filter(
            godown=instance.godown,
            product=instance.product,
            transaction_notes__contains=f'GodownInventory {instance.batch_id}',
            transaction_type='INWARD_RECEIPT'
        ).first()
        
        logger.debug(f"Checking for existing ledger entry for GodownInventory {instance.batch_id}: found={bool(existing_entry)}")
        
        if not existing_entry:
            try:
                with transaction.atomic():
                    logger.debug(f"Creating ledger entry for GodownInventory {instance.batch_id}")
                    
                    # Calculate balance before creating entry
                    previous_balance = _get_previous_balance(instance.godown, instance.product)
                    new_balance = previous_balance + instance.good_bags_available
                    
                    # Create ledger entry for good bags
                    ledger_entry = GodownInventoryLedger.objects.create(
                        transaction_type='INWARD_RECEIPT',
                        godown=instance.godown,
                        product=instance.product,
                        inward_quantity=instance.good_bags_available,
                        outward_quantity=0,
                        balance_after_transaction=new_balance,
                        condition_at_transaction='GOOD',
                        quality_notes=instance.storage_notes or '',
                        is_system_generated=True,
                        entry_status='SYSTEM_GENERATED',
                        created_by=instance.created_by,
                        transaction_notes=f'Automatic entry from GodownInventory creation: {instance.batch_id}'
                    )

                    logger.info(f"Created GOOD ledger entry for GodownInventory {instance.batch_id}: {instance.good_bags_available} bags, balance: {new_balance}")

                    # If there are damaged bags, create a separate entry
                    if instance.damaged_bags > 0:
                        damaged_balance = new_balance + instance.damaged_bags
                        damaged_entry = GodownInventoryLedger.objects.create(
                            transaction_type='INWARD_RECEIPT',
                            godown=instance.godown,
                            product=instance.product,
                            inward_quantity=instance.damaged_bags,
                            outward_quantity=0,
                            balance_after_transaction=damaged_balance,
                            condition_at_transaction='DAMAGED',
                            quality_notes=f'Damaged bags from inventory: {instance.storage_notes}',
                            is_system_generated=True,
                            entry_status='SYSTEM_GENERATED',
                            created_by=instance.created_by,
                            transaction_notes=f'Damaged bags entry from GodownInventory: {instance.batch_id}'
                        )
                        
                        logger.info(f"Created DAMAGED ledger entry for GodownInventory {instance.batch_id}: {instance.damaged_bags} bags, balance: {damaged_balance}")
                        
            except Exception as e:
                logger.error(f"Error creating ledger entry for GodownInventory {instance.batch_id}: {str(e)}", exc_info=True)
                raise
        else:
            logger.debug(f"Ledger entry already exists for GodownInventory {instance.batch_id}, skipping creation")
    else:
        logger.debug(f"GodownInventory signal conditions not met for {instance.batch_id}: created={created}, total_bags_received={instance.total_bags_received}")


@receiver(post_save, sender=DeliveryChallan)
def create_delivery_ledger_entries(sender, instance, created, **kwargs):
    """
    Create ledger entries for delivery challan when status changes to 'DELIVERED'.
    Creates entries for all challan items.
    """
    if not created and instance.status == 'DELIVERED' and instance.total_bags > 0:
        # Check if ledger entries already exist to prevent duplicates
        existing_entries = GodownInventoryLedger.objects.filter(
            source_challan=instance,
            transaction_type='OUTWARD_LOADING'
        )
        
        if not existing_entries.exists():
            with transaction.atomic():
                # Create entries for each challan item
                for challan_item in instance.challan_items.all():
                    # Calculate balance before creating entry
                    previous_balance = _get_previous_balance(instance.godown, challan_item.product)
                    new_balance = previous_balance - challan_item.bags
                    
                    ledger_entry = GodownInventoryLedger.objects.create(
                        transaction_type='OUTWARD_LOADING',
                        godown=instance.godown,
                        product=challan_item.product,
                        inward_quantity=0,
                        outward_quantity=challan_item.bags,
                        balance_after_transaction=new_balance,
                        source_challan=instance,
                        reference_document=instance.challan_number,
                        condition_at_transaction='GOOD',
                        quality_notes=challan_item.quality_notes or '',
                        is_system_generated=True,
                        entry_status='SYSTEM_GENERATED',
                        created_by=instance.created_by,
                        transaction_notes=f'Automatic entry from DeliveryChallan delivery: {instance.challan_number}'
                    )
                    
                    # Link to inventory batches through existing batch mappings
                    _link_challan_item_to_ledger(ledger_entry, challan_item)


def _get_previous_balance(godown, product):
    """
    Get the most recent balance for a godown-product combination from ledger.
    Returns 0 if no previous entries exist.
    """
    try:
        last_entry = GodownInventoryLedger.objects.filter(
            godown=godown,
            product=product,
            entry_status__in=['CONFIRMED', 'SYSTEM_GENERATED']
        ).latest('transaction_date', 'created_at')
        return last_entry.balance_after_transaction
    except GodownInventoryLedger.DoesNotExist:
        return 0


def _link_outward_transaction_to_batches(ledger_entry, quantity_needed):
    """
    Link outward transaction to inventory batches using FIFO method.
    Creates LedgerBatchMapping records for audit trail.
    """
    remaining_quantity = quantity_needed
    
    # Get available inventory batches in FIFO order
    available_batches = GodownInventory.objects.filter(
        godown=ledger_entry.godown,
        product=ledger_entry.product,
        good_bags_available__gt=0,
        status='ACTIVE'
    ).order_by('received_date')
    
    for batch in available_batches:
        if remaining_quantity <= 0:
            break
            
        # Calculate how many bags to take from this batch
        batch_consumption = min(remaining_quantity, batch.good_bags_available)
        
        # Create batch mapping record
        LedgerBatchMapping.objects.create(
            ledger_entry=ledger_entry,
            inventory_batch=batch,
            quantity_affected=batch_consumption,
            batch_balance_before=batch.good_bags_available,
            batch_balance_after=batch.good_bags_available - batch_consumption
        )
        
        remaining_quantity -= batch_consumption
    
    if remaining_quantity > 0:
        # Log warning if we couldn't fulfill the complete quantity
        ledger_entry.transaction_notes += f' WARNING: Could not link {remaining_quantity} bags to inventory batches.'
        ledger_entry.save()


def _link_challan_item_to_ledger(ledger_entry, challan_item):
    """
    Link challan item's existing batch mappings to the ledger entry.
    This maintains the FIFO traceability from challan to ledger.
    """
    # Get existing batch mappings from the challan item
    from .models import ChallanItemBatchMapping
    
    challan_batch_mappings = ChallanItemBatchMapping.objects.filter(
        challan_item=challan_item
    )
    
    for mapping in challan_batch_mappings:
        LedgerBatchMapping.objects.create(
            ledger_entry=ledger_entry,
            inventory_batch=mapping.inventory_batch,
            quantity_affected=mapping.bags_consumed,
            batch_balance_before=mapping.inventory_batch.good_bags_available + mapping.bags_consumed,
            batch_balance_after=mapping.inventory_batch.good_bags_available
        )


# Manual adjustment signals
def create_manual_adjustment_entry(godown, product, quantity, transaction_type, user, notes=''):
    """
    Helper function to create manual adjustment entries.
    Can be called from admin or API views for manual stock adjustments.
    """
    with transaction.atomic():
        # Calculate balance before creating entry
        previous_balance = _get_previous_balance(godown, product)
        if transaction_type.startswith('INWARD'):
            new_balance = previous_balance + quantity
        else:
            new_balance = previous_balance - quantity
            
        ledger_entry = GodownInventoryLedger.objects.create(
            transaction_type=transaction_type,
            godown=godown,
            product=product,
            inward_quantity=quantity if transaction_type.startswith('INWARD') else 0,
            outward_quantity=quantity if transaction_type.startswith('OUTWARD') else 0,
            balance_after_transaction=new_balance,
            condition_at_transaction='GOOD',
            is_system_generated=False,
            entry_status='PENDING',  # Manual entries need approval
            approval_required=True,
            created_by=user,
            transaction_notes=f'Manual adjustment: {notes}'
        )
        
        return ledger_entry


def create_variance_adjustment_entry(variance_record, adjusting_user):
    """
    Create ledger entry to adjust inventory based on variance record.
    Used when resolving inventory discrepancies.
    """
    adjustment_quantity = abs(variance_record.variance_quantity)
    transaction_type = 'INWARD_ADJUSTMENT' if variance_record.is_excess() else 'OUTWARD_ADJUSTMENT'
    
    with transaction.atomic():
        # Calculate balance before creating entry
        previous_balance = _get_previous_balance(variance_record.godown, variance_record.product)
        if variance_record.is_excess():
            new_balance = previous_balance + adjustment_quantity
        else:
            new_balance = previous_balance - adjustment_quantity
            
        ledger_entry = GodownInventoryLedger.objects.create(
            transaction_type='BALANCE_ADJUSTMENT',
            godown=variance_record.godown,
            product=variance_record.product,
            inward_quantity=adjustment_quantity if variance_record.is_excess() else 0,
            outward_quantity=adjustment_quantity if variance_record.is_shortage() else 0,
            balance_after_transaction=new_balance,
            condition_at_transaction='MIXED',
            is_system_generated=False,
            entry_status='CONFIRMED',  # Variance adjustments are pre-approved
            created_by=adjusting_user,
            authorized_by=adjusting_user,
            transaction_notes=f'Variance adjustment from {variance_record.variance_id}: {variance_record.root_cause}',
            reference_document=variance_record.variance_id
        )
        
        # Link the variance record to this adjustment
        variance_record.adjustment_ledger_entry = ledger_entry
        variance_record.save()
        
        return ledger_entry


@receiver(post_save, sender=GodownInventoryLedger)
def update_daily_balance(sender, instance, created, **kwargs):
    """
    Update or create GodownDailyBalance record when a ledger entry is created or updated.
    This ensures daily balance tracking is always up to date with inventory movements.
    """
    logger.debug(f"GodownInventoryLedger signal fired for transaction {instance.id}: created={created}, transaction_date={instance.transaction_date}")
    
    # Only process confirmed or system-generated entries
    if instance.entry_status not in ['CONFIRMED', 'SYSTEM_GENERATED']:
        logger.debug(f"Skipping daily balance update for ledger entry {instance.id} - status: {instance.entry_status}")
        return
    
    # Get the transaction date (date part only)
    transaction_date = instance.transaction_date.date()
    
    try:
        with transaction.atomic():
            logger.debug(f"Updating daily balance for {instance.godown.code}-{instance.product.code} on {transaction_date}")
            
            # Get or create daily balance record for this date
            daily_balance, db_created = GodownDailyBalance.objects.get_or_create(
                balance_date=transaction_date,
                godown=instance.godown,
                product=instance.product,
                defaults={
                    'opening_balance': 0,
                    'total_inward': 0,
                    'total_outward': 0,
                    'closing_balance': 0,
                    'balance_status': 'CALCULATED',
                    'is_auto_calculated': True,
                    'calculation_timestamp': timezone.now(),
                    'created_by': instance.created_by
                }
            )
            
            if db_created:
                logger.info(f"Created new daily balance record for {instance.godown.code}-{instance.product.code} on {transaction_date}")
            else:
                logger.debug(f"Found existing daily balance record for {instance.godown.code}-{instance.product.code} on {transaction_date}")
            
            # Recalculate the entire day's transactions for this godown-product
            _recalculate_daily_balance(daily_balance, transaction_date)
            
            logger.info(f"Updated daily balance for {instance.godown.code}-{instance.product.code} on {transaction_date}: opening={daily_balance.opening_balance}, inward={daily_balance.total_inward}, outward={daily_balance.total_outward}, closing={daily_balance.closing_balance}")
            
    except Exception as e:
        logger.error(f"Error updating daily balance for ledger entry {instance.id}: {str(e)}", exc_info=True)
        raise


def _recalculate_daily_balance(daily_balance, target_date):
    """
    Recalculate daily balance for a specific date by aggregating all ledger entries.
    This ensures accuracy even if entries are added out of order.
    """
    from django.db.models import Sum
    
    logger.debug(f"Recalculating daily balance for {daily_balance.godown.code}-{daily_balance.product.code} on {target_date}")
    
    # Get opening balance (closing balance from previous day)
    previous_date_balance = GodownDailyBalance.objects.filter(
        godown=daily_balance.godown,
        product=daily_balance.product,
        balance_date__lt=target_date
    ).order_by('-balance_date').first()
    
    opening_balance = previous_date_balance.closing_balance if previous_date_balance else 0
    logger.debug(f"Opening balance: {opening_balance}")
    
    # Get all confirmed/system-generated ledger entries for this date
    day_entries = GodownInventoryLedger.objects.filter(
        godown=daily_balance.godown,
        product=daily_balance.product,
        transaction_date__date=target_date,
        entry_status__in=['CONFIRMED', 'SYSTEM_GENERATED']
    )
    
    # Aggregate inward and outward quantities
    aggregates = day_entries.aggregate(
        total_inward=Sum('inward_quantity') or 0,
        total_outward=Sum('outward_quantity') or 0
    )
    
    total_inward = aggregates['total_inward'] or 0
    total_outward = aggregates['total_outward'] or 0
    
    logger.debug(f"Daily transactions - Inward: {total_inward}, Outward: {total_outward}")
    
    # Calculate quality breakdown
    good_condition = day_entries.filter(
        condition_at_transaction='GOOD'
    ).aggregate(Sum('inward_quantity'))['inward_quantity__sum'] or 0
    
    damaged = day_entries.filter(
        condition_at_transaction='DAMAGED'
    ).aggregate(Sum('inward_quantity'))['inward_quantity__sum'] or 0
    
    # Count active batches for this godown-product
    active_batches = GodownInventory.objects.filter(
        godown=daily_balance.godown,
        product=daily_balance.product,
        good_bags_available__gt=0,
        status='ACTIVE'
    ).count()
    
    # Calculate oldest batch age
    oldest_batch = GodownInventory.objects.filter(
        godown=daily_balance.godown,
        product=daily_balance.product,
        good_bags_available__gt=0,
        status='ACTIVE'
    ).order_by('received_date').first()
    
    oldest_batch_age = None
    if oldest_batch:
        # Convert received_date to date if it's datetime
        batch_date = oldest_batch.received_date
        if hasattr(batch_date, 'date'):
            batch_date = batch_date.date()
        oldest_batch_age = (target_date - batch_date).days
    
    # Update the daily balance record
    daily_balance.opening_balance = opening_balance
    daily_balance.total_inward = total_inward
    daily_balance.total_outward = total_outward
    daily_balance.closing_balance = opening_balance + total_inward - total_outward
    daily_balance.active_batches_count = active_batches
    daily_balance.oldest_batch_age_days = oldest_batch_age
    daily_balance.good_condition_bags = good_condition
    daily_balance.damaged_bags = damaged
    daily_balance.calculation_timestamp = timezone.now()
    daily_balance.is_auto_calculated = True
    
    # Preserve existing physical count and verification status
    if daily_balance.physical_count is not None:
        daily_balance.variance_quantity = daily_balance.physical_count - daily_balance.closing_balance
        if daily_balance.variance_quantity != 0:
            daily_balance.balance_status = 'DISCREPANCY'
        else:
            daily_balance.balance_status = 'VERIFIED'
    else:
        daily_balance.balance_status = 'CALCULATED'
        daily_balance.variance_quantity = 0
    
    daily_balance.save()
    
    logger.debug(f"Daily balance recalculated: {daily_balance.closing_balance} bags (variance: {daily_balance.variance_quantity})")
    
    # Update any subsequent days that might be affected
    _update_subsequent_daily_balances(daily_balance, target_date)


def _update_subsequent_daily_balances(changed_balance, changed_date):
    """
    Update opening balances for all subsequent days after a balance change.
    This ensures the running balance chain remains accurate.
    """
    logger.debug(f"Updating subsequent daily balances after {changed_date}")
    
    # Get all daily balance records for the same godown-product after the changed date
    subsequent_balances = GodownDailyBalance.objects.filter(
        godown=changed_balance.godown,
        product=changed_balance.product,
        balance_date__gt=changed_date
    ).order_by('balance_date')
    
    previous_closing = changed_balance.closing_balance
    
    for daily_balance in subsequent_balances:
        if daily_balance.opening_balance != previous_closing:
            logger.debug(f"Updating opening balance for {daily_balance.balance_date}: {daily_balance.opening_balance} -> {previous_closing}")
            
            daily_balance.opening_balance = previous_closing
            daily_balance.closing_balance = daily_balance.opening_balance + daily_balance.total_inward - daily_balance.total_outward
            
            # Recalculate variance if physical count exists
            if daily_balance.physical_count is not None:
                daily_balance.variance_quantity = daily_balance.physical_count - daily_balance.closing_balance
                if daily_balance.variance_quantity != 0:
                    daily_balance.balance_status = 'DISCREPANCY'
                else:
                    daily_balance.balance_status = 'VERIFIED'
            
            daily_balance.save()
            
        previous_closing = daily_balance.closing_balance
    
    logger.debug(f"Updated {subsequent_balances.count()} subsequent daily balance records")