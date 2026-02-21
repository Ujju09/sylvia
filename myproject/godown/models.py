from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from .managers import GodownTenantManager


class BaseModel(models.Model):
    """Base model with common fields"""
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_%(class)s_records')

    class Meta:
        abstract = True


class GodownTenantBaseModel(models.Model):
    """
    Base model with tenant isolation for the godown app.

    Reuses sylvia.Organization for multi-tenancy. The organization is auto-assigned
    from the thread-local context set by sylvia.middleware.TenantMiddleware.
    """
    organization = models.ForeignKey(
        'sylvia.Organization',
        on_delete=models.PROTECT,
        help_text="Organization this record belongs to"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_%(class)s_records'
    )

    objects = GodownTenantManager()
    all_objects = models.Manager()

    class Meta:
        abstract = True
        indexes = [
            models.Index(fields=['organization', '-created_at']),
        ]

    def save(self, *args, **kwargs):
        if not self.pk and getattr(self, 'organization_id', None) is None:
            from sylvia.middleware import get_current_organization
            current_org = get_current_organization()
            if current_org:
                self.organization = current_org
        super().save(*args, **kwargs)


class GodownLocation(GodownTenantBaseModel):
    """Model for godown/warehouse locations"""
    name = models.CharField(max_length=200, help_text="Name of the godown/warehouse")
    code = models.CharField(max_length=20, help_text="Unique code for the godown (unique within organization)")
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
        unique_together = [('organization', 'code')]


