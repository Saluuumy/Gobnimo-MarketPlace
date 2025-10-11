# models.py
from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.utils import timezone
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from cloudinary.models import CloudinaryField

class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(email, password, **extra_fields)

class User(AbstractUser):
    # Remove username and first/last name fields
    username = None
    first_name = None  # Explicitly remove first_name
    last_name = None   # Explicitly remove last_name
    
    full_name = models.CharField(
        _('full name'), 
        max_length=200, 
        blank=True, 
        help_text="Enter your full name as you want it displayed"
    )
    email = models.EmailField(_('email address'), max_length=200, unique=True)
    bio = models.TextField(_('bio'), null=True, blank=True)
    phone_number = models.CharField(
        _('phone number'), 
        max_length=15, 
        null=True, 
        blank=True, 
        unique=True
    )
    avatar = models.ImageField(
        _('avatar'), 
        null=True, 
        blank=True, 
        default="avatar.svg"
    )
    location = models.CharField(
        _('location'), 
        max_length=255, 
        blank=True, 
        help_text="City or region (e.g., Hargeisa)"
    )
    email_verified = models.BooleanField(_('email verified'), default=False)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS =  ['full_name']

    objects = CustomUserManager()

    def __str__(self):
        return self.email

    def get_full_name(self):
        """Return the user's full name."""
        return self.full_name.strip() if self.full_name else self.email.split('@')[0]

    def get_short_name(self):
        """Return the short name for the user."""
        if self.full_name:
            return self.full_name.split()[0]
        return self.email.split('@')[0]

    # Seller Rating Methods
    def get_seller_stats(self):
        """Get or create seller statistics for this user"""
        from django.db import transaction
        
        with transaction.atomic():
            stats, created = SellerStats.objects.get_or_create(user=self)
            if created:
                stats.update_stats()
            return stats
    
    def get_average_rating(self):
        """Get average rating as float"""
        stats = self.get_seller_stats()
        return float(stats.average_rating)
    
    def get_rating_count(self):
        """Get total number of ratings"""
        stats = self.get_seller_stats()
        return stats.total_ratings
    
    def can_rate_seller(self, rater):
        """Check if a user can rate this seller"""
        if self == rater:
            return False  # Can't rate yourself
        
        # Optional: Check if user has previously interacted with this seller
        # For example, check if they've messaged each other or completed a transaction
        # This is a placeholder for future business logic
        
        # For now, we'll allow any user to rate any seller
        return True
    
    def get_recent_ratings(self, limit=5):
        """Get recent ratings for this seller"""
        return SellerRating.objects.filter(seller=self).select_related('rater').order_by('-created_at')[:limit]
    
    def has_rated_seller(self, seller):
        """Check if this user has rated a specific seller"""
        if not self.is_authenticated:
            return False
        return SellerRating.objects.filter(seller=seller, rater=self).exists()
    
    def get_rating_for_seller(self, seller):
        """Get this user's rating for a specific seller if it exists"""
        try:
            return SellerRating.objects.get(seller=seller, rater=self)
        except SellerRating.DoesNotExist:
            return None
    
    def get_rating_distribution(self):
        """Get distribution of ratings (how many of each star rating)"""
        from django.db.models import Count
        return (
            SellerRating.objects
            .filter(seller=self)
            .values('rating')
            .annotate(count=Count('rating'))
            .order_by('rating')
        )
    
    def get_positive_rating_percentage(self, threshold=4):
        """Get percentage of ratings that are positive (>= threshold)"""
        total_ratings = self.get_rating_count()
        if total_ratings == 0:
            return 0
        
        positive_ratings = SellerRating.objects.filter(
            seller=self, 
            rating__gte=threshold
        ).count()
        
        return (positive_ratings / total_ratings) * 100
    
    def is_trusted_seller(self, min_ratings=5, min_rating=4.0):
        """Check if this user meets criteria to be considered a trusted seller"""
        if self.get_rating_count() < min_ratings:
            return False
        return self.get_average_rating() >= min_rating
    
    def get_seller_level(self):
        """Get seller level based on ratings and performance"""
        avg_rating = self.get_average_rating()
        rating_count = self.get_rating_count()
        
        if rating_count == 0:
            return "New Seller"
        elif rating_count < 3:
            return "Beginner Seller"
        elif avg_rating >= 4.8 and rating_count >= 10:
            return "Top Rated Seller"
        elif avg_rating >= 4.5 and rating_count >= 5:
            return "Rated Seller"
        elif avg_rating >= 4.0:
            return "Reliable Seller"
        else:
            return "Seller"
