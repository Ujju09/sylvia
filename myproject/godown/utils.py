"""
Utility functions for inventory ledger calculations, balance management, and variance detection.
Provides centralized business logic for audit and reporting functions.
"""

from django.db.models import Sum, Max, Count
from django.utils import timezone
from datetime import timedelta, datetime
from decimal import Decimal
from typing import Dict, List
from PIL import Image, ImageDraw, ImageFont
import io

from .models import (
    GodownInventoryLedger, GodownDailyBalance, InventoryVariance,
    GodownLocation, GodownInventory, LoadingRequest
)


def _load_font(size, bold=False):
    """
    Load a TrueType font with fallback support for cross-platform compatibility.

    Tries multiple font sources in order:
    1. DejaVu fonts (bundled with many Linux distributions)
    2. System fonts (Arial, Helvetica, etc.)
    3. Pillow's default font

    Args:
        size: Font size in points
        bold: Whether to load bold variant

    Returns:
        ImageFont object
    """
    # List of fonts to try, in order of preference
    font_candidates = [
        # DejaVu fonts (common on Linux servers)
        "DejaVuSans-Bold" if bold else "DejaVuSans",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",

        # System fonts (macOS, Windows)
        "Arial-Bold" if bold else "Arial",
        "Helvetica-Bold" if bold else "Helvetica",

        # Full paths for macOS
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/Library/Fonts/Arial.ttf",

        # Windows paths
        "C:\\Windows\\Fonts\\arialbd.ttf" if bold else "C:\\Windows\\Fonts\\arial.ttf",
    ]

    # Try each font candidate
    for font_name in font_candidates:
        try:
            return ImageFont.truetype(font_name, size)
        except (OSError, IOError):
            continue

    # If all else fails, use default font
    try:
        return ImageFont.load_default(size=size)
    except:
        return ImageFont.load_default()


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


def generate_opening_stock_image(products_data, date_str):
    """
    Generate a clean, minimal image showing opening stock for all products.

    Args:
        products_data: List of dicts with keys: product_name, opening_stock
        date_str: Date string to display (e.g., "11 Nov, 2025")

    Returns:
        PIL Image object
    """
    # Image dimensions - portrait format for mobile sharing
    width = 1080
    height = 1920

    # Colors
    bg_color = (255, 255, 255)  # White
    text_color = (40, 40, 40)  # Dark gray
    watermark_color = (220, 220, 220)  # Very light gray

    # Create image
    img = Image.new('RGB', (width, height), bg_color)
    draw = ImageDraw.Draw(img)

    # Load fonts with cross-platform support
    title_font = _load_font(60, bold=True)
    date_font = _load_font(48)
    header_font = _load_font(44, bold=True)
    content_font = _load_font(40)
    watermark_font = _load_font(36)

    # Draw date in top left corner
    date_x = 60
    date_y = 80
    draw.text((date_x, date_y), date_str, fill=text_color, font=date_font)

   
    # Table starting position
    table_start_y = 320
    row_height = 70

    # Draw table headers
    col1_x = 80  # Product name column
    col2_x = 750  # Opening stock column

    header_y = table_start_y
    draw.text((col1_x, header_y), "Product", fill=text_color, font=header_font)
    draw.text((col2_x, header_y), "Opening Stock", fill=text_color, font=header_font)

    # Draw a subtle line under headers
    line_y = header_y + 60
    draw.line([(60, line_y), (width - 60, line_y)], fill=(200, 200, 200), width=2)

    # Draw product rows
    current_y = line_y + 30
    for product in products_data:
        if current_y > height - 300:  # Leave space for watermark
            break

        # Product name
        product_name = product['product_name']
        if len(product_name) > 30:
            product_name = product_name[:27] + "..."
        draw.text((col1_x, current_y), product_name, fill=text_color, font=content_font)

        # Opening stock
        stock_text = str(product['opening_stock'])
        draw.text((col2_x, current_y), stock_text, fill=text_color, font=content_font)

        current_y += row_height

    # Draw total if available
    if products_data:
        total_stock = sum(p['opening_stock'] for p in products_data)
        current_y += 20
        # Draw line before total
        draw.line([(60, current_y), (width - 60, current_y)], fill=(200, 200, 200), width=2)
        current_y += 30
        draw.text((col1_x, current_y), "Total", fill=text_color, font=header_font)
        draw.text((col2_x, current_y), str(total_stock), fill=text_color, font=header_font)

    # Draw watermark at bottom left
    watermark_text = "Shyam Distributors"
    watermark_x = 60
    watermark_y = height - 120
    draw.text((watermark_x, watermark_y), watermark_text, fill=watermark_color, font=watermark_font)

    return img