class OrderInTransit(GodownTenantBaseModel):
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
        max_length=15,
        help_text="E-way bill number for the shipment (unique within organization)"
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
    crossover_dealer = models.ForeignKey(
        'sylvia.Dealer', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='incoming_crossovers',
        help_text="Dealer who will receive the crossover goods"
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
        unique_together = [('organization', 'eway_bill_number')]
        indexes = [
            models.Index(fields=['eway_bill_number']),
            models.Index(fields=['status', 'actual_arrival_date']),
            models.Index(fields=['godown', 'status']),
        ]


class GodownInventory(GodownTenantBaseModel):
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
        max_length=50, editable=False,
        help_text="Auto-generated FIFO batch identifier (unique within organization)"
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
        unique_together = [('organization', 'batch_id')]
        indexes = [
            models.Index(fields=['godown', 'product', 'received_date']),
            models.Index(fields=['status', 'received_date']),
            models.Index(fields=['batch_id']),
        ]


class CrossoverRecord(GodownTenantBaseModel):
    """Model for direct vehicle-to-vehicle transfers with delivery challan linkage"""
    
    
    # Identification
    crossover_id = models.CharField(
        max_length=50, editable=False,
        help_text="Auto-generated crossover identifier (unique within organization)"
    )
    
    # Source details
    source_order_transit = models.ForeignKey(
        OrderInTransit, on_delete=models.CASCADE, related_name='crossover_records',
        help_text="Source transit order for crossover"
    )
    
    
    # Destination details
    destination_dealer = models.ForeignKey(
        'sylvia.Dealer', on_delete=models.CASCADE, related_name='crossover_deliveries',
        help_text="Dealer receiving the crossover goods", blank=True,null=True
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
        unique_together = [('organization', 'crossover_id')]
        indexes = [
            models.Index(fields=['destination_dealer']),
            models.Index(fields=['crossover_id']),
        ]


class LoadingRequest(GodownTenantBaseModel):
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
        max_length=50, editable=False,
        help_text="Auto-generated loading request identifier (unique within organization)"
    )

    # Core details
    godown = models.ForeignKey(
        GodownLocation, on_delete=models.CASCADE, related_name='loading_requests'
    )
    dealer = models.ForeignKey(
        'sylvia.Dealer', on_delete=models.CASCADE, related_name='loading_requests',
        help_text="Dealer for whom loading is requested"
    )

    product = models.ForeignKey(
        'sylvia.Product', on_delete=models.CASCADE, related_name='loading_requests'
    )

    # Quantity details
    requested_bags = models.PositiveIntegerField(
        help_text="Number of bags requested for loading"
    )

    loaded_bags = models.PositiveIntegerField(
        default=0,
        help_text="Actual bags loaded onto vehicle"
    )

    # Status and priority
    # status = models.CharField(
    #     max_length=25, choices=LOADING_STATUS_CHOICES, default='REQUESTED'
    # )
    # priority = models.CharField(
    #     max_length=10, choices=PRIORITY_CHOICES, default='MEDIUM'
    # )

    # Timing
    # requested_date = models.DateTimeField(
    #     auto_now_add=True,
    #     help_text="When loading was requested"
    # )
    # required_by_date = models.DateTimeField(
    #     help_text="When loading must be completed by"
    # )
    # approved_date = models.DateTimeField(
    #     null=True, blank=True,
    #     help_text="When request was approved"
    # )
    # loading_start_time = models.DateTimeField(
    #     null=True, blank=True,
    #     help_text="When loading process started"
    # )
    # loading_completion_time = models.DateTimeField(
    #     null=True, blank=True,
    #     help_text="When loading was completed"
    # )

    # Authorization
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
        ordering = ['-created_at']
        verbose_name = "Loading Records"
        verbose_name_plural = "Loading Records"
        unique_together = [('organization', 'loading_request_id')]
        indexes = [
            models.Index(fields=['dealer']),
            models.Index(fields=['godown']),
            models.Index(fields=['loading_request_id']),
        ]


class LoadingRequestImage(GodownTenantBaseModel):
    """Model to store proof images for loading requests"""

    LOADING_IMAGE_TYPE_CHOICES = [
        ('LOADING_PROOF', 'Loading Proof Document'),
        ('TRUCK_PHOTO', 'Truck/Vehicle Photo'),
        ('QUALITY_CHECK', 'Quality Check Photo'),
        ('BAG_COUNT', 'Bag Count Verification'),
        ('OTHER', 'Other Documentation'),
    ]

    loading_request = models.ForeignKey(
        LoadingRequest, on_delete=models.CASCADE, related_name='loading_images'
    )
    image_url = models.URLField(
        max_length=500, help_text="Krutrim Storage URL for the image"
    )
    image_type = models.CharField(
        max_length=20, choices=LOADING_IMAGE_TYPE_CHOICES, default='LOADING_PROOF'
    )
    original_filename = models.CharField(max_length=255, blank=True)
    file_size = models.PositiveIntegerField(
        null=True, blank=True, help_text="File size in bytes"
    )
    upload_timestamp = models.DateTimeField(auto_now_add=True)
    description = models.TextField(
        blank=True, help_text="Optional description of the image"
    )
    is_primary = models.BooleanField(
        default=False, help_text="Mark as primary loading proof image"
    )

    # Storage metadata
    storage_key = models.CharField(
        max_length=255, blank=True, help_text="Krutrim storage key/path"
    )
    content_type = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return f"{self.loading_request.loading_request_id} - {self.get_image_type_display()}"

    def save(self, *args, **kwargs):
        # Ensure only one primary image per loading request
        if self.is_primary:
            LoadingRequestImage.objects.filter(
                loading_request=self.loading_request, is_primary=True
            ).update(is_primary=False)
        super().save(*args, **kwargs)

    class Meta:
        ordering = ['-upload_timestamp']
        verbose_name = "Loading Request Image"
        verbose_name_plural = "Loading Request Images"
        indexes = [
            models.Index(fields=['loading_request', '-upload_timestamp']),
            models.Index(fields=['image_type', 'is_primary']),
        ]


class DeliveryChallan(GodownTenantBaseModel):
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
        max_length=50, editable=False,
        help_text="Auto-generated delivery challan number (unique within organization)"
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
        unique_together = [('organization', 'challan_number')]
        indexes = [
            models.Index(fields=['status', 'issue_date']),
            models.Index(fields=['dealer', 'status']),
            models.Index(fields=['challan_number']),
        ]


class DeliveryChallanItem(GodownTenantBaseModel):
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


class ChallanItemBatchMapping(GodownTenantBaseModel):
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


class NotificationLog(GodownTenantBaseModel):
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


class NotificationRecipient(GodownTenantBaseModel):
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


class GodownInventoryLedger(GodownTenantBaseModel):
    """
    Complete transaction-based inventory ledger for audit compliance and real-time stock tracking.
    Records every inward and outward movement with full traceability.
    """
    
    TRANSACTION_TYPES = [
        ('INWARD_RECEIPT', 'Stock Receipt from Transit'),
        ('INWARD_ADJUSTMENT', 'Manual Stock Addition'),
        ('INWARD_RETURN', 'Returned Stock'),
        ('INWARD_OPENING', 'Opening Balance Entry'),
        ('OUTWARD_LOADING', 'Loading Request Fulfillment'),
        ('OUTWARD_CROSSOVER', 'Crossover Transfer'),
        ('OUTWARD_DAMAGE', 'Damage/Waste Writeoff'),
        ('OUTWARD_ADJUSTMENT', 'Manual Stock Reduction'),
        ('OUTWARD_CLOSING', 'Closing Balance Entry'),
        ('BALANCE_ADJUSTMENT', 'System Balance Correction'),
    ]
    
    ENTRY_STATUS_CHOICES = [
        ('PENDING', 'Pending Confirmation'),
        ('CONFIRMED', 'Confirmed Entry'),
        ('CANCELLED', 'Cancelled Entry'),
        ('SYSTEM_GENERATED', 'System Generated'),
    ]
    
    # Core identification and classification
    transaction_id = models.CharField(
        max_length=50, editable=False,
        help_text="Auto-generated unique transaction identifier (unique within organization)"
    )
    transaction_type = models.CharField(
        max_length=20, choices=TRANSACTION_TYPES,
        help_text="Type of inventory transaction"
    )
    transaction_date = models.DateTimeField(
        default=timezone.now,
        help_text="When the transaction occurred"
    )
    entry_status = models.CharField(
        max_length=20, choices=ENTRY_STATUS_CHOICES, default='PENDING'
    )
    
    # Location and product details
    godown = models.ForeignKey(
        GodownLocation, on_delete=models.CASCADE, related_name='ledger_entries'
    )
    product = models.ForeignKey(
        'sylvia.Product', on_delete=models.CASCADE, related_name='ledger_entries'
    )
    
    # Quantity tracking
    inward_quantity = models.PositiveIntegerField(
        default=0,
        help_text="Bags added to inventory (positive quantity)"
    )
    outward_quantity = models.PositiveIntegerField(
        default=0,
        help_text="Bags removed from inventory (positive quantity)"
    )
    balance_after_transaction = models.IntegerField(
        help_text="Calculated balance after this transaction"
    )
    
    # Source document tracking for complete audit trail
    source_order_transit = models.ForeignKey(
        OrderInTransit, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='ledger_entries',
        help_text="Source transit order (for INWARD_RECEIPT)"
    )
    source_loading_request = models.ForeignKey(
        LoadingRequest, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='ledger_entries',
        help_text="Source loading request (for OUTWARD_LOADING)"
    )
    source_crossover = models.ForeignKey(
        CrossoverRecord, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='ledger_entries',
        help_text="Source crossover record (for OUTWARD_CROSSOVER)"
    )
    source_challan = models.ForeignKey(
        DeliveryChallan, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='ledger_entries',
        help_text="Source delivery challan"
    )
    
    # FIFO batch tracking
    affected_inventory_batches = models.ManyToManyField(
        GodownInventory, through='LedgerBatchMapping',
        help_text="Inventory batches affected by this transaction"
    )
    
    # Quality and condition tracking
    quality_notes = models.TextField(
        blank=True,
        help_text="Quality observations or notes about the stock"
    )
    condition_at_transaction = models.CharField(
        max_length=20, choices=[
            ('GOOD', 'Good Condition'),
            ('DAMAGED', 'Damaged'),
            ('EXPIRED', 'Expired/Old'),
            ('MIXED', 'Mixed Condition'),
        ], default='GOOD'
    )
    
    # Authorization and approval
    authorized_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='authorized_ledger_entries',
        help_text="User who authorized this transaction"
    )
    approval_required = models.BooleanField(
        default=False,
        help_text="Whether this transaction requires approval"
    )
    approved_at = models.DateTimeField(
        null=True, blank=True,
        help_text="When transaction was approved"
    )
    
    # Documentation and notes
    reference_document = models.CharField(
        max_length=100, blank=True,
        help_text="Reference document number (challan, receipt, etc.)"
    )
    transaction_notes = models.TextField(
        blank=True,
        help_text="Detailed notes about this transaction"
    )
    
    # System tracking
    is_system_generated = models.BooleanField(
        default=False,
        help_text="Whether this entry was auto-generated by the system"
    )
    parent_transaction = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True,
        help_text="Parent transaction (for adjustment entries)"
    )
    
    def save(self, *args, **kwargs):
        if not self.transaction_id:
            # Generate transaction ID: TXN_GODOWN_YYYYMMDD_HHMMSS_SEQUENCE
            timestamp = timezone.now()
            date_str = timestamp.strftime('%Y%m%d')
            time_str = timestamp.strftime('%H%M%S')
            
            # Get count of transactions for this godown today
            today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
            today_count = GodownInventoryLedger.objects.filter(
                godown=self.godown,
                created_at__gte=today_start,
                transaction_id__startswith=f'TXN_{self.godown.code}_{date_str}_'
            ).count()
            
            self.transaction_id = f'TXN_{self.godown.code}_{date_str}_{time_str}_{today_count + 1:03d}'
        
        # Validate quantity logic
        if self.inward_quantity > 0 and self.outward_quantity > 0:
            raise ValueError("Transaction cannot have both inward and outward quantities")
        if self.inward_quantity == 0 and self.outward_quantity == 0:
            if self.transaction_type not in ['INWARD_OPENING', 'OUTWARD_CLOSING']:
                raise ValueError("Transaction must have either inward or outward quantity")
        
        # Set entry status for system-generated entries
        if self.is_system_generated and self.entry_status == 'PENDING':
            self.entry_status = 'SYSTEM_GENERATED'
        
        super().save(*args, **kwargs)
    
    def get_net_quantity(self):
        """Get net quantity change (positive for inward, negative for outward)"""
        return self.inward_quantity - self.outward_quantity
    
    def is_inward_transaction(self):
        """Check if this is an inward transaction"""
        return self.inward_quantity > 0
    
    def is_outward_transaction(self):
        """Check if this is an outward transaction"""
        return self.outward_quantity > 0
    
    def __str__(self):
        direction = "IN" if self.is_inward_transaction() else "OUT"
        quantity = self.inward_quantity or self.outward_quantity
        return f"{self.transaction_id} - {direction}: {quantity} bags - {self.product.code}"
    
    class Meta:
        ordering = ['-transaction_date', '-created_at']
        verbose_name = "Godown Inventory Ledger Entry"
        verbose_name_plural = "Godown Inventory Ledger Entries"
        unique_together = [('organization', 'transaction_id')]
        indexes = [
            models.Index(fields=['godown', 'product', '-transaction_date']),
            models.Index(fields=['transaction_type', '-transaction_date']),
            models.Index(fields=['entry_status', '-transaction_date']),
            models.Index(fields=['transaction_id']),
            models.Index(fields=['is_system_generated', '-transaction_date']),
        ]