class Category(models.Model):
    ICON_CHOICES = [
        ('building', 'Property'),
        ('land', 'Lands'),
        ('electronics', 'Electronics'),
        ('fashion', 'Fashion'),
        ('car', 'Vehicles'),
        ('wrench', 'Services'),
        ('briefcase', 'Jobs'),
        ('scissors', 'Beauty & Salons'),
        ('paint-brush', 'Decoration'),
    ]
    
    name = models.CharField(max_length=100, unique=True)
    icon = models.CharField(max_length=20, choices=ICON_CHOICES, default='tag')
    # Keep image field for backward compatibility if needed

    def __str__(self):
        return self.name


class Ad(models.Model):
    # ----- Status and Types -----
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    )
    AD_TYPE_CHOICES = (
        ('sell', 'Sell'),
        ('rent', 'Rent'),
        ('exchange', 'Exchange'),
        ('service', 'Service'),
        ('job', 'Job'),
        ('other', 'Other'),
    )

    # ----- Property Choices -----
    FURNISHING_CHOICES = (
        ('fully_furnished', 'Fully Furnished'),
        ('semi_furnished', 'Semi Furnished'),
        ('unfurnished', 'Unfurnished'),
    )
    PROPERTY_TYPE_CHOICES = (
        ('apartment', 'Apartment'),
        ('house', 'House'),
        ('villa', 'Villa'),
        ('condo', 'Condo'),
        ('commercial', 'Commercial'),
        ('office', 'Office Space'),
        ('warehouse', 'Warehouse'),
        ('farmhouse', 'Farm House'),
    )
    LAND_TYPE_CHOICES = (
        ('residential', 'Residential'),
        ('agricultural', 'Agricultural'),
        ('commercial', 'Commercial'),
        ('industrial', 'Industrial'),
    )

    # ----- Vehicle Choices -----
    VEHICLE_TYPE_CHOICES = (
        ('car', 'Car'),
        ('motorcycle', 'Motorcycle'),
        ('bus', 'Bus'),
        ('truck', 'Truck'),
    )

    # ----- Electronics Choices -----
    ELECTRONICS_TYPE_CHOICES = (
        ('phone', 'Mobile Phone'),
        ('laptop', 'Laptop'),
        ('tablet', 'Tablet'),
        ('camera', 'Camera'),
        ('tv', 'TV'),
        ('audio', 'Audio Equipment'),
        ('gaming', 'Gaming Console'),
        ('smart_home', 'Smart Home Devices'),
    )
    OS_CHOICES = (
        ('android', 'Android'),
        ('ios', 'iOS'),
        ('windows', 'Windows'),
        ('other', 'Other'),
    )
    CONDITION_CHOICES = (
        ('new', 'New'),
        ('second_hand', 'Second Hand'),
    )
    SIM_TYPE_CHOICES = (
        ('single', 'Single SIM'),
        ('dual', 'Dual SIM'),
        ('e_sim', 'eSIM'),
    )

    # ----- Job Choices -----
    JOB_TYPE_CHOICES = (
        ('full_time', 'Full Time'),
        ('part_time', 'Part Time'),
        ('contract', 'Contract'),
        ('internship', 'Internship'),
        ('remote', 'Remote'),
    )

    # ----- Service Choices -----
    SERVICE_TYPE_CHOICES = (
        ('cleaning', 'Cleaning'),
        ('moving', 'Moving & Storage'),
        ('repair', 'Repair & Maintenance'),
        ('it', 'IT Services'),
        ('beauty', 'Beauty & Wellness'),
        ('tutoring', 'Tutoring & Lessons'),
    )

    # ----- Fashion Choices -----
    FASHION_TYPE_CHOICES = (
        ('men', "Men's Fashion"),
        ('women', "Women's Fashion"),
        ('kids', "Kids' Fashion"),
        ('watches', 'Watches'),
        ('jewelry', 'Jewelry'),
        ('bags', 'Bags & Accessories'),
    )

    # ----- Core Ad Fields -----
    advertiser = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    location = models.CharField(max_length=255)
    ad_type = models.CharField(
        max_length=10,
        choices=AD_TYPE_CHOICES,
        default='sell'
    )
    description = models.TextField(blank=True)
    views = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)
    

    # ----- Common Item Fields -----
    model = models.CharField(max_length=100, blank=True, null=True)
    color = models.CharField(max_length=50, blank=True, null=True)
    year = models.PositiveIntegerField(blank=True, null=True)

    # ----- Property-Specific -----
    num_rooms = models.PositiveIntegerField(
        blank=True, null=True,
        help_text="Whole numbers only (e.g. 3)"
    )
    num_baths = models.PositiveIntegerField(
        blank=True, null=True,
        help_text="Whole numbers only (e.g. 2)"
    )
    area_size  = models.PositiveIntegerField(
        blank=True, null=True,
        help_text="Whole numbers only (e.g. 2)"
    )
    furnishing_type = models.CharField(
        max_length=20, choices=FURNISHING_CHOICES,
        blank=True, null=True
    )
    property_type = models.CharField(
        max_length=20, choices=PROPERTY_TYPE_CHOICES,
        blank=True, null=True
    )
    has_parking = models.BooleanField(default=False)
    has_pool = models.BooleanField(default=False)
    has_water = models.BooleanField(default=False)
    has_electricity = models.BooleanField(default=False)
  

    # ----- Land-Specific -----
    land_type = models.CharField(
        max_length=20, choices=LAND_TYPE_CHOICES,
        blank=True, null=True
    )
    land_area = models.PositiveIntegerField(
        blank=True, null=True,
        help_text="Whole numbers only (e.g. 0.5)"
    )
    
   

    # ----- Vehicle-Specific -----
    vehicle_type = models.CharField(
        max_length=20, choices=VEHICLE_TYPE_CHOICES,
        blank=True, null=True
    )
    motortype = models.CharField(max_length=100, blank=True, null=True)
    geartype = models.CharField(max_length=100, blank=True, null=True)
    is_automatic = models.BooleanField(default=False)

    

    # ----- Electronics-Specific -----
    electronics_type = models.CharField(
        max_length=20, choices=ELECTRONICS_TYPE_CHOICES,
        blank=True, null=True
    )
    operating_system = models.CharField(
        max_length=20, choices=OS_CHOICES,
        blank=True, null=True
    )
    storage_capacity = models.CharField(max_length=20, blank=True, null=True)
    screen_size = models.DecimalField(
        max_digits=5, decimal_places=2,
        blank=True, null=True,
        help_text="Screen size in inches"
    )
    ram = models.CharField(max_length=20, blank=True, null=True)
    processor = models.CharField(max_length=100, blank=True, null=True)
    camera_resolution = models.CharField(max_length=50, blank=True, null=True)
    electronics_condition = models.CharField(
        max_length=20, choices=CONDITION_CHOICES,
        blank=True, null=True
    )
    has_warranty = models.BooleanField(default=False)
    warranty_period = models.CharField(max_length=50, blank=True, null=True)
    sim_type = models.CharField(
        max_length=20, choices=SIM_TYPE_CHOICES,
        blank=True, null=True
    )

    # ----- Job-Specific -----
    job_type = models.CharField(
        max_length=20, choices=JOB_TYPE_CHOICES,
        blank=True, null=True
    )
    salary = models.CharField(max_length=100, blank=True, null=True)
    experience_required = models.CharField(max_length=100, blank=True, null=True)
    education_required = models.CharField(max_length=100, blank=True, null=True)

    # ----- Service-Specific -----
    service_type = models.CharField(
        max_length=20, choices=SERVICE_TYPE_CHOICES,
        blank=True, null=True
    )
    service_area = models.CharField(max_length=255, blank=True, null=True)
    availability = models.CharField(max_length=100, blank=True, null=True)

    # ----- Fashion-Specific -----
    fashion_type = models.CharField(
        max_length=20, choices=FASHION_TYPE_CHOICES,
        blank=True, null=True
    )
    size = models.CharField(max_length=20, blank=True, null=True)
    material = models.CharField(max_length=100, blank=True, null=True)

    # ----- Metadata -----
    is_approved = models.BooleanField(default=False)
    is_featured = models.BooleanField(default=False)
    status = models.CharField(
        max_length=10, choices=STATUS_CHOICES,
        default='pending'
    )

    def __str__(self):
        return f"{self.name} - {self.get_ad_type_display()} ({self.location})"

    def increment_views(self):
        self.views = models.F('views') + 1
        self.save(update_fields=['views'])

    def is_currently_featured(self):
        return hasattr(self, 'featuredad') and self.featuredad.is_active()
    class Meta:
        
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=["is_featured"]),
            models.Index(fields=["status"]),
            models.Index(fields=["ad_type"]),
            models.Index(fields=["category"]),
            models.Index(fields=["price"]),
            models.Index(fields=["created_at"]),
        ]


