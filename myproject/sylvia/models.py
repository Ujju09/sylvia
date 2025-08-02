from django.db import models
from django.contrib.auth.models import User
from django.core.validators import RegexValidator
from django.utils import timezone
from decimal import Decimal
import uuid

class BaseModel(models.Model):
    """Base model with common fields"""
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        abstract = True

class Depot(BaseModel):
    """Model for depot/warehouse locations"""
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=10, unique=True)
    address = models.TextField(blank=True)
    city = models.CharField(max_length=50)
    state = models.CharField(max_length=50)
    pincode = models.CharField(max_length=6, blank=True)
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return f"{self.name} ({self.code})"
    
    class Meta:
        ordering = ['name']

class Product(BaseModel):
    """Model for products/materials"""
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=20, unique=True)
    description = models.TextField(blank=True)
    unit = models.CharField(max_length=20, default='MT')  # Metric Ton
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return f"{self.name} ({self.code})"
    
    class Meta:
        ordering = ['name']

class Dealer(BaseModel):
    """Model for dealers/customers"""
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=20, unique=True)
    contact_person = models.CharField(max_length=100, blank=True)
    phone = models.CharField(max_length=15, validators=[
        RegexValidator(regex=r'^\+?1?\d{9,15}$', message="Enter a valid phone number.")
    ])
    whatsapp_number = models.CharField(max_length=15, blank=True, validators=[
        RegexValidator(regex=r'^\+?1?\d{9,15}$', message="Enter a valid WhatsApp number.")
    ])
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    city = models.CharField(max_length=50, blank=True)
    state = models.CharField(max_length=50, blank=True)
    pincode = models.CharField(max_length=6, blank=True)
    gstin = models.CharField(max_length=15, blank=True, unique=True, null=True)
    is_active = models.BooleanField(default=True)
    
    # Business relationship fields
    credit_limit = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    credit_days = models.IntegerField(default=0)
    
    def __str__(self):
        return f"{self.name} ({self.code})"
    
    def get_whatsapp_number(self):
        """Return WhatsApp number or phone number for messaging"""
        return self.whatsapp_number if self.whatsapp_number else self.phone
    
    class Meta:
        ordering = ['name']

class Vehicle(BaseModel):
    """Model for vehicles/trucks"""
    truck_number = models.CharField(max_length=20, unique=True, validators=[
        RegexValidator(
            regex=r'^[A-Z]{2}\d{2}[A-Z]{1,2}\d{4}$',
            message="Enter a valid truck number (e.g., CG15EA0464)"
        )
    ])
    owner_name = models.CharField(max_length=100, blank=True)
    driver_name = models.CharField(max_length=100, blank=True)
    driver_phone = models.CharField(max_length=15, blank=True)
    capacity = models.DecimalField(max_digits=6, decimal_places=2, default=0)  # in MT
    vehicle_type = models.CharField(max_length=50, choices=[
        ('TRUCK', 'Truck'),
        ('TRAILER', 'Trailer'),
        ('CONTAINER', 'Container'),
        ('OTHER', 'Other')
    ], default='TRUCK')
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return self.truck_number
    
    class Meta:
        ordering = ['truck_number']

class Order(BaseModel):
    """Main order model"""
    ORDER_STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('CONFIRMED', 'Confirmed'),
        ('MRN_CREATED', 'MRN Created'),
        ('BILLED', 'Billed'),
    ]
    
    order_number = models.CharField(max_length=20, unique=True, editable=False)
    dealer = models.ForeignKey(Dealer, on_delete=models.CASCADE, related_name='orders')
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, related_name='orders')
    depot = models.ForeignKey(Depot, on_delete=models.CASCADE, related_name='orders')
    
    # Dates
    order_date = models.DateTimeField(default=timezone.now)
    mrn_date = models.DateField(null=True, blank=True)
    bill_date = models.DateField(null=True, blank=True)
    dispatch_date = models.DateTimeField(null=True, blank=True)
    delivery_date = models.DateTimeField(null=True, blank=True)
    
    # Status and tracking
    status = models.CharField(max_length=20, choices=ORDER_STATUS_CHOICES, default='PENDING')
    remarks = models.TextField(blank=True)
    
    # WhatsApp confirmation
    whatsapp_sent = models.BooleanField(default=False)
    whatsapp_sent_at = models.DateTimeField(null=True, blank=True)
    
    def save(self, *args, **kwargs):
        if not self.order_number:
            from django.db import transaction
            with transaction.atomic():
                # Simple incremental order numbering
                # Get the highest existing order ID and increment
                last_order = Order.objects.select_for_update().order_by('id').last()
                
                if last_order:
                    next_id = last_order.id + 1
                else:
                    next_id = 1
                
                # Simple format: ORD + 6-digit incremental number
                self.order_number = f"ORD{next_id:06d}"
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.order_number} - {self.dealer.name}"
    
    def get_total_quantity(self):
        """Calculate total quantity across all order items"""
        return sum(item.quantity for item in self.order_items.all())
    
    def get_total_value(self):
        """Calculate total value of the order"""
        return sum(item.get_total_value() for item in self.order_items.all())
    
    class Meta:
        ordering = ['-order_date']