class LedgerBatchMapping(GodownTenantBaseModel):
    """
    Mapping table to track which inventory batches were affected by ledger transactions.
    Essential for FIFO compliance and batch traceability.
    """
    
    ledger_entry = models.ForeignKey(
        GodownInventoryLedger, on_delete=models.CASCADE, related_name='batch_mappings'
    )
    inventory_batch = models.ForeignKey(
        GodownInventory, on_delete=models.CASCADE, related_name='ledger_mappings'
    )
    quantity_affected = models.PositiveIntegerField(
        help_text="Number of bags affected in this batch for this transaction"
    )
    
    # Batch state tracking
    batch_balance_before = models.PositiveIntegerField(
        help_text="Batch balance before this transaction"
    )
    batch_balance_after = models.PositiveIntegerField(
        help_text="Batch balance after this transaction"
    )
    
    def __str__(self):
        return f"{self.ledger_entry.transaction_id} -> Batch {self.inventory_batch.batch_id}: {self.quantity_affected} bags"
    
    class Meta:
        unique_together = ['ledger_entry', 'inventory_batch']
        ordering = ['inventory_batch__received_date']  # FIFO ordering


class GodownDailyBalance(GodownTenantBaseModel):
    """
    Daily balance snapshots for each godown-product combination.
    Provides fast lookups for current stock levels and historical balance tracking.
    """
    
    BALANCE_STATUS_CHOICES = [
        ('CALCULATED', 'System Calculated'),
        ('VERIFIED', 'Manually Verified'),
        ('DISCREPANCY', 'Discrepancy Identified'),
        ('ADJUSTED', 'Balance Adjusted'),
    ]
    
    # Core identification
    balance_date = models.DateField(
        help_text="Date for which this balance is calculated"
    )
    godown = models.ForeignKey(
        GodownLocation, on_delete=models.CASCADE, related_name='daily_balances'
    )
    product = models.ForeignKey(
        'sylvia.Product', on_delete=models.CASCADE, related_name='daily_balances'
    )
    
    # Balance calculations
    opening_balance = models.IntegerField(
        default=0,
        help_text="Opening balance at start of day"
    )
    total_inward = models.PositiveIntegerField(
        default=0,
        help_text="Total inward movements during the day"
    )
    total_outward = models.PositiveIntegerField(
        default=0,
        help_text="Total outward movements during the day"
    )
    closing_balance = models.IntegerField(
        help_text="Calculated closing balance (opening + inward - outward)"
    )
    
    # Physical verification (if conducted)
    physical_count = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="Actual physical count (if verification was done)"
    )
    count_verified_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='verified_balances',
        help_text="User who conducted physical verification"
    )
    count_verification_date = models.DateTimeField(
        null=True, blank=True,
        help_text="When physical verification was conducted"
    )
    
    # Status and variance tracking
    balance_status = models.CharField(
        max_length=15, choices=BALANCE_STATUS_CHOICES, default='CALCULATED'
    )
    variance_quantity = models.IntegerField(
        default=0,
        help_text="Difference between calculated and physical count (+ = excess, - = shortage)"
    )
    
    # Batch-wise breakdown (for detailed analysis)
    active_batches_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of active inventory batches"
    )
    oldest_batch_age_days = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="Age of oldest active batch in days"
    )
    
    # Quality assessment
    good_condition_bags = models.PositiveIntegerField(
        default=0,
        help_text="Bags in good condition"
    )
    damaged_bags = models.PositiveIntegerField(
        default=0,
        help_text="Damaged bags count"
    )
    expired_bags = models.PositiveIntegerField(
        default=0,
        help_text="Expired/aged bags count"
    )
    
    # System calculations metadata
    calculation_timestamp = models.DateTimeField(
        auto_now_add=True,
        help_text="When this balance was calculated"
    )
    last_transaction_id = models.CharField(
        max_length=50, blank=True,
        help_text="Last transaction ID included in this calculation"
    )
    is_auto_calculated = models.BooleanField(
        default=True,
        help_text="Whether this balance was auto-calculated by system"
    )
    
    # Notes and remarks
    verification_notes = models.TextField(
        blank=True,
        help_text="Notes from physical verification or balance review"
    )
    discrepancy_reason = models.TextField(
        blank=True,
        help_text="Reason for discrepancy (if identified)"
    )
    
    def save(self, *args, **kwargs):
        # Calculate closing balance
        self.closing_balance = self.opening_balance + self.total_inward - self.total_outward
        
        # Calculate variance if physical count exists
        if self.physical_count is not None:
            self.variance_quantity = self.physical_count - self.closing_balance
            if self.variance_quantity != 0:
                self.balance_status = 'DISCREPANCY'
            else:
                self.balance_status = 'VERIFIED'
        
        super().save(*args, **kwargs)
    
    def has_variance(self):
        """Check if there's a variance between calculated and physical count"""
        return self.variance_quantity != 0 and self.physical_count is not None
    
    def get_variance_percentage(self):
        """Calculate variance as percentage of calculated balance"""
        if self.closing_balance == 0:
            return 0
        return (self.variance_quantity / abs(self.closing_balance)) * 100
    
    def is_shortage(self):
        """Check if there's a shortage (negative variance)"""
        return self.variance_quantity < 0
    
    def is_excess(self):
        """Check if there's excess stock (positive variance)"""
        return self.variance_quantity > 0
    
    def __str__(self):
        return f"{self.godown.code} - {self.product.code} - {self.balance_date}: {self.closing_balance} bags"
    
    @classmethod
    def get_current_balance(cls, godown, product):
        """Get the most recent calculated balance for a godown-product combination"""
        try:
            latest_balance = cls.objects.filter(
                godown=godown,
                product=product
            ).latest('balance_date')
            return latest_balance.closing_balance
        except cls.DoesNotExist:
            return 0
    
    @classmethod
    def calculate_balance_from_ledger(cls, godown, product, date):
        """Calculate balance for a specific date from ledger entries"""
        from django.db.models import Sum
        
        # Get all confirmed ledger entries up to the specified date
        ledger_entries = GodownInventoryLedger.objects.filter(
            godown=godown,
            product=product,
            transaction_date__date__lte=date,
            entry_status='CONFIRMED'
        )
        
        # Calculate total inward and outward quantities
        aggregates = ledger_entries.aggregate(
            total_inward=Sum('inward_quantity') or 0,
            total_outward=Sum('outward_quantity') or 0
        )
        
        balance = aggregates['total_inward'] - aggregates['total_outward']
        
        return {
            'balance': balance,
            'total_inward': aggregates['total_inward'],
            'total_outward': aggregates['total_outward']
        }
    
    class Meta:
        unique_together = ['balance_date', 'godown', 'product']
        ordering = ['-balance_date', 'godown__name', 'product__name']
        verbose_name = "Godown Daily Balance"
        verbose_name_plural = "Godown Daily Balances"
        indexes = [
            models.Index(fields=['balance_date', 'godown', 'product']),
            models.Index(fields=['godown', 'product', '-balance_date']),
            models.Index(fields=['balance_status', '-balance_date']),
            models.Index(fields=['-balance_date']),
        ]