class FeaturedAd(models.Model):
    ad = models.OneToOneField(Ad, on_delete=models.CASCADE, related_name='featuredad')
    payment_screenshot = models.ImageField(upload_to='payment_screenshots/')
    featured_start_date = models.DateTimeField(default=timezone.now)
    featured_expiry_date = models.DateTimeField()

    def save(self, *args, **kwargs):
        if not self.ad.is_approved:
            raise ValueError(f"Cannot create FeaturedAd for unapproved ad: {self.ad.name}")
        super().save(*args, **kwargs)

    def is_active(self):
        now = timezone.now()
        return self.featured_start_date <= now <= self.featured_expiry_date

    def __str__(self):
        return f"{self.ad.name} featured until {self.featured_expiry_date}"

class FeaturedAdHistory(models.Model):
    ad = models.ForeignKey(Ad, on_delete=models.CASCADE, related_name='featured_history')
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2)
    payment_screenshot = models.ImageField(upload_to='payment_screenshots/')
    featured_date = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    def __str__(self):
        return f"{self.ad.name} featured until {self.expires_at}"

class PendingFeaturedAd(models.Model):
    ad = models.OneToOneField(Ad, on_delete=models.CASCADE, related_name='pending_featured')
    payment_screenshot = models.ImageField(upload_to='payment_screenshots/')
    featured_start_date = models.DateTimeField()
    featured_expiry_date = models.DateTimeField()

    def __str__(self):
        return f"Pending feature for {self.ad.name}"

