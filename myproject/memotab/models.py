from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from decimal import Decimal


class BaseModel(models.Model):
    """Base model with common fields"""
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        abstract = True


class Source(BaseModel):
    """Model for cash collection sources"""
    text = models.CharField(max_length=200, help_text="Description of the cash collection source")
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return self.text
    
    class Meta:
        ordering = ['text']


class CashCollect(BaseModel):
    """Model for cash collection records"""
    date = models.DateField(default=timezone.now, help_text="Date of cash collection")
    source = models.ForeignKey(Source, on_delete=models.CASCADE, related_name='cash_collections')
    amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        help_text="Amount collected in currency"
    )
    received_by = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='received_cash_collections',
        help_text="User who received the cash"
    )
    note = models.TextField(blank=True, help_text="Additional notes about the cash collection")
    
    def __str__(self):
        return f"{self.date} - {self.source.text}: {self.amount}"
    
    class Meta:
        ordering = ['-date', '-created_at']
        verbose_name = "Cash Collection"
        verbose_name_plural = "Cash Collections"
        indexes = [
            models.Index(fields=['date', 'source']),
            models.Index(fields=['received_by', '-date']),
        ]
