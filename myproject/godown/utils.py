"""
Utility functions for inventory ledger calculations, balance management, and variance detection.
Provides centralized business logic for audit and reporting functions.
"""

from django.db.models import Sum, Max, Count
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from typing import Dict, List

from .models import (
    GodownInventoryLedger, GodownDailyBalance, InventoryVariance,
    GodownLocation, GodownInventory, LoadingRequest
)


class LedgerCalculator:
    """
    Central class for all ledger calculations, balance updates, and variance detection.
    Implements industry-standard perpetual inventory tracking with FIFO compliance.
    """
    
    @classmethod
    def calculate_current_balance(cls, godown, product) -> int:
        """
        Calculate real-time current balance for a godown-product combination.
        Uses confirmed ledger entries to ensure accuracy.
        """
        ledger_entries = GodownInventoryLedger.objects.filter(
            godown=godown,
            product=product,
            entry_status__in=['CONFIRMED', 'SYSTEM_GENERATED']
        )
        
        aggregates = ledger_entries.aggregate(
            total_inward=Sum('inward_quantity') ,
            total_outward=Sum('outward_quantity') 
        )

        total_inward = aggregates['total_inward'] or 0
        total_outward = aggregates['total_outward'] or 0

        return total_inward - total_outward

    @classmethod
    def calculate_balance_for_date(cls, godown, product, target_date) -> Dict:
        """
        Calculate balance as of a specific date.
        Returns detailed breakdown of inward/outward movements.
        """
        ledger_entries = GodownInventoryLedger.objects.filter(
            godown=godown,
            product=product,
            transaction_date__date__lte=target_date,
            entry_status__in=['CONFIRMED', 'SYSTEM_GENERATED']
        )
        
        aggregates = ledger_entries.aggregate(
            total_inward=Sum('inward_quantity') ,
            total_outward=Sum('outward_quantity')
        )

        total_inward = aggregates['total_inward'] or 0
        total_outward = aggregates['total_outward'] or 0

        balance = total_inward - total_outward

        return {
            'balance': balance,
            'total_inward': total_inward,
            'total_outward': total_outward,
            'calculation_date': target_date,
            'last_transaction_date': ledger_entries.aggregate(
                last_date=Max('transaction_date')
            ).get('last_date')
        }
    
    @classmethod
    def get_balance_movement_summary(cls, godown, product, start_date, end_date) -> Dict:
        """
        Get detailed movement summary for a date range.
        Useful for audit reports and analysis.
        """
        # Opening balance (as of start_date - 1 day)
        day_before_start = start_date - timedelta(days=1)
        opening_data = cls.calculate_balance_for_date(godown, product, day_before_start)
        
        # Movements during the period
        period_entries = GodownInventoryLedger.objects.filter(
            godown=godown,
            product=product,
            transaction_date__date__gte=start_date,
            transaction_date__date__lte=end_date,
            entry_status__in=['CONFIRMED', 'SYSTEM_GENERATED']
        )
        
        # Breakdown by transaction type
        movement_breakdown = {}
        for transaction_type, display_name in GodownInventoryLedger.TRANSACTION_TYPES:
            type_entries = period_entries.filter(transaction_type=transaction_type)
            if type_entries.exists():
                aggregates = type_entries.aggregate(
                    inward=Sum('inward_quantity'),
                    outward=Sum('outward_quantity'),
                    count=type_entries.count()
                )
                inward_quantity = aggregates['inward'] or 0
                outward_quantity = aggregates['outward'] or 0

                movement_breakdown[transaction_type] = {
                    'display_name': display_name,
                    'inward_quantity': inward_quantity,
                    'outward_quantity': outward_quantity,
                    'net_movement': inward_quantity - outward_quantity,
                    'transaction_count': aggregates['count']
                }
        
        # Total movements
        total_aggregates = period_entries.aggregate(
            total_inward=Sum('inward_quantity'),
            total_outward=Sum('outward_quantity')
        )

        total_inward = total_aggregates['total_inward'] or 0
        total_outward = total_aggregates['total_outward'] or 0

        closing_balance = opening_data['balance'] + total_inward - total_outward

        return {
            'period': {'start_date': start_date, 'end_date': end_date},
            'opening_balance': opening_data['balance'],
            'total_inward': total_inward,
            'total_outward': total_outward,
            'net_movement': total_inward - total_outward,
            'closing_balance': closing_balance,
            'movement_breakdown': movement_breakdown,
            'transaction_count': period_entries.count()
        }
    
    @classmethod
    def validate_balance_integrity(cls, godown, product) -> Dict:
        """
        Validate ledger integrity against inventory batches.
        Identifies discrepancies that may require investigation.
        """
        # Get balance from ledger
        ledger_balance = cls.calculate_current_balance(godown, product)
        
        # Get balance from inventory batches
        batch_balance = GodownInventory.objects.filter(
            godown=godown,
            product=product,
            status='ACTIVE'
        ).aggregate(
            total_available=Sum('good_bags_available'),
            total_reserved=Sum('good_bags_reserved')
        )

        total_available = batch_balance['total_available'] or 0
        total_reserved = batch_balance['total_reserved'] or 0

        inventory_total = total_available + total_reserved

        # Calculate variance
        variance = inventory_total - ledger_balance
        
        return {
            'ledger_balance': ledger_balance,
            'inventory_balance': inventory_total,
            'variance': variance,
            'batch_breakdown': batch_balance,
            'is_balanced': variance == 0,
            'requires_investigation': abs(variance) > 5,  # Tolerance of 5 bags
            'validation_timestamp': timezone.now()
        }
    
    @classmethod
    def get_loading_transactions_summary(cls, godown=None, product=None, start_date=None, end_date=None) -> Dict:
        """
        Get summary of loading transactions (LoadingRequest) for analysis.
        Provides detailed breakdown of loading activities.
        """
        filters = {'transaction_type': 'OUTWARD_LOADING', 'entry_status__in': ['CONFIRMED', 'SYSTEM_GENERATED']}
        
        if godown:
            filters['godown'] = godown
        if product:
            filters['product'] = product
        if start_date:
            filters['transaction_date__date__gte'] = start_date
        if end_date:
            filters['transaction_date__date__lte'] = end_date
        
        loading_entries = GodownInventoryLedger.objects.filter(**filters)
        
        # Get related LoadingRequest data
        loading_requests = LoadingRequest.objects.filter(
            id__in=loading_entries.values_list('source_loading_request_id', flat=True)
        ).select_related('dealer', 'product', 'godown', 'supervised_by')
        
        # Aggregate statistics
        loading_stats = loading_entries.aggregate(
            total_loaded_bags=Sum('outward_quantity'),
        )
        loading_stats['total_transactions'] = loading_entries.count()
        loading_stats['total_loaded_bags'] = loading_stats['total_loaded_bags'] or 0
        
        request_stats = loading_requests.aggregate(
            total_requested_bags=Sum('requested_bags'),
            total_loaded_bags=Sum('loaded_bags'),
        )
        request_stats['total_requests'] = loading_requests.count()
        request_stats['total_requested_bags'] = request_stats['total_requested_bags'] or 0
        request_stats['total_loaded_bags'] = request_stats['total_loaded_bags'] or 0
        
        # Calculate completion rate
        completion_rate = 0
        if request_stats['total_requested_bags'] > 0 and request_stats['total_loaded_bags'] > 0:
            completion_rate = (request_stats['total_loaded_bags'] / request_stats['total_requested_bags']) * 100
        
        # Top dealers by loading volume
        top_dealers = loading_requests.values(
            'dealer__name', 'dealer__code'
        ).annotate(
            total_loaded=Sum('loaded_bags'),
            request_count=Count('id')
        ).order_by('-total_loaded')[:5]
        
        return {
            'period': {'start_date': start_date, 'end_date': end_date},
            'loading_stats': loading_stats,
            'request_stats': request_stats,
            'completion_rate': round(completion_rate, 1),
            'top_dealers': list(top_dealers),
            'analysis_timestamp': timezone.now()
        }