class OrderItem(BaseModel):
    """Order line items for different products"""
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='order_items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.DecimalField(max_digits=8, decimal_places=2)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    def get_total_value(self):
        """Calculate total value for this line item"""
        return self.quantity * self.unit_price
    
    def __str__(self):
        return f"{self.order.order_number} - {self.product.name}: {self.quantity}"
    
    class Meta:
        unique_together = ['order', 'product']

class MRN(BaseModel):
    """Material Receipt Note model"""
    MRN_STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
    ]
    
    mrn_number = models.CharField(max_length=20, unique=True, editable=False)
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='mrn')
    mrn_date = models.DateField(default=timezone.now)
    status = models.CharField(max_length=20, choices=MRN_STATUS_CHOICES, default='PENDING')
    
    # Quality check fields
    quality_checked = models.BooleanField(default=False)
    quality_remarks = models.TextField(blank=True)
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_mrns')
    
    def save(self, *args, **kwargs):
        if not self.mrn_number:
            self.mrn_number = f"MRN{uuid.uuid4().hex[:12].upper()}"
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.mrn_number} - {self.order.order_number}"
    
    class Meta:
        ordering = ['-mrn_date']

class Invoice(BaseModel):
    """Invoice/Bill model"""
    INVOICE_STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('SENT', 'Sent'),
        ('PAID', 'Paid'),
        ('OVERDUE', 'Overdue'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    invoice_number = models.CharField(max_length=20, unique=True, editable=False)
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='invoice')
    invoice_date = models.DateField(default=timezone.now)
    due_date = models.DateField()
    
    # Financial fields
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    status = models.CharField(max_length=20, choices=INVOICE_STATUS_CHOICES, default='DRAFT')
    
    # Payment tracking
    payment_received = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    payment_date = models.DateField(null=True, blank=True)
    
    def save(self, *args, **kwargs):
        if not self.invoice_number:
            today = timezone.now().date()
            count = Invoice.objects.filter(invoice_date=today).count() + 1
            self.invoice_number = f"INV{today.strftime('%Y%m%d')}{count:04d}"
        
        # Calculate due date if not provided
        if not self.due_date:
            self.due_date = self.invoice_date + timezone.timedelta(days=self.order.dealer.credit_days)
        
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.invoice_number} - {self.order.dealer.name}"
    
    def get_balance_amount(self):
        """Calculate remaining balance"""
        return self.total_amount - self.payment_received
    
    class Meta:
        ordering = ['-invoice_date']



class AuditLog(BaseModel):
    """Audit trail for important actions"""
    ACTION_CHOICES = [
        ('ORDER_CREATED', 'Order Created'),
        ('ORDER_UPDATED', 'Order Updated'),
        ('MRN_CREATED', 'MRN Created'),
        ('MRN_APPROVED', 'MRN Approved'),
        ('INVOICE_GENERATED', 'Invoice Generated'),
        ('PAYMENT_RECEIVED', 'Payment Received'),
        ('ORDER_CANCELLED', 'Order Cancelled'),
    ]
    
    action = models.CharField(max_length=30, choices=ACTION_CHOICES)
    model_name = models.CharField(max_length=50)
    object_id = models.CharField(max_length=20)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='auditlog_user_set')
    details = models.JSONField(default=dict)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.action} - {self.model_name}({self.object_id})"
    
    class Meta:
        ordering = ['-created_at']

# Additional utility models for system configuration
class AppSettings(BaseModel):
    """Application settings and configurations"""
    key = models.CharField(max_length=100, unique=True)
    value = models.TextField()
    description = models.TextField(blank=True)
    
    def __str__(self):
        return f"{self.key}: {self.value}"
    
    class Meta:
        ordering = ['key']

