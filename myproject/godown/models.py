from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class BaseModel(models.Model):
    """Base model with common fields"""
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_%(class)s_records')
    
    class Meta:
        abstract = True


class GodownLocation(BaseModel):
    """Model for godown/warehouse locations"""
    name = models.CharField(max_length=200, help_text="Name of the godown/warehouse")
    code = models.CharField(max_length=20, unique=True, help_text="Unique code for the godown")
    address = models.TextField(blank=True, help_text="Full address of the godown")
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    pincode = models.CharField(max_length=10, blank=True)
    latitude = models.DecimalField(
        max_digits=10, decimal_places=7, null=True, blank=True,
        help_text="GPS latitude coordinate"
    )
    longitude = models.DecimalField(
        max_digits=10, decimal_places=7, null=True, blank=True,
        help_text="GPS longitude coordinate"
    )
    total_capacity = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        help_text="Total storage capacity in cubic meters"
    )
    manager = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='managed_godowns', help_text="Manager of this godown"
    )
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return f"{self.name} ({self.code})"
    
    class Meta:
        ordering = ['name']
        verbose_name = "Godown Location"
        verbose_name_plural = "Godown Locations"


class OrderInTransit(BaseModel):
    """Model for tracking incoming dispatches with e-way bills and expected quantities"""

    TRANSIT_STATUS_CHOICES = [
        ('IN_TRANSIT', 'In Transit'),
        ('ARRIVED', 'Arrived at Godown'),
        ('CANCELLED', 'Cancelled'),
    ]


    
    dispatch_id = models.CharField(
        max_length=50, blank=True,
        help_text="Unique ID for the dispatch", primary_key=True
    )


    product = models.ForeignKey(
        'sylvia.Product', on_delete=models.CASCADE, related_name='order_in_transit_product', blank=True,null=True
    )

    # E-way bill and transport details
    eway_bill_number = models.CharField(
        max_length=15, unique=True,
        help_text="E-way bill number for the shipment"
    )
    transport_document_number = models.CharField(
        max_length=50, blank=True,
        help_text="Transport receipt/challan number"
    )
    
    # Location and timing
    godown = models.ForeignKey(
        GodownLocation, on_delete=models.CASCADE, related_name='incoming_orders'
    )
   
    actual_arrival_date = models.DateTimeField(
        null=True, blank=True,
        help_text="Actual arrival date and time"
    )
    
    # Status tracking
    status = models.CharField(
        max_length=20, choices=TRANSIT_STATUS_CHOICES, default='IN_TRANSIT'
    )
    
    # Expected vs actual quantities
    expected_total_bags = models.PositiveIntegerField(
        help_text="Total expected bags as per invoice/order"
    )
    actual_received_bags = models.PositiveIntegerField(
        default=0,
        help_text="Actual bags received after counting"
    )
    
    # Quality and condition tracking
    good_bags = models.PositiveIntegerField(
        default=0,
        help_text="Number of bags in good condition"
    )
    damaged_bags = models.PositiveIntegerField(
        default=0,
        help_text="Number of damaged bags"
    )
    shortage_bags = models.PositiveIntegerField(
        default=0,
        help_text="Number of bags short from expected quantity"
    )
    excess_bags = models.PositiveIntegerField(
        default=0,
        help_text="Number of excess bags beyond expected quantity"
    )
    
    # Cross-over requirements
    crossover_required = models.BooleanField(
        default=False,
        help_text="Whether part of this shipment needs direct cross-over"
    )
    crossover_bags = models.PositiveIntegerField(
        default=0,
        help_text="Number of bags allocated for cross-over"
    )
    
    # Notes and remarks
    arrival_notes = models.TextField(
        blank=True,
        help_text="Notes about arrival condition, delays, etc."
    )
    
    
    def get_storage_bags(self):
        """Calculate number of bags going to storage"""
        return self.good_bags - self.crossover_bags

    def __str__(self):
        return f"Transit: {self.eway_bill_number}"
    
    class Meta:
        verbose_name = "Order in Transit"
        verbose_name_plural = "Orders in Transit"
        indexes = [
            models.Index(fields=['eway_bill_number']),
            models.Index(fields=['status', 'actual_arrival_date']),
            models.Index(fields=['godown', 'status']),
        ]