class InventoryVariance(GodownTenantBaseModel):
    """
    Model to track and analyze inventory discrepancies requiring investigation.
    Helps maintain audit trail for all stock variances and their resolution.
    """
    
    VARIANCE_TYPES = [
        ('SHORTAGE', 'Stock Shortage'),
        ('EXCESS', 'Excess Stock'),
        ('QUALITY_ISSUE', 'Quality Degradation'),
        ('SYSTEM_ERROR', 'System Calculation Error'),
        ('THEFT_SUSPECTED', 'Suspected Theft'),
        ('DAMAGE_UNREPORTED', 'Unreported Damage'),
        ('COUNTING_ERROR', 'Physical Counting Error'),
        ('DATA_ENTRY_ERROR', 'Data Entry Mistake'),
    ]
    
    VARIANCE_STATUS = [
        ('IDENTIFIED', 'Variance Identified'),
        ('INVESTIGATING', 'Under Investigation'),
        ('ROOT_CAUSE_FOUND', 'Root Cause Identified'),
        ('RESOLVED', 'Resolved'),
        ('WRITTEN_OFF', 'Written Off'),
        ('DISMISSED', 'Dismissed as Non-Issue'),
    ]
    
    PRIORITY_LEVELS = [
        ('LOW', 'Low Priority'),
        ('MEDIUM', 'Medium Priority'),
        ('HIGH', 'High Priority'),
        ('CRITICAL', 'Critical - Immediate Action Required'),
    ]
    
    # Core identification
    variance_id = models.CharField(
        max_length=50, editable=False,
        help_text="Auto-generated variance identifier (unique within organization)"
    )
    
    # Source information
    godown = models.ForeignKey(
        GodownLocation, on_delete=models.CASCADE, related_name='inventory_variances'
    )
    product = models.ForeignKey(
        'sylvia.Product', on_delete=models.CASCADE, related_name='inventory_variances'
    )
    
    # Linked to daily balance (if applicable)
    related_daily_balance = models.ForeignKey(
        GodownDailyBalance, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='variances',
        help_text="Daily balance record that identified this variance"
    )
    
    # Variance details
    variance_type = models.CharField(max_length=20, choices=VARIANCE_TYPES)
    variance_date = models.DateField(
        help_text="Date when variance was first identified"
    )
    expected_quantity = models.PositiveIntegerField(
        help_text="Expected/calculated quantity"
    )
    actual_quantity = models.PositiveIntegerField(
        help_text="Actual/physical quantity found"
    )
    variance_quantity = models.IntegerField(
        help_text="Difference (actual - expected)"
    )
    
    # Financial impact
    estimated_value_impact = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        help_text="Estimated financial value of variance"
    )
    
    # Status and priority
    status = models.CharField(max_length=20, choices=VARIANCE_STATUS, default='IDENTIFIED')
    priority_level = models.CharField(max_length=10, choices=PRIORITY_LEVELS, default='MEDIUM')
    
    # Investigation details
    investigation_started_at = models.DateTimeField(
        null=True, blank=True,
        help_text="When investigation was started"
    )
    investigated_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='investigated_variances',
        help_text="User conducting the investigation"
    )
    investigation_notes = models.TextField(
        blank=True,
        help_text="Detailed investigation findings and notes"
    )
    
    # Root cause analysis
    root_cause = models.TextField(
        blank=True,
        help_text="Identified root cause of the variance"
    )
    root_cause_identified_at = models.DateTimeField(
        null=True, blank=True,
        help_text="When root cause was identified"
    )
    
    # Resolution
    resolution_action = models.TextField(
        blank=True,
        help_text="Action taken to resolve the variance"
    )
    resolved_at = models.DateTimeField(
        null=True, blank=True,
        help_text="When variance was resolved"
    )
    resolved_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='resolved_variances',
        help_text="User who resolved the variance"
    )
    
    # Corrective measures
    preventive_measures = models.TextField(
        blank=True,
        help_text="Measures implemented to prevent similar variances"
    )
    
    # System integration
    adjustment_ledger_entry = models.ForeignKey(
        GodownInventoryLedger, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='variance_adjustments',
        help_text="Ledger entry created to adjust for this variance"
    )
    
    # Escalation tracking
    escalated_to = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='escalated_variances',
        help_text="User to whom variance was escalated"
    )
    escalated_at = models.DateTimeField(
        null=True, blank=True,
        help_text="When variance was escalated"
    )
    
    def save(self, *args, **kwargs):
        if not self.variance_id:
            # Generate variance ID: VAR_GODOWN_YYYYMMDD_SEQUENCE
            date_str = timezone.now().strftime('%Y%m%d')
            today_count = InventoryVariance.objects.filter(
                variance_id__startswith=f'VAR_{self.godown.code}_{date_str}_'
            ).count()
            self.variance_id = f'VAR_{self.godown.code}_{date_str}_{today_count + 1:03d}'
        
        # Calculate variance quantity
        self.variance_quantity = self.actual_quantity - self.expected_quantity
        
        # Auto-set priority based on variance magnitude
        if abs(self.variance_quantity) > 100:  # More than 100 bags
            self.priority_level = 'HIGH'
        elif abs(self.variance_quantity) > 50:   # 50-100 bags
            self.priority_level = 'MEDIUM'
        else:  # Less than 50 bags
            self.priority_level = 'LOW'
        
        # Set investigation start time when status changes to investigating
        if self.status == 'INVESTIGATING' and not self.investigation_started_at:
            self.investigation_started_at = timezone.now()
        
        # Set resolution time when status changes to resolved
        if self.status in ['RESOLVED', 'WRITTEN_OFF', 'DISMISSED'] and not self.resolved_at:
            self.resolved_at = timezone.now()
        
        super().save(*args, **kwargs)
    
    def is_shortage(self):
        """Check if this is a shortage variance"""
        return self.variance_quantity < 0
    
    def is_excess(self):
        """Check if this is an excess variance"""
        return self.variance_quantity > 0
    
    def get_variance_percentage(self):
        """Calculate variance as percentage of expected quantity"""
        if self.expected_quantity == 0:
            return 0
        return (abs(self.variance_quantity) / self.expected_quantity) * 100
    
    def get_resolution_time_days(self):
        """Calculate days taken to resolve the variance"""
        if self.resolved_at and self.created_at:
            return (self.resolved_at - self.created_at).days
        return None
    
    def is_overdue_investigation(self, threshold_days=7):
        """Check if investigation is overdue (default 7 days)"""
        if self.status in ['RESOLVED', 'WRITTEN_OFF', 'DISMISSED']:
            return False
        
        days_since_creation = (timezone.now() - self.created_at).days
        return days_since_creation > threshold_days
    
    def __str__(self):
        direction = "Shortage" if self.is_shortage() else "Excess"
        return f"{self.variance_id} - {direction}: {abs(self.variance_quantity)} bags - {self.product.code}"
    
    class Meta:
        ordering = ['-variance_date', '-created_at']
        verbose_name = "Inventory Variance"
        verbose_name_plural = "Inventory Variances"
        unique_together = [('organization', 'variance_id')]
        indexes = [
            models.Index(fields=['variance_id']),
            models.Index(fields=['godown', 'product', '-variance_date']),
            models.Index(fields=['status', 'priority_level', '-variance_date']),
            models.Index(fields=['variance_type', '-variance_date']),
            models.Index(fields=['-variance_date']),
        ]