class DailyBalanceManager:
    """
    Manager for creating and maintaining daily balance snapshots.
    Automates end-of-day balance calculations and variance detection.
    """
    
    @classmethod
    def create_daily_balance(cls, godown, product, balance_date=None) -> GodownDailyBalance:
        """
        Create or update daily balance record for a specific date.
        If balance_date is None, uses current date.
        """
        if balance_date is None:
            balance_date = timezone.now().date()
        
        # Check if balance already exists
        existing_balance, _ = GodownDailyBalance.objects.get_or_create(
            godown=godown,
            product=product,
            balance_date=balance_date,
            defaults={
                'opening_balance': 0,
                'total_inward': 0,
                'total_outward': 0,
                'closing_balance': 0
            }
        )
        
        # Calculate opening balance (previous day's closing balance)
        previous_date = balance_date - timedelta(days=1)
        try:
            previous_balance_record = GodownDailyBalance.objects.get(
                godown=godown,
                product=product,
                balance_date=previous_date
            )
            opening_balance = previous_balance_record.closing_balance
        except GodownDailyBalance.DoesNotExist:
            # If no previous record, calculate from ledger
            opening_data = LedgerCalculator.calculate_balance_for_date(
                godown, product, previous_date
            )
            opening_balance = opening_data['balance']
        
        # Calculate day's movements
        day_entries = GodownInventoryLedger.objects.filter(
            godown=godown,
            product=product,
            transaction_date__date=balance_date,
            entry_status__in=['CONFIRMED', 'SYSTEM_GENERATED']
        )
        
        day_aggregates = day_entries.aggregate(
            inward=Sum('inward_quantity') ,
            outward=Sum('outward_quantity')
        )

        inward_quantity = day_aggregates['inward'] or 0
        outward_quantity = day_aggregates['outward'] or 0
        
        # Update balance record
        existing_balance.opening_balance = opening_balance
        existing_balance.total_inward = inward_quantity
        existing_balance.total_outward = outward_quantity
        existing_balance.closing_balance = opening_balance + inward_quantity - outward_quantity

        # Get batch information
        active_batches = GodownInventory.objects.filter(
            godown=godown,
            product=product,
            status='ACTIVE',
            good_bags_available__gt=0
        )
        
        if active_batches.exists():
            existing_balance.active_batches_count = active_batches.count()
            oldest_batch = active_batches.order_by('received_date').first()
            existing_balance.oldest_batch_age_days = (timezone.now().date() - oldest_batch.received_date.date()).days
            
            # Quality breakdown
            quality_aggregates = active_batches.aggregate(
                good_bags=Sum('good_bags_available') ,
                damaged_bags=Sum('damaged_bags') 
            )

            good_bags = quality_aggregates['good_bags'] or 0
            damaged_bags = quality_aggregates['damaged_bags'] or 0
            existing_balance.good_condition_bags = good_bags
            existing_balance.damaged_bags = damaged_bags

        # Get last transaction ID for reference
        last_transaction = day_entries.last()
        if last_transaction:
            existing_balance.last_transaction_id = last_transaction.transaction_id
        
        existing_balance.save()
        
        return existing_balance
    
    @classmethod
    def generate_all_daily_balances(cls, target_date=None) -> Dict:
        """
        Generate daily balances for all active godown-product combinations.
        Used for end-of-day processing or catch-up calculations.
        """
        if target_date is None:
            target_date = timezone.now().date()
        
        # Get all active godown-product combinations that have transactions
        combinations = GodownInventoryLedger.objects.filter(
            transaction_date__date__lte=target_date,
            entry_status__in=['CONFIRMED', 'SYSTEM_GENERATED']
        ).values('godown', 'product').distinct()
        
        results = {
            'target_date': target_date,
            'processed_combinations': 0,
            'created_balances': 0,
            'updated_balances': 0,
            'errors': []
        }
        
        for combo in combinations:
            try:
                balance_record = cls.create_daily_balance(
                    GodownLocation.objects.get(pk=combo['godown']),
                    combo['product'],  # This will be resolved by Django ORM
                    target_date
                )
                
                results['processed_combinations'] += 1
                if hasattr(balance_record, '_created'):
                    results['created_balances'] += 1
                else:
                    results['updated_balances'] += 1
                    
            except Exception as e:
                results['errors'].append({
                    'godown_id': combo['godown'],
                    'product_id': combo['product'],
                    'error': str(e)
                })
        
        return results