class GodownInventory(BaseModel):
    """FIFO-based inventory management for cement bags with separate quantity tracking"""
    
    INVENTORY_STATUS_CHOICES = [
        ('ACTIVE', 'Active Stock'),
        ('RESERVED', 'Reserved for Loading'),
        ('ALLOCATED', 'Allocated to Order'),
        ('EXPIRED', 'Expired/Old Stock'),
        ('DAMAGED', 'Damaged Stock'),
    ]
    
    # Core identification
    batch_id = models.CharField(
        max_length=50, unique=True, editable=False,
        help_text="Auto-generated FIFO batch identifier"
    )
    
    # Links to existing system
    godown = models.ForeignKey(
        GodownLocation, on_delete=models.CASCADE, related_name='inventory_batches'
    )
    product = models.ForeignKey(
        'sylvia.Product', on_delete=models.CASCADE, related_name='inventory_batches'
    )
    order_in_transit = models.ForeignKey(
        OrderInTransit, on_delete=models.CASCADE, related_name='inventory_batches',
        help_text="Source transit record for this inventory batch"
    )
    
    # FIFO tracking
    received_date = models.DateTimeField(
        auto_now_add=True,
        help_text="Date when this batch was received and stored"
    )
    
    # Detailed quantity breakdown
    total_bags_received = models.PositiveIntegerField(
        help_text="Total bags in this batch when first stored"
    )
    good_bags_available = models.PositiveIntegerField(
        help_text="Current available good bags in this batch"
    )
    good_bags_reserved = models.PositiveIntegerField(
        default=0,
        help_text="Good bags reserved for pending loading requests"
    )
    damaged_bags = models.PositiveIntegerField(
        default=0,
        help_text="Damaged bags identified after storage"
    )
    
    # Status and condition
    status = models.CharField(
        max_length=20, choices=INVENTORY_STATUS_CHOICES, default='ACTIVE'
    )
    
    # Location within godown
    storage_location = models.CharField(
        max_length=100, blank=True,
        help_text="Specific location within godown (e.g., Section A, Row 5)"
    )
    
    # Quality and aging
    quality_grade = models.CharField(
        max_length=20, choices=[
            ('A', 'Grade A - Excellent'),
            ('B', 'Grade B - Good'),
            ('C', 'Grade C - Average'),
            ('D', 'Grade D - Below Average'),
        ], default='A'
    )
    
    # Batch metadata
    manufacturing_date = models.DateField(
        null=True, blank=True,
        help_text="Manufacturing date of cement (if available)"
    )
    expiry_alert_date = models.DateField(
        null=True, blank=True,
        help_text="Date to alert for aging stock"
    )
    
    # Notes
    storage_notes = models.TextField(
        blank=True,
        help_text="Notes about storage conditions, quality observations"
    )
    
    def get_total_available_bags(self):
        """Get total available bags (not reserved)"""
        return self.good_bags_available
    
    def get_total_allocated_bags(self):
        """Get total allocated/reserved bags"""
        return self.good_bags_reserved
    
    def reserve_bags(self, quantity):
        """Reserve bags for loading request"""
        if quantity > self.good_bags_available:
            raise ValueError(f"Cannot reserve {quantity} bags, only {self.good_bags_available} available")
        
        self.good_bags_available -= quantity
        self.good_bags_reserved += quantity
        self.save()
    
    def release_reservation(self, quantity):
        """Release reserved bags back to available"""
        if quantity > self.good_bags_reserved:
            raise ValueError(f"Cannot release {quantity} bags, only {self.good_bags_reserved} reserved")
        
        self.good_bags_reserved -= quantity
        self.good_bags_available += quantity
        self.save()
    
    def consume_bags(self, quantity):
        """Consume reserved bags for actual loading"""
        if quantity > self.good_bags_reserved:
            raise ValueError(f"Cannot consume {quantity} bags, only {self.good_bags_reserved} reserved")
        
        self.good_bags_reserved -= quantity
        self.save()
    
    def save(self, *args, **kwargs):
        if not self.batch_id:
            # Generate FIFO batch ID: GODOWN_PRODUCT_DATETIME
            timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
            self.batch_id = f"{self.godown.code}_{self.product.code}_{timestamp}"
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.batch_id} - {self.good_bags_available} bags available"
    
    class Meta:
        ordering = ['received_date']  # FIFO ordering
        verbose_name = "Godown Inventory Batch"
        verbose_name_plural = "Godown Inventory Batches"
        indexes = [
            models.Index(fields=['godown', 'product', 'received_date']),
            models.Index(fields=['status', 'received_date']),
            models.Index(fields=['batch_id']),
        ]


