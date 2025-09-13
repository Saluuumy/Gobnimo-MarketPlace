from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.forms import ModelForm, ClearableFileInput
from django.utils import timezone
from .models import Ad, User, Comment
import re
ALLOWED_EMAIL_DOMAINS = [
    'gmail.com',
    'outlook.com',
    'hotmail.com',
    'yahoo.com',
    'icloud.com',
]
class SignupForm(forms.ModelForm):
    password1 = forms.CharField(widget=forms.PasswordInput, label="Password")
    password2 = forms.CharField(widget=forms.PasswordInput, label="Confirm Password")

    class Meta:
        model = User
        fields = ['email', 'full_name', 'phone_number', 'bio', 'location', 'avatar']

    def clean_password2(self):
        password1 = self.cleaned_data.get('password1')
        password2 = self.cleaned_data.get('password2')
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError("Passwords don't match")
        return password2

    def clean_phone_number(self):
        phone_number = self.cleaned_data.get('phone_number')
        if phone_number:
            # Validate phone number format (e.g., +1234567890)
            if not re.match(r'^\+\d{8,15}$', phone_number):
                raise forms.ValidationError("Phone number must start with '+' followed by 8-15 digits (e.g., +25212345678).")
            # Check uniqueness (excluding current instance if editing)
            if User.objects.filter(phone_number=phone_number).exclude(id=self.instance.id).exists():
                raise forms.ValidationError("This phone number is already registered.")
        return phone_number

    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = self.cleaned_data['email']  # Set username to email
        user.set_password(self.cleaned_data['password1'])
        user.is_active = False
        user.email_verified = False
        if commit:
            user.save()
        return user

class LoginForm(forms.Form):
    email = forms.EmailField(
        label="Email",
        widget=forms.EmailInput(attrs={
            'class': 'mt-1 w-full p-2 bg-gray-700 border border-gray-600 rounded focus:outline-none focus:ring-2 focus:ring-yellow-500'
        })
    )
    password = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(attrs={
            'class': 'mt-1 w-full p-2 bg-gray-700 border border-gray-600 rounded focus:outline-none focus:ring-2 focus:ring-yellow-500'
        })
    )

class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ['text']
        widgets = {
            'text': forms.Textarea(attrs={
                'class': 'w-full p-2 border rounded text-sm',
                'rows': 3,
                'placeholder': 'Write your reply...'
            })
        }