def generate_opening_stock_image_bytes(products_data, date_str):
    """
    Generate opening stock image and return as bytes for HTTP response.

    Args:
        products_data: List of dicts with keys: product_name, opening_stock
        date_str: Date string to display

    Returns:
        BytesIO object containing PNG image data
    """
    img = generate_opening_stock_image(products_data, date_str)

    # Convert to bytes
    img_io = io.BytesIO()
    img.save(img_io, format='PNG', quality=95)
    img_io.seek(0)

    return img_io


def generate_opening_stock_matrix_image(products_matrix, godown_codes, godown_names, date_str):
    """
    Generate a matrix-style image showing opening stock for all products across all godowns.

    Args:
        products_matrix: Dict with structure {product_name: {godown_code: opening_stock}}
        godown_codes: List of godown codes (determines column order)
        godown_names: Dict mapping godown_code to godown_name
        date_str: Date string to display (e.g., "11 Nov, 2025")

    Returns:
        PIL Image object
    """
    # Calculate dynamic dimensions based on number of godowns and products
    num_godowns = len(godown_codes)
    num_products = len(products_matrix)

    base_width = 400  # For product name column
    column_width = 160  # Width per godown column
    total_column_width = 160  # Width for total column

    width = base_width + (num_godowns * column_width) + total_column_width + 100  # Extra padding

    # Dynamic height calculation (max 7 products expected)
    # Top padding (date) + table header + products rows + totals row + bottom padding (watermark)
    top_padding = 150
    header_height = 90
    row_height = 60
    totals_height = 90
    bottom_padding = 150

    height = top_padding + header_height + (num_products * row_height) + totals_height + bottom_padding

    # Colors
    bg_color = (255, 255, 255)  # White
    text_color = (40, 40, 40)  # Dark gray
    header_color = (30, 30, 30)  # Darker for headers
    watermark_color = (220, 220, 220)  # Very light gray
    line_color = (200, 200, 200)  # Light gray for lines

    # Create image
    img = Image.new('RGB', (width, height), bg_color)
    draw = ImageDraw.Draw(img)

    # Load fonts with cross-platform support
    date_font = _load_font(38)
    header_font = _load_font(34, bold=True)
    content_font = _load_font(32)
    watermark_font = _load_font(32)

    # Draw date in top left corner
    date_x = 40
    date_y = 60
    draw.text((date_x, date_y), date_str, fill=text_color, font=date_font)

    # Table starting position
    table_start_y = 180
    row_height = 60

    # Column positions
    product_col_x = 40
    godown_col_start_x = product_col_x + base_width

    # Draw column headers
    header_y = table_start_y

    # Product column header
    draw.text((product_col_x, header_y), "Product", fill=header_color, font=header_font)

    # Godown column headers (use first 3-4 letters of godown code for compact display)
    current_x = godown_col_start_x
    for godown_code in godown_codes:
        # Use godown code for header (compact)
        header_text = godown_code if len(godown_code) <= 6 else godown_code[:6]
        draw.text((current_x + 10, header_y), header_text, fill=header_color, font=header_font)
        current_x += column_width

    # Total column header
    draw.text((current_x + 10, header_y), "Total", fill=header_color, font=header_font)

    # Draw line under headers
    line_y = header_y + 50
    draw.line([(30, line_y), (width - 30, line_y)], fill=line_color, width=2)

    # Draw product rows
    current_y = line_y + 20
    product_names = sorted(products_matrix.keys())

    # Column totals (sum per godown)
    column_totals = {code: 0 for code in godown_codes}
    grand_total = 0

    for product_name in product_names:
        # Product name (truncate if too long)
        display_name = product_name if len(product_name) <= 25 else product_name[:22] + "..."
        draw.text((product_col_x, current_y), display_name, fill=text_color, font=content_font)

        # Stock values for each godown
        current_x = godown_col_start_x
        row_total = 0

        for godown_code in godown_codes:
            stock = products_matrix[product_name].get(godown_code, 0)
            display_text = str(stock) if stock > 0 else "-"

            # Right-align numbers
            draw.text((current_x + 10, current_y), display_text, fill=text_color, font=content_font)

            row_total += stock
            column_totals[godown_code] += stock
            current_x += column_width

        # Row total
        draw.text((current_x + 10, current_y), str(row_total), fill=header_color, font=content_font)
        grand_total += row_total

        current_y += row_height

    # Draw line before totals
    totals_line_y = current_y + 10
    draw.line([(30, totals_line_y), (width - 30, totals_line_y)], fill=line_color, width=2)

    # Draw totals row
    totals_y = totals_line_y + 20
    draw.text((product_col_x, totals_y), "Total", fill=header_color, font=header_font)

    # Column totals
    current_x = godown_col_start_x
    for godown_code in godown_codes:
        draw.text((current_x + 10, totals_y), str(column_totals[godown_code]), fill=header_color, font=header_font)
        current_x += column_width

    # Grand total
    draw.text((current_x + 10, totals_y), str(grand_total), fill=header_color, font=header_font)

    # Draw watermark at bottom left (with proper spacing)
    watermark_text = "Shyam Distributors"
    watermark_x = 40
    watermark_y = height - 80  # Closer to bottom with dynamic height
    draw.text((watermark_x, watermark_y), watermark_text, fill=watermark_color, font=watermark_font)

    return img