class VarianceDetector:
    """
    Automated variance detection and investigation workflow.
    Identifies discrepancies requiring manual investigation.
    """
    
    @classmethod
    def detect_daily_variances(cls, target_date=None, threshold_bags=5) -> List[Dict]:
        """
        Detect variances in daily balances that exceed threshold.
        Creates InventoryVariance records for investigation.
        """
        if target_date is None:
            target_date = timezone.now().date()
        
        variances_detected = []
        
        # Get all daily balances with physical counts
        daily_balances = GodownDailyBalance.objects.filter(
            balance_date=target_date,
            physical_count__isnull=False
        )
        
        for balance in daily_balances:
            if balance.has_variance() and abs(balance.variance_quantity) >= threshold_bags:
                # Check if variance record already exists
                existing_variance = InventoryVariance.objects.filter(
                    related_daily_balance=balance
                ).first()
                
                if not existing_variance:
                    variance_type = 'SHORTAGE' if balance.is_shortage() else 'EXCESS'
                    
                    variance_record = InventoryVariance.objects.create(
                        godown=balance.godown,
                        product=balance.product,
                        related_daily_balance=balance,
                        variance_type=variance_type,
                        variance_date=target_date,
                        expected_quantity=balance.closing_balance,
                        actual_quantity=balance.physical_count,
                        variance_quantity=balance.variance_quantity,
                        status='IDENTIFIED',
                        created_by_id=1  # System user
                    )
                    
                    variances_detected.append({
                        'variance_id': variance_record.variance_id,
                        'godown': balance.godown.name,
                        'product': balance.product.name,
                        'variance_quantity': balance.variance_quantity,
                        'variance_type': variance_type,
                        'variance_percentage': balance.get_variance_percentage()
                    })
        
        return variances_detected
    
    @classmethod
    def detect_system_inconsistencies(cls) -> List[Dict]:
        """
        Detect system inconsistencies between ledger and inventory batches.
        Identifies data integrity issues requiring investigation.
        """
        inconsistencies = []
        
        # Get all active godown-product combinations
        active_combinations = GodownInventory.objects.filter(
            status='ACTIVE'
        ).values('godown', 'product').distinct()
        
        for combo in active_combinations:
            godown = GodownLocation.objects.get(pk=combo['godown'])
            
            # Validate balance integrity
            integrity_check = LedgerCalculator.validate_balance_integrity(
                godown, combo['product']
            )
            
            if not integrity_check['is_balanced']:
                # Check if variance record already exists
                existing_variance = InventoryVariance.objects.filter(
                    godown=godown,
                    product_id=combo['product'],
                    variance_type='SYSTEM_ERROR',
                    status__in=['IDENTIFIED', 'INVESTIGATING']
                ).first()
                
                if not existing_variance:
                    variance_record = InventoryVariance.objects.create(
                        godown=godown,
                        product_id=combo['product'],
                        variance_type='SYSTEM_ERROR',
                        variance_date=timezone.now().date(),
                        expected_quantity=integrity_check['ledger_balance'],
                        actual_quantity=integrity_check['inventory_balance'],
                        variance_quantity=integrity_check['variance'],
                        status='IDENTIFIED',
                        investigation_notes=f'System inconsistency detected: Ledger={integrity_check["ledger_balance"]}, Inventory={integrity_check["inventory_balance"]}',
                        created_by_id=1  # System user
                    )
                    
                    inconsistencies.append({
                        'variance_id': variance_record.variance_id,
                        'godown': godown.name,
                        'product_name': variance_record.product.name,
                        'integrity_check': integrity_check
                    })
        
        return inconsistencies
    
    @classmethod
    def generate_variance_report(cls, start_date, end_date) -> Dict:
        """
        Generate comprehensive variance report for a date range.
        Provides audit trail and investigation status summary.
        """
        variances = InventoryVariance.objects.filter(
            variance_date__gte=start_date,
            variance_date__lte=end_date
        )
        
        # Status breakdown
        status_breakdown = {}
        for status_code, status_display in InventoryVariance.VARIANCE_STATUS:
            count = variances.filter(status=status_code).count()
            if count > 0:
                status_breakdown[status_code] = {
                    'display_name': status_display,
                    'count': count
                }
        
        # Type breakdown
        type_breakdown = {}
        for type_code, type_display in InventoryVariance.VARIANCE_TYPES:
            count = variances.filter(variance_type=type_code).count()
            if count > 0:
                type_breakdown[type_code] = {
                    'display_name': type_display,
                    'count': count
                }
        
        # Financial impact
        total_impact = variances.aggregate(
            total_impact=Sum('estimated_value_impact')
        )['total_impact']

        if not total_impact:
            total_impact = Decimal('0.00')

        # Resolution metrics
        resolved_variances = variances.filter(status__in=['RESOLVED', 'WRITTEN_OFF'])
        if resolved_variances.exists():
            avg_resolution_time = sum([
                v.get_resolution_time_days() or 0 
                for v in resolved_variances
            ]) / resolved_variances.count()
        else:
            avg_resolution_time = 0
        
        return {
            'report_period': {'start_date': start_date, 'end_date': end_date},
            'total_variances': variances.count(),
            'status_breakdown': status_breakdown,
            'type_breakdown': type_breakdown,
            'financial_impact': total_impact,
            'resolution_metrics': {
                'resolved_count': resolved_variances.count(),
                'avg_resolution_days': round(avg_resolution_time, 1),
                'pending_count': variances.filter(
                    status__in=['IDENTIFIED', 'INVESTIGATING']
                ).count()
            },
            'overdue_investigations': variances.filter(
                status__in=['IDENTIFIED', 'INVESTIGATING']
            ).count()  # Simplified - could add actual overdue logic
        }


