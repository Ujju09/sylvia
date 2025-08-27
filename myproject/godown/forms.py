from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db import models
from .models import OrderInTransit, GodownLocation, CrossoverRecord, GodownInventory
from sylvia.models import Product, Dealer
from django.db.models import Sum


class OrderInTransitForm(forms.ModelForm):
    """User-friendly form for OrderInTransit model designed for minimally skilled users"""
    
    class Meta:
        model = OrderInTransit
        fields = [
            'eway_bill_number', 'transport_document_number', 'godown',
            'actual_arrival_date', 'status', 'product','expected_total_bags',
            'actual_received_bags', 'good_bags', 'damaged_bags',
            'crossover_required', 'crossover_bags', 'arrival_notes'
        ]
        widgets = {
            'eway_bill_number': forms.TextInput(attrs={
                'class': 'form-control form-control-lg',
                'placeholder': 'Enter E-way bill number (e.g., 123456789012)',
                'pattern': '[0-9]{12}',
                'title': 'E-way bill number should be 12 digits',
                'maxlength': '15',
                'autocomplete': 'off'
            }),
            'transport_document_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Transport document number (optional)',
                'maxlength': '50'
            }),
            'godown': forms.Select(attrs={
                'class': 'form-control form-control-lg',
                'required': True
            }),
            'actual_arrival_date': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local',
                'value': timezone.now().strftime('%Y-%m-%dT%H:%M')
            }),
            'status': forms.Select(attrs={
                'class': 'form-control form-control-lg'
            }),
            'product': forms.Select(attrs={
                'class': 'form-control form-control-lg',
                'required': True
            }),
            'expected_total_bags': forms.NumberInput(attrs={
                'class': 'form-control form-control-lg',
                'placeholder': 'Number of bags expected (from E-way bill)',
                'min': '1',
                'step': '1',
                'required': True
            }),
            'actual_received_bags': forms.NumberInput(attrs={
                'class': 'form-control form-control-lg',
                'placeholder': 'Number of bags actually received',
                'min': '0',
                'step': '1',
                'value': '0'
            }),
            'good_bags': forms.NumberInput(attrs={
                'class': 'form-control form-control-lg',
                'placeholder': 'Number of bags in good condition',
                'min': '0',
                'step': '1',
                'value': '0'
            }),
            'damaged_bags': forms.NumberInput(attrs={
                'class': 'form-control form-control-lg',
                'placeholder': 'Number of damaged bags',
                'min': '0',
                'step': '1',
                'value': '0'
            }),
            'crossover_required': forms.CheckboxInput(attrs={
                'class': 'form-check-input form-check-input-lg',
                'role': 'switch'
            }),
            'crossover_bags': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Number of bags for crossover',
                'min': '0',
                'step': '1',
                'value': '0'
            }),
            'arrival_notes': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'Add any notes about arrival condition, delays, or special instructions',
                'rows': '4',
                'maxlength': '1000'
            })
        }
        labels = {
            'eway_bill_number': 'E-way Bill Number',
            'transport_document_number': 'Transport Document Number',
            'godown': 'Select Godown Location',
            'actual_arrival_date': 'Actual Arrival Date & Time',
            'status': 'Current Status',
            'product': 'Product',
            'expected_total_bags': 'Expected Total Bags',
            'actual_received_bags': 'Actual Received Bags',
            'good_bags': 'Good Bags (for storage)',
            'damaged_bags': 'Damaged Bags',
            'crossover_required': 'Crossover Required?',
            'crossover_bags': 'Crossover Bags',
            'arrival_notes': 'Notes and Remarks'
        }
        help_texts = {
            'eway_bill_number': 'Enter the 12-digit E-way bill number exactly as shown on the document',
            'transport_document_number': 'Any transport receipt, challan or reference number (can be left blank)',
            'godown': 'Select the godown where this shipment will be received',
            'actual_arrival_date': 'Date and time when the shipment actually arrived (defaults to now)',
            'status': 'IN_TRANSIT: Still coming | ARRIVED: Reached godown',
            'product': 'Select the product that arrived',
            'expected_total_bags': 'Total number of bags mentioned in the E-way bill',
            'actual_received_bags': 'Count of bags actually received after unloading',
            'good_bags': 'Number of bags that are in good condition and can be stored',
            'damaged_bags': 'Number of bags that are damaged and cannot be stored for sale',
            'crossover_required': 'Check if some bags need to be transferred directly to another vehicle',
            'crossover_bags': 'Number of bags to be transferred directly (crossover)',
            'arrival_notes': 'Any special notes about delays, condition, or instructions'
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Filter active godowns only
        self.fields['godown'].queryset = GodownLocation.objects.filter(is_active=True).order_by('name')
        
        # Set default arrival date to current time if creating new record
        if not self.instance.pk:
            self.fields['actual_arrival_date'].initial = timezone.now()
            
        # Crossover bags field visibility is controlled by JavaScript, not inline styles

    def clean(self):
        cleaned_data = super().clean()
        
        # Get values for validation
        expected_total = cleaned_data.get('expected_total_bags', 0)
        actual_received = cleaned_data.get('actual_received_bags', 0)
        good_bags = cleaned_data.get('good_bags', 0)
        damaged_bags = cleaned_data.get('damaged_bags', 0)
        crossover_required = cleaned_data.get('crossover_required', False)
        crossover_bags = cleaned_data.get('crossover_bags', 0)

        # Validation: Good bags + Damaged bags should equal Actual received bags
        if good_bags + damaged_bags != actual_received:
            raise ValidationError(
                "Good bags + Damaged bags must equal Actual received bags. "
                f"Currently: {good_bags} + {damaged_bags} = {good_bags + damaged_bags}, "
                f"but actual received is {actual_received}"
            )

        # Validation: If crossover required, crossover bags must be greater than 0
        if crossover_required and crossover_bags <= 0:
            raise ValidationError(
                "If crossover is required, you must specify the number of crossover bags (greater than 0)"
            )

        # Validation: Crossover bags cannot exceed good bags
        if crossover_bags > good_bags:
            raise ValidationError(
                f"Crossover bags ({crossover_bags}) cannot exceed good bags ({good_bags})"
            )

        # Auto-calculate shortage and excess bags
        if expected_total > actual_received:
            cleaned_data['shortage_bags'] = expected_total - actual_received
            cleaned_data['excess_bags'] = 0
        elif actual_received > expected_total:
            cleaned_data['excess_bags'] = actual_received - expected_total
            cleaned_data['shortage_bags'] = 0
        else:
            cleaned_data['shortage_bags'] = 0
            cleaned_data['excess_bags'] = 0

        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        
        # Set the calculated shortage and excess bags
        cleaned_data = self.cleaned_data
        instance.shortage_bags = cleaned_data.get('shortage_bags', 0)
        instance.excess_bags = cleaned_data.get('excess_bags', 0)
        
        # Generate dispatch_id if not set (for new instances)
        if not instance.dispatch_id:
            # Generate a unique dispatch ID based on godown code and timestamp
            timestamp = timezone.now().strftime('%Y%m%d%H%M%S')
            godown_code = instance.godown.code if instance.godown else 'GD'
            instance.dispatch_id = f"TXN{godown_code}{timestamp}"
        
        if commit:
            instance.save()
        
        return instance


# Removed ProductCrossoverForm - no longer needed for single-product workflow


class CrossoverRecordForm(forms.ModelForm):
    """Main form for crossover record creation and editing"""
    
    class Meta:
        model = CrossoverRecord
        fields = [
            'source_order_transit', 'destination_dealer', 'product', 
            'requested_bags', 'actual_transferred_bags', 'approved_date', 
            'supervised_by', 'crossover_notes'
        ]
        widgets = {
            'source_order_transit': forms.Select(attrs={
                'class': 'form-control form-control-lg',
                'required': True
            }),
            'destination_dealer': forms.Select(attrs={
                'class': 'form-control form-control-lg',
                'required': True
            }),
            'product': forms.Select(attrs={
                'class': 'form-control form-control-lg',
                'required': True
            }),
            'requested_bags': forms.NumberInput(attrs={
                'class': 'form-control form-control-lg',
                'placeholder': 'Number of bags to crossover',
                'min': '1',
                'step': '1',
                'required': True
            }),
            'actual_transferred_bags': forms.NumberInput(attrs={
                'class': 'form-control form-control-lg',
                'placeholder': 'Actual bags transferred',
                'min': '0',
                'step': '1',
                'value': '0'
            }),
            'approved_date': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local',
                'value': timezone.now().strftime('%Y-%m-%dT%H:%M')
            }),
            'supervised_by': forms.Select(attrs={
                'class': 'form-control',
            }),
            'crossover_notes': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'Add any notes about the crossover process',
                'rows': '4',
                'maxlength': '1000'
            })
        }
        labels = {
            'source_order_transit': 'Source Transit Order',
            'destination_dealer': 'Destination Dealer',
            'product': 'Product',
            'requested_bags': 'Requested Bags',
            'actual_transferred_bags': 'Actual Transferred Bags',
            'approved_date': 'Approval Date & Time',
            'supervised_by': 'Supervised By',
            'crossover_notes': 'Notes and Remarks'
        }
        help_texts = {
            'source_order_transit': 'Select the arrived E-way Bill from which to crossover',
            'destination_dealer': 'Select the dealer who will receive the crossover goods',
            'product': 'Select the product to crossover',
            'requested_bags': 'Number of bags requested for crossover',
            'actual_transferred_bags': 'Actual number of bags transferred (fill after completion)',
            'approved_date': 'Date and time when crossover was approved',
            'supervised_by': 'Person who supervised the crossover process',
            'crossover_notes': 'Any additional notes about the crossover process'
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Filter to only show ARRIVED transit orders with crossover bags available
        self.fields['source_order_transit'].queryset = OrderInTransit.objects.filter(
            status='ARRIVED',
            crossover_required=True,
            crossover_bags__gt=0
        ).order_by('-actual_arrival_date')
        
        # Filter active dealers
        self.fields['destination_dealer'].queryset = Dealer.objects.filter(
            is_active=True
        ).order_by('name')
        
        # Filter active products
        self.fields['product'].queryset = Product.objects.filter(
            is_active=True
        ).order_by('name')
        
        # Filter users for supervised_by field
        from django.contrib.auth.models import User
        self.fields['supervised_by'].queryset = User.objects.filter(
            is_active=True
        ).order_by('first_name', 'last_name')
        
        # Set default approval date
        if not self.instance.pk:
            self.fields['approved_date'].initial = timezone.now()

    def clean(self):
        cleaned_data = super().clean()
        print(cleaned_data)

        source_order_transit = cleaned_data.get('source_order_transit.id_for_label')
        print(source_order_transit)
        product = cleaned_data.get('product')
        requested_bags = cleaned_data.get('requested_bags')
        actual_transferred_bags = cleaned_data.get('actual_transferred_bags')
        
        if source_order_transit and product and requested_bags:
            # Check if product is available in the source transit order's inventory
            available_inventory_qs = OrderInTransit.objects.filter(
                dispatch_id=source_order_transit,
                product=product.id,
                 good_bags__gt=0
            )

            print(available_inventory_qs)

            if not available_inventory_qs.exists():
                raise ValidationError(
                    f"Product {product.name} is not available in the selected transit order."
                )
            
            # Get total available bags across all inventory records for this product
            total_available_bags = available_inventory_qs.aggregate(
                total=models.Sum('good_bags')
            )['total'] or 0
            
            if total_available_bags <= 0:
                raise ValidationError(
                    f"Product {product.name} has no available bags for crossover in the selected transit order."
                )
            
            # Check if requested bags exceed available bags
            if requested_bags > total_available_bags:
                raise ValidationError(
                    f"Cannot request {requested_bags} bags of {product.name}. "
                    f"Only {total_available_bags} bags available for crossover."
                )
            
            # Check against crossover allocation from transit order
            total_crossover_requested = CrossoverRecord.objects.filter(
                source_order_transit=source_order_transit,
                product=product
            ).exclude(pk=self.instance.pk if self.instance else None).aggregate(
                total=models.Sum('requested_bags')
            )['total'] or 0
            
            total_with_current = total_crossover_requested + requested_bags
            
            if total_with_current > source_order_transit.crossover_bags:
                raise ValidationError(
                    f"Total crossover requests ({total_with_current} bags) exceed "
                    f"available crossover allocation ({source_order_transit.crossover_bags} bags) "
                    f"for this transit order."
                )
        
        if actual_transferred_bags and requested_bags and actual_transferred_bags > requested_bags:
            raise ValidationError(
                "Actual transferred bags cannot exceed requested bags."
            )
        
        return cleaned_data


# Removed MultipleCrossoverForm - no longer needed for single-product workflow