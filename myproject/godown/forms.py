from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db import models
from .models import OrderInTransit, GodownLocation, CrossoverRecord, GodownInventory, LoadingRequest
from sylvia.models import Product, Dealer
from django.db.models import Sum



class OrderInTransitForm(forms.ModelForm):
    """User-friendly form for OrderInTransit model designed for minimally skilled users"""

    class Meta:
        model = OrderInTransit
        fields = [
            'eway_bill_number', 'transport_document_number', 'godown',
            'actual_arrival_date', 'status', 'product', 'expected_total_bags',
            'actual_received_bags', 'good_bags', 'damaged_bags',
            'crossover_required', 'crossover_bags', 'crossover_dealer', 'arrival_notes'
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
            'crossover_dealer': forms.Select(attrs={
                'class': 'form-control',
                'style': 'display: none;'  # Initially hidden, shown via JavaScript
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
            'crossover_dealer': 'Crossover Dealer',
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
            'crossover_dealer': 'Select the dealer who will receive the crossover goods',
            'arrival_notes': 'Any special notes about delays, condition, or instructions'
        }

    def __init__(self, *args, **kwargs):
        # Extract user from kwargs for atomic transaction use
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        # Filter active godowns only
        self.fields['godown'].queryset = GodownLocation.objects.filter(
            is_active=True).order_by('name')

        # Filter active dealers for crossover
        self.fields['crossover_dealer'].queryset = Dealer.objects.filter(
            is_active=True).order_by('name')
        self.fields['crossover_dealer'].empty_label = "-- Select Dealer for Crossover --"

        # Set default arrival date to current time if creating new record
        if not self.instance.pk:
            self.fields['actual_arrival_date'].initial = timezone.now()

        # Crossover fields visibility is controlled by JavaScript

    def clean(self):
        cleaned_data = super().clean()

        # Get values for validation
        expected_total = cleaned_data.get('expected_total_bags', 0)
        actual_received = cleaned_data.get('actual_received_bags', 0)
        good_bags = cleaned_data.get('good_bags', 0)
        damaged_bags = cleaned_data.get('damaged_bags', 0)
        crossover_required = cleaned_data.get('crossover_required', False)
        crossover_bags = cleaned_data.get('crossover_bags', 0)
        crossover_dealer = cleaned_data.get('crossover_dealer')

        # Validation: Good bags + Damaged bags should equal Actual received bags
        if good_bags + damaged_bags != actual_received:
            raise ValidationError(
                "Good bags + Damaged bags must equal Actual received bags. "
                f"Currently: {good_bags} + {damaged_bags} = {good_bags + damaged_bags}, "
                f"but actual received is {actual_received}"
            )

        # Validation: If crossover required, crossover bags must be greater than 0 and dealer must be selected
        if crossover_required and crossover_bags <= 0:
            raise ValidationError(
                "If crossover is required, you must specify the number of crossover bags (greater than 0)"
            )
        
        if crossover_required and not crossover_dealer:
            raise ValidationError(
                "If crossover is required, you must select a dealer who will receive the crossover goods"
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
    

    def _create_godown_inventory_record(self, order_instance, storage_bags):
        """Create GodownInventory record for bags going to storage"""
        
        try:
            inventory_record = GodownInventory.objects.create(
                order_in_transit=order_instance,
                godown=order_instance.godown,
                product=order_instance.product,
                total_bags_received=storage_bags,
                good_bags_available=storage_bags,
                damaged_bags=0,
                storage_notes=f"Auto-created from OrderInTransit {order_instance.eway_bill_number}",
                created_by=order_instance.created_by
            )
            return inventory_record
            
        except Exception as e:
            # TODO: Implement logging
            raise
    
    def _create_crossover_record(self, order_instance):
        
        try:
            crossover_record = CrossoverRecord.objects.create(
                source_order_transit=order_instance,
                destination_dealer=order_instance.crossover_dealer,
                product=order_instance.product,
                requested_bags=order_instance.crossover_bags,
                actual_transferred_bags=order_instance.crossover_bags,
                approved_date=timezone.now(),
                supervised_by=order_instance.created_by,
                crossover_notes=f"Auto-created from OrderInTransit {order_instance.eway_bill_number}",
                created_by=order_instance.created_by
            )
            return crossover_record
            
        except Exception as e:
            # TODO: Implement logging
            raise

    def save(self, commit=True):
        from django.db import transaction
        import logging
        logger = logging.getLogger(__name__)
       
        instance = super().save(commit=False)
        is_new = not hasattr(instance, 'dispatch_id') or not instance.dispatch_id

        # Set the calculated shortage and excess bags
        cleaned_data = self.cleaned_data
        instance.shortage_bags = cleaned_data.get('shortage_bags', 0)
        instance.excess_bags = cleaned_data.get('excess_bags', 0)


        # Generate dispatch_id if this is a new instance
        if is_new:
            # Generate a unique dispatch ID based on godown code and timestamp
            timestamp = timezone.now().strftime('%Y%m%d%H%M%S')
            godown_code = instance.godown.code if instance.godown else 'GD'
            instance.dispatch_id = f"TXN{godown_code}-{timestamp}"

        if commit:
            try:
                with transaction.atomic():
                    print("Saving OrderInTransit instance...")
                    

                    # Set created_by user if provided and this is a new instance
                    if self.user and is_new:
                        instance.created_by = self.user
                        instance.updated_by = self.user

                    # Save the main instance first
                    instance.save()
                    
                    
                    # Only create related records for new instances
                    if is_new:
                        # Calculate storage bags (good bags minus crossover bags)
                        storage_bags = instance.good_bags
                        if instance.crossover_required:
                            storage_bags -= instance.crossover_bags
                       
                        
                        # Create GodownInventory record if there are storage bags
                        if storage_bags > 0:

                            inventory_record = self._create_godown_inventory_record(instance, storage_bags)

                        else:
                            pass

                        # Create CrossoverRecord if crossover is required
                        if instance.crossover_required and instance.crossover_bags > 0:
                            crossover_record = self._create_crossover_record(instance)
                        else:
                            pass
                        #TODO: Implement logging
                    

            except Exception as e:
                
                logger.error(f"Error during OrderInTransit save: {str(e)}", exc_info=True)
                raise
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

        source_order_transit = cleaned_data.get(
            'source_order_transit.id_for_label')
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


class GodownInventoryForm(forms.ModelForm):
    class Meta:
        model = GodownInventory
        fields = [
            'order_in_transit', 'godown', 'product', 'total_bags_received', 'good_bags_available', 'damaged_bags', 'storage_notes'
        ]
        widgets = {
            'order_in_transit': forms.Select(attrs={
                'class': 'form-control form-control-lg',
                'required': True
            }),
            'godown': forms.Select(attrs={
                'class': 'form-control form-control-lg',
                'required': True
            }),
            'product': forms.Select(attrs={
                'class': 'form-control form-control-lg',
                'required': True
            }),
            
            'total_bags_received': forms.NumberInput(attrs={
                'class': 'form-control form-control-lg',
                'placeholder': 'Total bags received',
                'min': 1,
                'step': 1,
                'required': True
            }),
            'good_bags_available': forms.NumberInput(attrs={
                'class': 'form-control form-control-lg',
                'placeholder': 'Good bags available for storage',
                'min': 0,
                'step': 1,
                'value': 0
            }),
            'damaged_bags': forms.NumberInput(attrs={
                'class': 'form-control form-control-lg',
                'placeholder': 'Damaged bags',
                'min': 0,
                'step': 1,
                'value': 0
            }),
            'storage_notes': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': "Add any notes about storage conditions, quality, or special instructions",
                'rows': 4,
                'maxlength': 1000
            })
        }

        labels = {
            'order_in_transit': 'Source Order Transit',
            'godown': 'Godown',
            'product': 'Product',
            'total_bags_received': 'Total Bags Received',
            'good_bags_available': 'Good Bags Available',
            'damaged_bags': 'Damaged Bags',
            'storage_notes': 'Storage Notes'
        }

        help_texts = {
            'order_in_transit': 'Select the source order transit for this inventory record.',
            'godown': 'Select the godown where the inventory is stored.',
            'product': 'Select the product for this inventory record.',
            'total_bags_received': 'Enter the total number of bags received.',
            'good_bags_available': 'Enter the number of good bags available for storage.',
            'damaged_bags': 'Enter the number of damaged bags.',
            'storage_notes': 'Add any notes about storage conditions, quality, or special instructions.'
        }

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)

            # Filter active godowns only
            self.fields['godown'].queryset = GodownLocation.objects.filter(
                is_active=True).order_by('name')

            self.fields['order_in_transit'].queryset = OrderInTransit.objects.filter(
                status='ARRIVED'
            ).order_by('-actual_arrival_date')

            self.fields['product'].queryset = Product.objects.filter(
                is_active=True).order_by('name')


        def clean(self):
            cleaned_data = super().clean()

            # Custom validation logic here

            return cleaned_data


