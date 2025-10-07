from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.forms import ModelForm, ClearableFileInput
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.contrib.auth.password_validation import validate_password
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
    password1 = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-input',
            'placeholder': 'Enter your password',
            'minlength': '8'
        }),
        label="Password",
        help_text="Password must be at least 8 characters long and contain letters and numbers."
    )
    password2 = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-input', 
            'placeholder': 'Confirm your password'
        }),
        label="Confirm Password"
    )

    class Meta:
        model = User
        fields = ['email', 'full_name', 'phone_number', 'bio', 'location', 'avatar']
        widgets = {
            'email': forms.EmailInput(attrs={
                'class': 'form-input',
                'placeholder': 'your@email.com',
                'autocomplete': 'email'
            }),
            'full_name': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'John Doe',
                'autocomplete': 'name'
            }),
            'phone_number': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': '+25212345678',
                'autocomplete': 'tel'
            }),
            'bio': forms.Textarea(attrs={
                'class': 'w-full py-3 pl-10 pr-3 border rounded-lg focus:border-cyan-400 h-24',
                'placeholder': 'Tell us about yourself...',
                'rows': 4,
                'style': 'background: var(--chip); color: #e6eef8; border-color: rgba(255,255,255,0.1);'
            }),
            'location': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'City, Country',
                'autocomplete': 'address-level2'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make email and full_name required
        self.fields['email'].required = True
        self.fields['full_name'].required = True
        self.fields['avatar'].required = False

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip().lower()
        
        if not email:
            raise ValidationError("Email address is required.")
        
        # Basic email format validation
        if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
            raise ValidationError("Please enter a valid email address.")
        
        # Check uniqueness
        if User.objects.filter(email=email).exists():
            raise ValidationError("An account with this email already exists. Please use a different email or try logging in.")
        
        return email

    def clean_full_name(self):
        full_name = self.cleaned_data.get('full_name', '').strip()
        
        if not full_name:
            raise ValidationError("Full name is required.")
        
        # Check minimum length
        if len(full_name) < 2:
            raise ValidationError("Full name must be at least 2 characters long.")
        
        # Check for reasonable length
        if len(full_name) > 100:
            raise ValidationError("Full name is too long. Maximum 100 characters allowed.")
        
        return full_name

    def clean_password1(self):
        password1 = self.cleaned_data.get('password1')
        
        if not password1:
            raise ValidationError("Password is required.")
        
        # Check minimum length
        if len(password1) < 8:
            raise ValidationError("Password must be at least 8 characters long.")
        
        # Check for at least one letter and one number
        if not re.search(r'[a-zA-Z]', password1):
            raise ValidationError("Password must contain at least one letter.")
        
        if not re.search(r'\d', password1):
            raise ValidationError("Password must contain at least one number.")
        
        return password1

    def clean_password2(self):
        password1 = self.cleaned_data.get('password1')
        password2 = self.cleaned_data.get('password2')
        
        if not password2:
            raise ValidationError("Please confirm your password.")
            
        if password1 and password2 and password1 != password2:
            raise ValidationError("Passwords don't match. Please enter the same password in both fields.")
        
        return password2

    def clean_phone_number(self):
        phone_number = self.cleaned_data.get('phone_number', '').strip()
        
        if not phone_number:
            return phone_number  # Optional field
        
        # Remove any spaces, dashes, parentheses, etc.
        cleaned_phone = re.sub(r'[\s\-\(\)]', '', phone_number)
        
        # Validate phone number format (international format)
        if not re.match(r'^\+\d{8,15}$', cleaned_phone):
            raise ValidationError(
                "Phone number must be in international format starting with '+' followed by 8-15 digits. "
                "Example: +25212345678"
            )
        
        # Check uniqueness
        query = User.objects.filter(phone_number=cleaned_phone)
        if self.instance and self.instance.pk:
            query = query.exclude(pk=self.instance.pk)
        
        if query.exists():
            raise ValidationError("This phone number is already registered.")
        
        return cleaned_phone

    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = self.cleaned_data['email']
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