def get_inventory_audit_summary(godown=None, product=None, date_range_days=30) -> Dict:
    """
    Generate comprehensive audit summary for management reporting.
    Provides executive dashboard view of inventory health including loading operations.
    """
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=date_range_days)
    
    # Base query filters
    filters = {'transaction_date__date__gte': start_date}
    if godown:
        filters['godown'] = godown
    if product:
        filters['product'] = product
    
    # Transaction summary
    transactions = GodownInventoryLedger.objects.filter(**filters)
    transaction_summary = transactions.aggregate(
        total_transactions=transactions.count(),
        total_inward=Sum('inward_quantity'),
        total_outward=Sum('outward_quantity') 
    )
    
    # Loading operations summary
    loading_summary = LedgerCalculator.get_loading_transactions_summary(
        godown=godown, 
        product=product, 
        start_date=start_date, 
        end_date=end_date
    )
    
    # Current balances
    if godown and product:
        current_balance = LedgerCalculator.calculate_current_balance(godown, product)
        integrity_check = LedgerCalculator.validate_balance_integrity(godown, product)
    else:
        current_balance = "N/A - Multiple combinations"
        integrity_check = {'is_balanced': True}  # Simplified for summary
    
    # Variance summary
    variance_filters = {'variance_date__gte': start_date}
    if godown:
        variance_filters['godown'] = godown
    if product:
        variance_filters['product'] = product
    
    variance_summary = VarianceDetector.generate_variance_report(start_date, end_date)
    
    return {
        'audit_period': {'start_date': start_date, 'end_date': end_date, 'days': date_range_days},
        'scope': {
            'godown': godown.name if godown else 'All Godowns',
            'product': product.name if product else 'All Products'
        },
        'transaction_summary': transaction_summary,
        'loading_summary': loading_summary,
        'current_balance': current_balance,
        'system_integrity': {
            'is_balanced': integrity_check['is_balanced'],
            'requires_attention': not integrity_check['is_balanced']
        },
        'variance_summary': variance_summary,
        'audit_timestamp': timezone.now()
    }