class AdForm(ModelForm):
    """Form for free ads (admin approval required)."""
    images = forms.FileField(
        widget=ClearableFileInput(attrs={'multiple': False}),
        required=False,
        help_text="You may upload multiple product images."
    )

    class Meta:
        model = Ad
        fields = [
            'name', 'description', 'price', 'location', 'ad_type',
            'model', 'color', 'year',
            'num_rooms', 'num_baths', 'area_size', 'furnishing_type', 'property_type',
            'has_parking', 'has_pool', 'has_water', 'has_electricity',
            'land_type', 'land_area',
            'vehicle_type', 'motortype', 'geartype', 'is_automatic',
            'electronics_type', 'operating_system', 'storage_capacity', 'screen_size', 'ram',
            'processor', 'camera_resolution', 'electronics_condition', 'has_warranty',
            'warranty_period', 'sim_type',
            'job_type', 'salary', 'experience_required', 'education_required',
            'service_type', 'service_area', 'availability',
            'fashion_type', 'size', 'material',
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        category = getattr(self.instance, 'category', None)
        if category:
            name = category.name.lower()
            category_fields = {
                'property': ['num_rooms', 'num_baths', 'property_type', 'area_size'],
                'land': ['land_type', 'land_area'],
                'vehicle': ['vehicle_type', 'motortype', 'geartype', 'year', 'color'],
                'electronics': ['electronics_type', 'operating_system', 'storage_capacity', 'ram', 'processor'],
                'job': ['job_type', 'experience_required', 'education_required'],
                'service': ['service_type', 'service_area', 'availability'],
                'fashion': ['fashion_type', 'size', 'material'],
            }
            all_category_fields = set(f for fields in category_fields.values() for f in fields)
            
            # Set required fields
            for cat, fields in category_fields.items():
                if cat in name:
                    for fld in fields:
                        if fld in self.fields:
                            self.fields[fld].required = True
            
            # Hide irrelevant fields
            always = {'name', 'description', 'price', 'location', 'ad_type'}
            for fld in list(self.fields):
                if fld not in always and fld not in all_category_fields:
                    self.fields[fld].widget = forms.HiddenInput()
                    self.fields[fld].required = False

    def clean(self):
        cleaned = super().clean()
        ad_type = cleaned.get('ad_type')
        property_type = cleaned.get('property_type')
        
        # Fix: Check if property_type exists before accessing
        if ad_type == 'rent' and property_type == 'commercial':
            if not cleaned.get('area_size'):
                self.add_error('area_size', 'Area size is required for commercial properties')
        
        # Fix: Add validation for land type
        if cleaned.get('land_type') and not cleaned.get('land_area'):
            self.add_error('land_area', 'Land area is required when land type is specified')
        
        return cleaned


class AdPaidForm(ModelForm):
    """Form for paid ads (creates a PendingFeaturedAd request)."""
    featured_start_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date'}),
        help_text="When should the ad go live?",
    )
    featured_expiry_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date'}),
        help_text="When should the ad expire?",
    )
    payment_screenshot = forms.ImageField(
        help_text="Upload proof of payment (screenshot)."
    )
    images = forms.FileField(
        widget=ClearableFileInput(attrs={'multiple': False}),
        required=False,
        help_text="You may upload multiple product images."
    )

    class Meta:
        model = Ad
        fields = [
            'name', 'description', 'price', 'location', 'ad_type',
            'model', 'color', 'year',
            'num_rooms', 'num_baths', 'area_size', 'furnishing_type', 'property_type',
            'has_parking', 'has_pool', 'has_water', 'has_electricity',
            'land_type', 'land_area',
            'vehicle_type', 'motortype', 'geartype', 'is_automatic',
            'electronics_type', 'operating_system', 'storage_capacity', 'screen_size', 'ram', 
            'processor', 'camera_resolution', 'electronics_condition', 'has_warranty', 
            'warranty_period', 'sim_type',
            'job_type', 'salary', 'experience_required', 'education_required',
            'service_type', 'service_area', 'availability',
            'fashion_type', 'size', 'material',
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        category = getattr(self.instance, 'category', None)
        if category:
            name = category.name.lower()
            category_fields = {
                'property': ['num_rooms', 'num_baths', 'property_type', 'area_size'],
                'land': ['land_type', 'land_area'],
                'vehicle': ['vehicle_type', 'motortype', 'geartype', 'year', 'color'],
                'electronics': ['electronics_type', 'operating_system', 'storage_capacity', 'ram', 'processor'],
                'job': ['job_type', 'experience_required', 'education_required'],
                'service': ['service_type', 'service_area', 'availability'],
                'fashion': ['fashion_type', 'size', 'material'],
            }
            all_category_fields = set(f for fields in category_fields.values() for f in fields)
            
            for cat, fields in category_fields.items():
                if cat in name:
                    for fld in fields:
                        if fld in self.fields:
                            self.fields[fld].required = True
            
            always = {
                'name', 'description', 'price', 'location', 'ad_type', 
                'featured_start_date', 'featured_expiry_date', 'payment_screenshot'
            }
            for fld in list(self.fields):
                if fld not in always and fld not in all_category_fields:
                    self.fields[fld].widget = forms.HiddenInput()
                    self.fields[fld].required = False

    def clean(self):
        cleaned = super().clean()
        today = timezone.now().date()
        start = cleaned.get('featured_start_date')
        end = cleaned.get('featured_expiry_date')
        
        if start and start < today:
            self.add_error('featured_start_date', 'Start date cannot be in the past.')
        if end and start and end <= start:
            self.add_error('featured_expiry_date', 'Expiry must be after the start date.')
        if end and end <= today:
            self.add_error('featured_expiry_date', 'Expiry date must be in the future.')
        
        # FIX: Removed rental_duration reference (non-existent field)
        
        # FIX: Only validate if property_type exists
        if cleaned.get('property_type') and not cleaned.get('area_size'):
            self.add_error('area_size', 'Area size is required for properties')
        
        # FIX: Validate land fields
        if cleaned.get('land_type') and not cleaned.get('land_area'):
            self.add_error('land_area', 'Land area is required when land type is specified')
        
        return cleaned

class UserProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['full_name', 'email', 'bio', 'phone_number', 'location', 'avatar']
        widgets = {
            'bio': forms.Textarea(attrs={'rows': 4}),
        }