class AdImage(models.Model):
    ad = models.ForeignKey(Ad, on_delete=models.CASCADE, related_name='images')
    image = CloudinaryField('image', blank=True, null=True)
    def __str__(self):
        return f"Image for {self.ad.name}"

class Comment(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    ad = models.ForeignKey(Ad, on_delete=models.CASCADE, related_name='comments')
    text = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    parent = models.ForeignKey('self', null=True, blank=True, on_delete=models.CASCADE, related_name='replies')

    def __str__(self):
        return f"Comment by {self.user.email} on {self.ad.name}"

class Notification(models.Model):
    NOTIFICATION_TYPES = (
        ('approval', 'Ad Approved'),
        ('rejection', 'Ad Rejected'),
        ('featured', 'Ad Featured'),
        ('info', 'Information'),
        ('warning', 'Warning'),
    )
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
    ad = models.ForeignKey('Ad', on_delete=models.CASCADE, null=True, blank=True, related_name='notifications')
    message = models.TextField()
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Notification'
        verbose_name_plural = 'Notifications'
    
    def __str__(self):
        return f"{self.get_notification_type_display()} - {self.user.email}"
    
    @property
    def status_color(self):
        colors = {
            'approval': 'green',
            'featured': 'purple',
            'rejection': 'red',
            'warning': 'yellow',
            'info': 'blue'
        }
        return colors.get(self.notification_type, 'gray')
    
class Favorite(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="favorites"
    )
    ad = models.ForeignKey(
        Ad,
        on_delete=models.CASCADE,
        related_name="favorited_by"
    )
    saved_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "ad")
        ordering = ["-saved_at"]

    def __str__(self):
        return f"{self.user.get_short_name()} → {self.ad.name}"
        