def generate_opening_stock_matrix_image_bytes(products_matrix, godown_codes, godown_names, date_str):
    """
    Generate opening stock matrix image and return as bytes for HTTP response.

    Args:
        products_matrix: Dict with structure {product_name: {godown_code: opening_stock}}
        godown_codes: List of godown codes
        godown_names: Dict mapping godown_code to godown_name
        date_str: Date string to display

    Returns:
        BytesIO object containing PNG image data
    """
    img = generate_opening_stock_matrix_image(products_matrix, godown_codes, godown_names, date_str)

    # Convert to bytes
    img_io = io.BytesIO()
    img.save(img_io, format='PNG', quality=95)
    img_io.seek(0)

    return img_io


def generate_stock_aging_image(aging_data, date_str):
    """
    Generate a clean image showing stock aging report.

    Args:
        aging_data: List of dicts with keys: product_name, bucket_0_30, bucket_31_60, bucket_61_90, bucket_90_plus, total_stock
        date_str: Date string to display

    Returns:
        PIL Image object
    """
    # Image dimensions
    width = 1400 # Increased width for Action column
    height = 560 + (len(aging_data) * 80)  # Adaptive height

    # Colors
    bg_color = (255, 255, 255)
    text_color = (40, 40, 40)
    header_bg = (240, 240, 240)
    line_color = (200, 200, 200)
    watermark_color = (220, 220, 220)
    danger_color = (220, 53, 69) # Red for >90 days
    warning_color = (255, 193, 7) # Yellow/Orange for warning
    success_color = (40, 167, 69) # Green for success

    # Create image
    img = Image.new('RGB', (width, height), bg_color)
    draw = ImageDraw.Draw(img)

    # Load fonts
    title_font = _load_font(40, bold=True)
    date_font = _load_font(30)
    header_font = _load_font(28, bold=True)
    content_font = _load_font(28)
    watermark_font = _load_font(36)
    action_font = _load_font(18, bold=True)

    # Draw Title and Date
    draw.text((60, 60), "Stock Aging Report", fill=text_color, font=title_font)
    draw.text((60, 140), f"As of: {date_str}", fill=text_color, font=date_font)

    # Table Layout
    start_y = 250
    row_height = 80
    
    # Column positions (adjusted for center alignment of numbers)
    col_prod = 60
    # For numeric columns, these are center points
    col_0_30 = 450
    col_31_60 = 600
    col_61_90 = 750
    col_90_plus = 900
    col_total = 1020
    col_action = 1250 # Center for Action

    # Draw Header Background
    draw.rectangle([(40, start_y), (width - 40, start_y + row_height)], fill=header_bg)

    # Draw Headers
    header_y = start_y + 20
    draw.text((col_prod, header_y), "Product", fill=text_color, font=header_font)
    
    # Helper to draw centered text
    def draw_centered(text, x, y, font, fill):
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        draw.text((x - text_width / 2, y), text, fill=fill, font=font)

    draw_centered("0-30", col_0_30, header_y, header_font, text_color)
    draw_centered("31-60", col_31_60, header_y, header_font, text_color)
    draw_centered("61-90", col_61_90, header_y, header_font, text_color)
    draw_centered(">90", col_90_plus, header_y, header_font, danger_color)
    draw_centered("Total", col_total, header_y, header_font, text_color)
    draw_centered("Action", col_action, header_y, header_font, text_color)

    current_y = start_y + row_height

    # Draw Rows
    total_0_30 = 0
    total_31_60 = 0
    total_61_90 = 0
    total_90_plus = 0
    grand_total = 0

    for item in aging_data:
        # Product Name (Truncate if too long)
        prod_name = item['product_name']
        if len(prod_name) > 18:
            prod_name = prod_name[:15] + "..."
        
        draw.text((col_prod, current_y + 20), prod_name, fill=text_color, font=content_font)
        
        draw_centered(str(item['bucket_0_30']), col_0_30, current_y + 20, content_font, text_color)
        draw_centered(str(item['bucket_31_60']), col_31_60, current_y + 20, content_font, text_color)
        draw_centered(str(item['bucket_61_90']), col_61_90, current_y + 20, content_font, text_color)
        draw_centered(str(item['bucket_90_plus']), col_90_plus, current_y + 20, content_font, danger_color)
        draw_centered(str(item['total_stock']), col_total, current_y + 20, _load_font(32, bold=True), text_color)

        # Action Column
        action_text = item.get('action', '')
        action_color = text_color
        if "CRITICAL" in action_text:
            action_color = danger_color
        elif "High Alert" in action_text:
            action_color = warning_color # Use warning color but maybe darker for visibility? Let's stick to danger for high alert too or standard text
            action_color = (255, 140, 0) # Dark Orange
        elif "Monitor" in action_text:
            action_color = (23, 162, 184) # Info Blue
        elif "Normal" in action_text:
            action_color = success_color

        # Split action text if too long? "CRITICAL: Stop Sending" fits?
        # Let's just draw centered
        draw_centered(action_text, col_action, current_y + 25, _load_font(24, bold=True), action_color)

        # Draw separator line
        draw.line([(60, current_y + row_height), (width - 60, current_y + row_height)], fill=line_color, width=1)
        
        current_y += row_height

        # Accumulate totals
        total_0_30 += item['bucket_0_30']
        total_31_60 += item['bucket_31_60']
        total_61_90 += item['bucket_61_90']
        total_90_plus += item['bucket_90_plus']
        grand_total += item['total_stock']

    # Draw Totals Row
    current_y += 10
    draw.line([(60, current_y), (width - 60, current_y)], fill=text_color, width=3)
    current_y += 10
    
    draw.text((col_prod, current_y + 20), "TOTAL", fill=text_color, font=header_font)
    
    draw_centered(str(total_0_30), col_0_30, current_y + 20, header_font, text_color)
    draw_centered(str(total_31_60), col_31_60, current_y + 20, header_font, text_color)
    draw_centered(str(total_61_90), col_61_90, current_y + 20, header_font, text_color)
    draw_centered(str(total_90_plus), col_90_plus, current_y + 20, header_font, danger_color)
    draw_centered(str(grand_total), col_total, current_y + 20, header_font, text_color)
    
    # Bottom line for table closure
    current_y += 80
    draw.line([(60, current_y), (width - 60, current_y)], fill=text_color, width=3)

    # Watermark
    watermark_text = "Shyam Distributors"
    draw.text((60, height - 80), watermark_text, fill=watermark_color, font=watermark_font)

    return img