class CrossoverRecord(BaseModel):
    """Model for direct vehicle-to-vehicle transfers with delivery challan linkage"""
    
    
    # Identification
    crossover_id = models.CharField(
        max_length=50, unique=True, editable=False,
        help_text="Auto-generated crossover identifier"
    )
    
    # Source details
    source_order_transit = models.ForeignKey(
        OrderInTransit, on_delete=models.CASCADE, related_name='crossover_records',
        help_text="Source transit order for crossover"
    )
    
    
    # Destination details
    destination_dealer = models.ForeignKey(
        'sylvia.Dealer', on_delete=models.CASCADE, related_name='crossover_deliveries',
        help_text="Dealer receiving the crossover goods"
    )
   
    
    # Product and quantity details
    product = models.ForeignKey(
        'sylvia.Product', on_delete=models.CASCADE, related_name='crossover_records'
    )
    requested_bags = models.PositiveIntegerField(
        help_text="Number of bags requested for crossover"
    )
    actual_transferred_bags = models.PositiveIntegerField(
        default=0,
        help_text="Actual bags transferred"
    )
    
    
    
    approved_date = models.DateTimeField(
        null=True, blank=True,
        help_text="When crossover was approved"
    )
   
    
   
    
    
    supervised_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='supervised_crossovers',
        help_text="User who supervised the transfer"
    )
    
    # Documentation
    crossover_notes = models.TextField(
        blank=True,
        help_text="Notes about the crossover process"
    )
    
    def save(self, *args, **kwargs):
        if not self.crossover_id:
            # Generate crossover ID: XO_YYYYMMDD_SEQUENCE
            date_str = timezone.now().strftime('%Y%m%d')
            # Simple sequence based on date
            today_count = CrossoverRecord.objects.filter(
                crossover_id__startswith=f'XO_{date_str}_'
            ).count()
            self.crossover_id = f'XO_{date_str}_{today_count + 1:03d}'
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.crossover_id} - {self.destination_dealer.name} ({self.requested_bags} bags)"
    
    class Meta:
        ordering = ['-approved_date']
        verbose_name = "Crossover Record"
        verbose_name_plural = "Crossover Records"
        indexes = [
            models.Index(fields=['destination_dealer']),
            models.Index(fields=['crossover_id']),
        ]


class LoadingRequest(BaseModel):
    """Model for outbound loading requests from stored inventory"""
    
    LOADING_STATUS_CHOICES = [
        ('REQUESTED', 'Loading Requested'),
        ('APPROVED', 'Approved for Loading'),
        ('INVENTORY_ALLOCATED', 'Inventory Allocated'),
        ('LOADING_IN_PROGRESS', 'Loading in Progress'),
        ('COMPLETED', 'Loading Completed'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    PRIORITY_CHOICES = [
        ('LOW', 'Low Priority'),
        ('MEDIUM', 'Medium Priority'),
        ('HIGH', 'High Priority'),
        ('URGENT', 'Urgent'),
    ]
    
    # Identification
    loading_request_id = models.CharField(
        max_length=50, unique=True, editable=False,
        help_text="Auto-generated loading request identifier"
    )
    
    # Core details
    godown = models.ForeignKey(
        GodownLocation, on_delete=models.CASCADE, related_name='loading_requests'
    )
    dealer = models.ForeignKey(
        'sylvia.Dealer', on_delete=models.CASCADE, related_name='loading_requests',
        help_text="Dealer for whom loading is requested"
    )
    vehicle = models.ForeignKey(
        'sylvia.Vehicle', on_delete=models.CASCADE, related_name='loading_requests',
        help_text="Vehicle to be loaded"
    )
    product = models.ForeignKey(
        'sylvia.Product', on_delete=models.CASCADE, related_name='loading_requests'
    )
    
    # Quantity details
    requested_bags = models.PositiveIntegerField(
        help_text="Number of bags requested for loading"
    )
    allocated_bags = models.PositiveIntegerField(
        default=0,
        help_text="Bags allocated from inventory (may be from multiple batches)"
    )
    loaded_bags = models.PositiveIntegerField(
        default=0,
        help_text="Actual bags loaded onto vehicle"
    )
    
    # Status and priority
    status = models.CharField(
        max_length=25, choices=LOADING_STATUS_CHOICES, default='REQUESTED'
    )
    priority = models.CharField(
        max_length=10, choices=PRIORITY_CHOICES, default='MEDIUM'
    )
    
    # Timing
    requested_date = models.DateTimeField(
        auto_now_add=True,
        help_text="When loading was requested"
    )
    required_by_date = models.DateTimeField(
        help_text="When loading must be completed by"
    )
    approved_date = models.DateTimeField(
        null=True, blank=True,
        help_text="When request was approved"
    )
    loading_start_time = models.DateTimeField(
        null=True, blank=True,
        help_text="When loading process started"
    )
    loading_completion_time = models.DateTimeField(
        null=True, blank=True,
        help_text="When loading was completed"
    )
    
    # Authorization
    requested_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='requested_loadings',
        help_text="User who made the loading request"
    )
    approved_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='approved_loadings',
        help_text="User who approved the loading request"
    )
    supervised_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='supervised_loadings',
        help_text="User who supervised the loading"
    )
    
    # Documentation
    special_instructions = models.TextField(
        blank=True,
        help_text="Special instructions for loading (handling, quality, etc.)"
    )
    loading_notes = models.TextField(
        blank=True,
        help_text="Notes about the loading process"
    )
    
    def save(self, *args, **kwargs):
        if not self.loading_request_id:
            # Generate loading request ID: LR_YYYYMMDD_SEQUENCE
            date_str = timezone.now().strftime('%Y%m%d')
            today_count = LoadingRequest.objects.filter(
                loading_request_id__startswith=f'LR_{date_str}_'
            ).count()
            self.loading_request_id = f'LR_{date_str}_{today_count + 1:04d}'
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.loading_request_id} - {self.dealer.name} ({self.requested_bags} bags)"
    
    class Meta:
        ordering = ['-requested_date']
        verbose_name = "Loading Request"
        verbose_name_plural = "Loading Requests"
        indexes = [
            models.Index(fields=['status', 'priority', 'required_by_date']),
            models.Index(fields=['dealer', 'status']),
            models.Index(fields=['godown', 'status']),
            models.Index(fields=['loading_request_id']),
        ]


