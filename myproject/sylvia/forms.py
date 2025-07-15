from django import forms
from .models import Vehicle, Dealer, Product, Depot, Order, OrderItem


class VehicleForm(forms.ModelForm):
    """Form for adding and editing vehicle details"""
    
    class Meta:
        model = Vehicle
        fields = ['truck_number', 'owner_name', 'driver_name', 'driver_phone', 'capacity', 'vehicle_type', 'is_active']
        widgets = {
            'truck_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., CG15EA0464',
                'pattern': '[A-Z]{2}[0-9]{2}[A-Z]{1,2}[0-9]{4}',
                'title': 'Enter valid truck number format (e.g., CG15EA0464)'
            }),
            'owner_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Vehicle owner name'
            }),
            'driver_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Driver name'
            }),
            'driver_phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Driver phone number',
                'pattern': '[0-9]{10,15}',
                'title': 'Enter valid phone number'
            }),
            'capacity': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Capacity in MT',
                'step': '0.01',
                'min': '0'
            }),
            'vehicle_type': forms.Select(attrs={
                'class': 'form-control'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            })
        }
        labels = {
            'truck_number': 'Truck Number',
            'owner_name': 'Owner Name',
            'driver_name': 'Driver Name',
            'driver_phone': 'Driver Phone',
            'capacity': 'Capacity (MT)',
            'vehicle_type': 'Vehicle Type',
            'is_active': 'Active'
        }

    def clean_truck_number(self):
        truck_number = self.cleaned_data.get('truck_number')
        if truck_number:
            truck_number = truck_number.upper()
            # Check for duplicates (excluding current instance if editing)
            if self.instance.pk:
                if Vehicle.objects.exclude(pk=self.instance.pk).filter(truck_number=truck_number).exists():
                    raise forms.ValidationError("A vehicle with this truck number already exists.")
            else:
                if Vehicle.objects.filter(truck_number=truck_number).exists():
                    raise forms.ValidationError("A vehicle with this truck number already exists.")
        return truck_number

    def clean_capacity(self):
        capacity = self.cleaned_data.get('capacity')
        if capacity is not None and capacity < 0:
            raise forms.ValidationError("Capacity cannot be negative.")
        return capacity


class DealerForm(forms.ModelForm):
    """Form for adding and editing dealer details"""
    
    class Meta:
        model = Dealer
        fields = ['name', 'code', 'contact_person', 'phone', 'whatsapp_number', 'email', 
                 'address', 'city', 'state', 'pincode', 'gstin', 'credit_limit', 'credit_days', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'code': forms.TextInput(attrs={'class': 'form-control'}),
            'contact_person': forms.TextInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'pattern': '[0-9]{10,15}'}),
            'whatsapp_number': forms.TextInput(attrs={'class': 'form-control', 'pattern': '[0-9]{10,15}'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'city': forms.TextInput(attrs={'class': 'form-control'}),
            'state': forms.TextInput(attrs={'class': 'form-control'}),
            'pincode': forms.TextInput(attrs={'class': 'form-control', 'pattern': '[0-9]{6}'}),
            'gstin': forms.TextInput(attrs={'class': 'form-control'}),
            'credit_limit': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'credit_days': forms.NumberInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'})
        }


class ProductForm(forms.ModelForm):
    """Form for adding and editing product details"""
    
    class Meta:
        model = Product
        fields = ['name', 'code', 'description', 'unit', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'code': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'unit': forms.TextInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'})
        }


class DepotForm(forms.ModelForm):
    """Form for adding and editing depot details"""
    
    class Meta:
        model = Depot
        fields = ['name', 'code', 'address', 'city', 'state', 'pincode', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'code': forms.TextInput(attrs={'class': 'form-control'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'city': forms.TextInput(attrs={'class': 'form-control'}),
            'state': forms.TextInput(attrs={'class': 'form-control'}),
            'pincode': forms.TextInput(attrs={'class': 'form-control', 'pattern': '[0-9]{6}'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'})
        }