class SellerRating(models.Model):
    RATING_CHOICES = [
        (1, '1 Star - Poor'),
        (2, '2 Stars - Fair'),
        (3, '3 Stars - Good'),
        (4, '4 Stars - Very Good'),
        (5, '5 Stars - Excellent'),
    ]
    
    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='ratings_received'
    )
    rater = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='ratings_given'
    )
    rating = models.PositiveSmallIntegerField(choices=RATING_CHOICES)
    comment = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Optional: Reference to the ad that triggered the rating
    ad = models.ForeignKey(
        'Ad', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='ratings'
    )
    
    class Meta:
        unique_together = ['seller', 'rater']  # Prevent multiple ratings from same user
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['seller', 'created_at']),
            models.Index(fields=['rater', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.rater.get_short_name()} rated {self.seller.get_short_name()} - {self.rating} stars"
    
    def save(self, *args, **kwargs):
        """Override save to update seller stats"""
        super().save(*args, **kwargs)
        # Update seller stats
        self.seller.get_seller_stats().update_stats()
    
    def delete(self, *args, **kwargs):
        """Override delete to update seller stats"""
        seller = self.seller
        super().delete(*args, **kwargs)
        # Update seller stats
        seller.get_seller_stats().update_stats()

class SellerStats(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='seller_stats'
    )
    total_ratings = models.PositiveIntegerField(default=0)
    average_rating = models.DecimalField(max_digits=3, decimal_places=2, default=0.00)
    response_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    total_ads = models.PositiveIntegerField(default=0)
    last_updated = models.DateTimeField(auto_now=True)
    
    # Rating distribution (cached for performance)
    five_star_count = models.PositiveIntegerField(default=0)
    four_star_count = models.PositiveIntegerField(default=0)
    three_star_count = models.PositiveIntegerField(default=0)
    two_star_count = models.PositiveIntegerField(default=0)
    one_star_count = models.PositiveIntegerField(default=0)
    
    class Meta:
        verbose_name_plural = "Seller Stats"
        indexes = [
            models.Index(fields=['average_rating', 'total_ratings']),
        ]
    
    def __str__(self):
        return f"Stats for {self.user.get_short_name()}"
    
    def update_stats(self):
        """Update all seller statistics"""
        from django.db.models import Avg, Count, Q
        
        # Update rating stats
        ratings = SellerRating.objects.filter(seller=self.user)
        self.total_ratings = ratings.count()
        
        if self.total_ratings > 0:
            # Calculate average rating
            avg_result = ratings.aggregate(avg=Avg('rating'))
            self.average_rating = avg_result['avg'] or 0.00
            
            # Update rating distribution
            self.five_star_count = ratings.filter(rating=5).count()
            self.four_star_count = ratings.filter(rating=4).count()
            self.three_star_count = ratings.filter(rating=3).count()
            self.two_star_count = ratings.filter(rating=2).count()
            self.one_star_count = ratings.filter(rating=1).count()
        else:
            self.average_rating = 0.00
            self.five_star_count = 0
            self.four_star_count = 0
            self.three_star_count = 0
            self.two_star_count = 0
            self.one_star_count = 0
        
        # Update ad count (only approved ads)
        self.total_ads = Ad.objects.filter(
            advertiser=self.user, 
            status='approved'
        ).count()
        
        # Update response rate (you can implement this based on your messaging system)
        # For now, we'll set a placeholder or keep the existing value
        if not self.response_rate:
            # Simple heuristic based on ratings and ad count
            if self.total_ads > 0 and self.total_ratings > 0:
                self.response_rate = min(100, (self.total_ratings / self.total_ads) * 100)
            else:
                self.response_rate = 0.00
        
        self.save()
    
    def get_rating_percentage(self, star_rating):
        """Get percentage of a specific star rating"""
        if self.total_ratings == 0:
            return 0
        count = getattr(self, f'{star_rating}_star_count')
        return (count / self.total_ratings) * 100
    
    def get_positive_rating_percentage(self):
        """Get percentage of 4 and 5 star ratings"""
        if self.total_ratings == 0:
            return 0
        positive_count = self.four_star_count + self.five_star_count
        return (positive_count / self.total_ratings) * 100