class DeliveryChallan(BaseModel):
    """Unified delivery document for both crossover and independent loading operations"""
    
    CHALLAN_TYPE_CHOICES = [
        ('CROSSOVER', 'Crossover Delivery'),
        ('INDEPENDENT', 'Independent Loading'),
        ('MIXED', 'Mixed (Crossover + Loading)'),
    ]
    
    DELIVERY_STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('IN_TRANSIT', 'In Transit'),
        ('DELIVERED', 'Delivered'),
    ]
    
    # Identification
    challan_number = models.CharField(
        max_length=50, unique=True, editable=False,
        help_text="Auto-generated delivery challan number"
    )
    challan_type = models.CharField(
        max_length=15, choices=CHALLAN_TYPE_CHOICES,
        help_text="Type of delivery challan"
    )
    
    # Core details
    dealer = models.ForeignKey(
        'sylvia.Dealer', on_delete=models.CASCADE, related_name='delivery_challans',
        help_text="Dealer receiving the goods"
    )
    vehicle = models.ForeignKey(
        'sylvia.Vehicle', on_delete=models.CASCADE, related_name='delivery_challans',
        help_text="Delivery vehicle"
    )
    godown = models.ForeignKey(
        GodownLocation, on_delete=models.CASCADE, related_name='delivery_challans',
        help_text="Source godown"
    )
    
    # Linked operations (optional - for traceability)
    crossover_record = models.ForeignKey(
        CrossoverRecord, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='delivery_challans',
        help_text="Linked crossover operation (if applicable)"
    )
    loading_request = models.ForeignKey(
        LoadingRequest, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='delivery_challans',
        help_text="Linked loading request (if applicable)"
    )
    
    # Timing
    issue_date = models.DateTimeField(
        auto_now_add=True,
        help_text="When challan was issued"
    )
    
    actual_delivery_date = models.DateTimeField(
        null=True, blank=True,
        help_text="Actual delivery date and time"
    )
    
    # Status
    status = models.CharField(
        max_length=15, choices=DELIVERY_STATUS_CHOICES, default='DRAFT'
    )
    
    # Quantities (summary across all line items)
    total_bags = models.PositiveIntegerField(
        default=0,
        help_text="Total bags in this challan"
    )
    total_weight_mt = models.DecimalField(
        max_digits=10, decimal_places=3, default=0,
        help_text="Total weight in metric tons"
    )
    
    # Documentation
    delivery_address = models.TextField(
        help_text="Complete delivery address"
    )
    special_instructions = models.TextField(
        blank=True,
        help_text="Special delivery instructions"
    )
    remarks = models.TextField(
        blank=True,
        help_text="General remarks about the delivery"
    )
    
   
    
    def save(self, *args, **kwargs):
        if not self.challan_number:
            # Generate challan number: DC_GODOWN_YYYYMMDD_SEQUENCE
            date_str = timezone.now().strftime('%Y%m%d')
            today_count = DeliveryChallan.objects.filter(
                challan_number__startswith=f'DC_{self.godown.code}_{date_str}_'
            ).count()
            self.challan_number = f'DC_{self.godown.code}_{date_str}_{today_count + 1:04d}'
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.challan_number} - {self.dealer.name} ({self.total_bags} bags)"
    
    class Meta:
        ordering = ['-issue_date']
        verbose_name = "Delivery Challan"
        verbose_name_plural = "Delivery Challans"
        indexes = [
            models.Index(fields=['status', 'issue_date']),
            models.Index(fields=['dealer', 'status']),
            models.Index(fields=['challan_number']),
        ]