class NotificationTemplate(BaseModel):
    """Templates for various notifications"""
    TEMPLATE_TYPE_CHOICES = [
        ('WHATSAPP', 'WhatsApp'),
        ('EMAIL', 'Email'),
        ('SMS', 'SMS'),
    ]
    
    name = models.CharField(max_length=100)
    type = models.CharField(max_length=20, choices=TEMPLATE_TYPE_CHOICES)
    subject = models.CharField(max_length=200, blank=True)
    template_content = models.TextField()
    variables = models.JSONField(default=list, help_text="List of variables used in template")
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return f"{self.name} ({self.type})"
    
    class Meta:
        ordering = ['name']

# Think this through before implementing a model.
class DealerContext(BaseModel):
    """Model to store contextual information about dealers for AI-enhanced relationship management
    
    Based on psychological principles:
    1. Kahneman's structured evaluation: Independent trait assessment before intuitive judgment
    2. Understanding-focused negotiation: Deep comprehension over persuasion
    """
    
    INTERACTION_TYPE_CHOICES = [
        ('CALL', 'Phone Call'),
        ('WHATSAPP', 'WhatsApp'),
        ('EMAIL', 'Email'),
        ('MEETING', 'In-Person Meeting'),
        ('ORDER', 'Order Related'),
        ('COMPLAINT', 'Complaint/Issue'),
        ('INQUIRY', 'General Inquiry'),
        ('PAYMENT', 'Payment Related'),
        ('OTHER', 'Other'),
    ]
    
    SENTIMENT_CHOICES = [
        ('POSITIVE', 'Positive'),
        ('NEUTRAL', 'Neutral'),
        ('NEGATIVE', 'Negative'),
        ('URGENT', 'Urgent'),
    ]
    
    PRIORITY_CHOICES = [
        ('LOW', 'Low'),
        ('MEDIUM', 'Medium'),
        ('HIGH', 'High'),
        ('CRITICAL', 'Critical'),
    ]
    
    dealer = models.ForeignKey(Dealer, on_delete=models.CASCADE, related_name='contexts')
    
    # Interaction details
    interaction_type = models.CharField(max_length=20, choices=INTERACTION_TYPE_CHOICES)
    interaction_date = models.DateTimeField(default=timezone.now)
    interaction_summary = models.TextField(help_text="Brief summary of the interaction")
    detailed_notes = models.TextField(blank=True, help_text="Detailed notes about the interaction")
    
    # Context and sentiment analysis
    sentiment = models.CharField(max_length=20, choices=SENTIMENT_CHOICES, default='NEUTRAL')
    priority_level = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='MEDIUM')
    
    # Kahneman-inspired structured trait evaluation (1-10 scale for independent assessment)
    # Business traits
    reliability_score = models.PositiveSmallIntegerField(null=True, blank=True, help_text="Reliability in commitments (1-10)")
    communication_clarity = models.PositiveSmallIntegerField(null=True, blank=True, help_text="How clearly they communicate (1-10)")
    payment_punctuality = models.PositiveSmallIntegerField(null=True, blank=True, help_text="Payment timeliness (1-10)")
    order_consistency = models.PositiveSmallIntegerField(null=True, blank=True, help_text="Consistency in order patterns (1-10)")
    
    # Relationship traits
    trust_level = models.PositiveSmallIntegerField(null=True, blank=True, help_text="Level of mutual trust (1-10)")
    openness_to_feedback = models.PositiveSmallIntegerField(null=True, blank=True, help_text="Receptiveness to suggestions (1-10)")
    cooperation_level = models.PositiveSmallIntegerField(null=True, blank=True, help_text="Willingness to cooperate (1-10)")
    loyalty_tendency = models.PositiveSmallIntegerField(null=True, blank=True, help_text="Tendency to remain loyal (1-10)")
    
    # Understanding-focused fields (based on "negotiation is about understanding")
    # Deep understanding of dealer's perspective
    primary_motivations = models.TextField(blank=True, help_text="What truly drives this dealer's decisions")
    business_challenges = models.TextField(blank=True, help_text="Key challenges they face in their business")
    success_metrics = models.TextField(blank=True, help_text="How they measure success and what matters most")
    concerns_expressed = models.TextField(blank=True, help_text="Specific concerns or worries they've shared")
    aspirations_goals = models.TextField(blank=True, help_text="Their business aspirations and long-term goals")
    
    # Communication and decision-making patterns
    preferred_communication_style = models.CharField(max_length=200, blank=True, help_text="How they prefer to communicate")
    decision_making_process = models.TextField(blank=True, help_text="How they make business decisions and who influences them")
    information_preferences = models.TextField(blank=True, help_text="What type of information they value most")
    timing_preferences = models.TextField(blank=True, help_text="When and how they prefer to be contacted")
    
    
    # Business context
    topics_discussed = models.JSONField(default=list, help_text="List of topics/keywords discussed")
    products_mentioned = models.ManyToManyField(Product, blank=True, help_text="Products discussed in this interaction")
    follow_up_required = models.BooleanField(default=False)
    follow_up_date = models.DateTimeField(null=True, blank=True)
    follow_up_notes = models.TextField(blank=True)
    

    intuitive_assessment = models.TextField(blank=True, help_text="Final intuitive judgment after structured trait evaluation")
    
  
    # Resolution and outcome
    issue_resolved = models.BooleanField(default=False)
    resolution_notes = models.TextField(blank=True)
    outcome = models.CharField(max_length=200, blank=True, help_text="Key outcome or next step")
    understanding_gained = models.TextField(blank=True, help_text="New understanding gained about the dealer")
    
   
    # Tags for categorization
    tags = models.JSONField(default=list, help_text="Custom tags for categorization and filtering")
    
    def __str__(self):
        return f"{self.dealer.name} - {self.interaction_type} ({self.interaction_date.strftime('%Y-%m-%d')})"
    
    def get_follow_up_status(self):
        """Check if follow-up is overdue"""
        if self.follow_up_required and self.follow_up_date:
            return timezone.now() > self.follow_up_date
        return False
    
    def add_ai_insight(self, key, value):
        """Helper method to add AI insights"""
        if not self.ai_insights:
            self.ai_insights = {}
        self.ai_insights[key] = value
        self.save()
    
    def get_structured_trait_scores(self):
        """Get all structured trait scores (Kahneman approach)"""
        business_traits = {
            'reliability_score': self.reliability_score,
            'communication_clarity': self.communication_clarity,
            'payment_punctuality': self.payment_punctuality,
            'order_consistency': self.order_consistency,
        }
        relationship_traits = {
            'trust_level': self.trust_level,
            'openness_to_feedback': self.openness_to_feedback,
            'cooperation_level': self.cooperation_level,
            'loyalty_tendency': self.loyalty_tendency,
        }
        return {
            'business_traits': business_traits,
            'relationship_traits': relationship_traits,
            'average_business': sum(filter(None, business_traits.values())) / len([x for x in business_traits.values() if x is not None]) if any(business_traits.values()) else None,
            'average_relationship': sum(filter(None, relationship_traits.values())) / len([x for x in relationship_traits.values() if x is not None]) if any(relationship_traits.values()) else None,
        }
    
    def get_understanding_summary(self):
        """Get summary of understanding gained about dealer"""
        understanding = {}
        if self.primary_motivations:
            understanding['motivations'] = self.primary_motivations
        if self.business_challenges:
            understanding['challenges'] = self.business_challenges
        if self.success_metrics:
            understanding['success_metrics'] = self.success_metrics
        if self.concerns_expressed:
            understanding['concerns'] = self.concerns_expressed
        if self.aspirations_goals:
            understanding['goals'] = self.aspirations_goals
        return understanding
    
    def update_trait_score(self, trait_name, score):
        """Update a specific trait score with validation"""
        if trait_name in ['reliability_score', 'communication_clarity', 'payment_punctuality', 
                         'order_consistency', 'trust_level', 'openness_to_feedback', 
                         'cooperation_level', 'loyalty_tendency']:
            if 1 <= score <= 10:
                setattr(self, trait_name, score)
                self.save()
                return True
        return False
    
    class Meta:
        ordering = ['-interaction_date']
        verbose_name = "Dealer Context"
        verbose_name_plural = "Dealer Contexts"
        indexes = [
            models.Index(fields=['dealer', '-interaction_date']),
            models.Index(fields=['interaction_type', '-interaction_date']),
            models.Index(fields=['sentiment', 'priority_level']),
            models.Index(fields=['follow_up_required', 'follow_up_date']),
            models.Index(fields=['reliability_score', 'trust_level']),
        ]