class LoadingRecordForm(forms.ModelForm):
    """Ultra-simple form for Loading Records designed for minimally skilled users"""

    class Meta:
        model = LoadingRequest
        fields = [
            'godown', 'dealer', 'product', 
            'requested_bags', 'loaded_bags', 'supervised_by', 
            'special_instructions', 'loading_notes'
        ]
        widgets = {
            'godown': forms.Select(attrs={
                'class': 'form-control form-control-lg',
                'required': True,
                'style': 'font-size: 1.1rem; padding: 0.75rem;'
            }),
            'dealer': forms.Select(attrs={
                'class': 'form-control form-control-lg',
                'required': True,
                'style': 'font-size: 1.1rem; padding: 0.75rem;'
            }),
            'product': forms.Select(attrs={
                'class': 'form-control form-control-lg',
                'required': True,
                'style': 'font-size: 1.1rem; padding: 0.75rem;'
            }),
            'requested_bags': forms.NumberInput(attrs={
                'class': 'form-control form-control-lg',
                'placeholder': 'How many bags requested?',
                'min': '1',
                'step': '1',
                'required': True,
                'style': 'font-size: 1.2rem; padding: 1rem; text-align: center;'
            }),
            'loaded_bags': forms.NumberInput(attrs={
                'class': 'form-control form-control-lg',
                'placeholder': 'How many bags actually loaded?',
                'min': '0',
                'step': '1',
                'value': '0',
                'style': 'font-size: 1.2rem; padding: 1rem; text-align: center;'
            }),
            'supervised_by': forms.Select(attrs={
                'class': 'form-control form-control-lg',
                'style': 'font-size: 1.1rem; padding: 0.75rem;'
            }),
            'special_instructions': forms.Textarea(attrs={
                'class': 'form-control form-control-lg',
                'placeholder': 'Any special instructions for loading? (Optional)',
                'rows': '3',
                'maxlength': '500',
                'style': 'font-size: 1rem; padding: 0.75rem;'
            }),
            'loading_notes': forms.Textarea(attrs={
                'class': 'form-control form-control-lg',
                'placeholder': 'Any notes about the loading process? (Optional)',
                'rows': '3',
                'maxlength': '500',
                'style': 'font-size: 1rem; padding: 0.75rem;'
            })
        }
        labels = {
            'godown': '📦 Which Godown (Warehouse)?',
            'dealer': '🏪 Which Dealer (Customer)?',
            'product': '🎯 Which Product?',
            'requested_bags': '📋 Bags Requested',
            'loaded_bags': '✅ Bags Actually Loaded',
            'supervised_by': '👤 Supervised By',
            'special_instructions': '📝 Special Instructions',
            'loading_notes': '💭 Loading Notes'
        }
        help_texts = {
            'godown': 'Select the warehouse location where goods will be loaded from',
            'dealer': 'Select which dealer/customer is receiving the goods',
            'product': 'Select the type of product being loaded',
            'requested_bags': 'Enter how many bags were requested by the dealer',
            'loaded_bags': 'Enter how many bags were actually loaded onto the vehicle',
            'supervised_by': 'Who supervised this loading operation?',
            'special_instructions': 'Any special handling or loading instructions (can be left blank)',
            'loading_notes': 'Any notes about the loading process or observations (can be left blank)'
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Filter active godowns only
        self.fields['godown'].queryset = GodownLocation.objects.filter(
            is_active=True).order_by('name')
        self.fields['godown'].empty_label = "-- Choose Warehouse --"

        # Filter active dealers
        self.fields['dealer'].queryset = Dealer.objects.filter(
            is_active=True).order_by('name')
        self.fields['dealer'].empty_label = "-- Choose Customer --"

        # Filter active products
        self.fields['product'].queryset = Product.objects.filter(
            is_active=True).order_by('name')
        self.fields['product'].empty_label = "-- Choose Product --"

        # Filter users for supervised_by field
        from django.contrib.auth.models import User
        self.fields['supervised_by'].queryset = User.objects.filter(
            is_active=True
        ).order_by('first_name', 'last_name')
        self.fields['supervised_by'].empty_label = "-- Choose Supervisor --"

        # Make optional fields clearly optional
        self.fields['special_instructions'].required = False
        self.fields['loading_notes'].required = False
        self.fields['supervised_by'].required = False

    def clean(self):
        cleaned_data = super().clean()
        
        godown = cleaned_data.get('godown')
        product = cleaned_data.get('product')
        requested_bags = cleaned_data.get('requested_bags', 0)
        loaded_bags = cleaned_data.get('loaded_bags', 0)

        # Validation: Check if requested bags exceed available inventory
        if godown and product and requested_bags > 0:
            # Get total available bags from GodownInventory for this godown and product
            available_inventory = GodownInventory.objects.filter(
                godown=godown,
                product=product,
                status='ACTIVE'
            ).aggregate(
                total_available=Sum('good_bags_available')
            )['total_available'] or 0

            if requested_bags > available_inventory:
                raise ValidationError(
                    f"Cannot request {requested_bags} bags of {product.name}. "
                    f"Only {available_inventory} bags are available in {godown.name} inventory."
                )

        # Validation: loaded bags should not exceed requested bags by more than reasonable margin
        if loaded_bags > requested_bags * 1.1:  # Allow 10% overage
            raise ValidationError(
                f"Loaded bags ({loaded_bags}) seems too high compared to requested bags ({requested_bags}). "
                f"Please double-check the numbers."
            )

        # Validation: loaded bags cannot exceed available inventory either
        if godown and product and loaded_bags > 0:
            # Get total available bags from GodownInventory for this godown and product
            available_inventory = GodownInventory.objects.filter(
                godown=godown,
                product=product,
                status='ACTIVE'
            ).aggregate(
                total_available=Sum('good_bags_available')
            )['total_available'] or 0

            if loaded_bags > available_inventory:
                raise ValidationError(
                    f"Cannot load {loaded_bags} bags of {product.name}. "
                    f"Only {available_inventory} bags are available in {godown.name} inventory."
                )

        # Warning for significant under-loading
        if loaded_bags < requested_bags * 0.8 and loaded_bags > 0:  # Less than 80% of requested
            # This is just a validation, but we'll allow it
            pass

        return cleaned_data