class DeliveryChallanItem(BaseModel):
    """Line items for delivery challans with product and quantity details"""
    
    challan = models.ForeignKey(
        DeliveryChallan, on_delete=models.CASCADE, related_name='challan_items'
    )
    product = models.ForeignKey(
        'sylvia.Product', on_delete=models.CASCADE, related_name='challan_items'
    )
    
    # Quantity details
    bags = models.PositiveIntegerField(
        help_text="Number of bags for this product"
    )
    weight_per_bag_kg = models.DecimalField(
        max_digits=6, decimal_places=2, default=50.0,
        help_text="Weight per bag in kilograms"
    )
    total_weight_mt = models.DecimalField(
        max_digits=10, decimal_places=3,
        help_text="Total weight in metric tons for this line item"
    )
    
    # Source tracking (for FIFO compliance)
    source_inventory_batches = models.ManyToManyField(
        GodownInventory, through='ChallanItemBatchMapping',
        help_text="Inventory batches used for this challan item"
    )
    
    # Quality details
    quality_notes = models.TextField(
        blank=True,
        help_text="Quality notes for this product line item"
    )
    
    def save(self, *args, **kwargs):
        # Calculate total weight in MT
        self.total_weight_mt = (self.bags * self.weight_per_bag_kg) / 1000
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.challan.challan_number} - {self.product.name}: {self.bags} bags"
    
    class Meta:
        unique_together = ['challan', 'product']
        ordering = ['product__name']


class ChallanItemBatchMapping(BaseModel):
    """Mapping table to track which inventory batches were used for challan items (FIFO compliance)"""
    
    challan_item = models.ForeignKey(
        DeliveryChallanItem, on_delete=models.CASCADE, related_name='batch_mappings'
    )
    inventory_batch = models.ForeignKey(
        GodownInventory, on_delete=models.CASCADE, related_name='challan_mappings'
    )
    bags_consumed = models.PositiveIntegerField(
        help_text="Number of bags consumed from this batch for this challan item"
    )
    
    def __str__(self):
        return f"{self.challan_item} - Batch {self.inventory_batch.batch_id}: {self.bags_consumed} bags"
    
    class Meta:
        unique_together = ['challan_item', 'inventory_batch']
        ordering = ['inventory_batch__received_date']  # FIFO ordering


class NotificationLog(BaseModel):
    """Model for tracking damage, shortage, delay alerts and notifications to teams"""
    
    NOTIFICATION_TYPES = [
        ('DAMAGE_ALERT', 'Damage Alert'),
        ('SHORTAGE_ALERT', 'Shortage Alert'),
        ('EXCESS_ALERT', 'Excess Alert'),
        ('DELAY_ALERT', 'Delay Alert'),
        ('QUALITY_ALERT', 'Quality Alert'),
        ('INVENTORY_LOW', 'Low Inventory Alert'),
        ('CROSSOVER_URGENT', 'Urgent Crossover Required'),
        ('LOADING_DELAY', 'Loading Delay Alert'),
        ('VEHICLE_WAITING', 'Vehicle Waiting Alert'),
    ]
    
    SEVERITY_LEVELS = [
        ('INFO', 'Information'),
        ('WARNING', 'Warning'),
        ('ERROR', 'Error'),
        ('CRITICAL', 'Critical'),
    ]
    
    NOTIFICATION_STATUS = [
        ('SENT', 'Notification Sent'),
        ('ACKNOWLEDGED', 'Acknowledged'),
        ('RESOLVED', 'Issue Resolved'),
        ('DISMISSED', 'Dismissed'),
        ('FAILED', 'Failed to Send'),
    ]
    
    # Core identification
    notification_type = models.CharField(
        max_length=20, choices=NOTIFICATION_TYPES,
        help_text="Type of notification/alert"
    )
    severity = models.CharField(
        max_length=10, choices=SEVERITY_LEVELS,
        help_text="Severity level of the notification"
    )
    status = models.CharField(
        max_length=15, choices=NOTIFICATION_STATUS, default='SENT'
    )
    
    # Content
    title = models.CharField(
        max_length=200,
        help_text="Short title/summary of the notification"
    )
    message = models.TextField(
        help_text="Detailed notification message"
    )
    
    # Context links (optional - depending on notification type)
    order_in_transit = models.ForeignKey(
        OrderInTransit, on_delete=models.CASCADE, null=True, blank=True,
        related_name='notifications',
        help_text="Related transit order (if applicable)"
    )
    inventory_batch = models.ForeignKey(
        GodownInventory, on_delete=models.CASCADE, null=True, blank=True,
        related_name='notifications',
        help_text="Related inventory batch (if applicable)"
    )
    loading_request = models.ForeignKey(
        LoadingRequest, on_delete=models.CASCADE, null=True, blank=True,
        related_name='notifications',
        help_text="Related loading request (if applicable)"
    )
    crossover_record = models.ForeignKey(
        CrossoverRecord, on_delete=models.CASCADE, null=True, blank=True,
        related_name='notifications',
        help_text="Related crossover record (if applicable)"
    )
    
    # Recipients
    notified_users = models.ManyToManyField(
        User, through='NotificationRecipient',
        through_fields=('notification', 'user'),
        help_text="Users who received this notification"
    )
    
    # Timing
    sent_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When notification was sent"
    )
    acknowledged_at = models.DateTimeField(
        null=True, blank=True,
        help_text="When notification was acknowledged"
    )
    resolved_at = models.DateTimeField(
        null=True, blank=True,
        help_text="When underlying issue was resolved"
    )
    
    # Additional data
    metadata = models.JSONField(
        default=dict, blank=True,
        help_text="Additional structured data related to the notification"
    )
    
    def __str__(self):
        return f"{self.notification_type} - {self.title}"
    
    class Meta:
        ordering = ['-sent_at']
        verbose_name = "Notification Log"
        verbose_name_plural = "Notification Logs"
        indexes = [
            models.Index(fields=['notification_type', 'severity', 'sent_at']),
            models.Index(fields=['status', 'sent_at']),
        ]


class NotificationRecipient(BaseModel):
    """Through model for tracking notification recipients and their responses"""
    
    DELIVERY_STATUS_CHOICES = [
        ('PENDING', 'Pending Delivery'),
        ('DELIVERED', 'Delivered'),
        ('READ', 'Read by Recipient'),
        ('ACKNOWLEDGED', 'Acknowledged'),
        ('FAILED', 'Delivery Failed'),
    ]
    
    notification = models.ForeignKey(
        NotificationLog, on_delete=models.CASCADE, related_name='recipient_records'
    )
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='notification_receipts'
    )
    
    delivery_status = models.CharField(
        max_length=15, choices=DELIVERY_STATUS_CHOICES, default='PENDING'
    )
    
    # Timing
    delivered_at = models.DateTimeField(
        null=True, blank=True,
        help_text="When notification was delivered to user"
    )
    read_at = models.DateTimeField(
        null=True, blank=True,
        help_text="When user read the notification"
    )
    acknowledged_at = models.DateTimeField(
        null=True, blank=True,
        help_text="When user acknowledged the notification"
    )
    
    # Delivery details
    delivery_channel = models.CharField(
        max_length=20, choices=[
            ('EMAIL', 'Email'),
            ('SMS', 'SMS'),
            ('WHATSAPP', 'WhatsApp'),
            ('IN_APP', 'In-App Notification'),
            ('PUSH', 'Push Notification'),
        ], default='IN_APP'
    )
    delivery_address = models.CharField(
        max_length=200, blank=True,
        help_text="Email address, phone number, etc. used for delivery"
    )
    
    def __str__(self):
        return f"{self.notification} -> {self.user.username} ({self.delivery_status})"
    
    class Meta:
        unique_together = ['notification', 'user']
        ordering = ['-created_at']
