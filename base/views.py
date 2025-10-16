from django.shortcuts import render, redirect, get_object_or_404
from .models import Category, AdImage, Ad, User, Comment, FeaturedAd, FeaturedAdHistory, PendingFeaturedAd, Notification, Favorite ,SellerRating, SellerStats
from .forms import AdForm, SignupForm, LoginForm, AuthenticationForm, CommentForm, AdPaidForm, UserProfileForm
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.http import JsonResponse, HttpResponseBadRequest
from django_ratelimit.decorators import ratelimit
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.conf import settings
from django.http import JsonResponse
from django.utils.encoding import force_bytes
from .forms import RatingForm
from django.db.models import Avg, Count
from django.views.decorators.http import require_POST
from django.contrib.auth.views import PasswordResetView
from django.core.mail import send_mail
from django.contrib.auth.tokens import default_token_generator
from django.urls import reverse
import logging
from django.utils import timezone
from datetime import timedelta
from django.db.models import Prefetch
from allauth.socialaccount.models import SocialAccount
from django.http import HttpResponse
from django.contrib import messages
from django.db.models import Q
from django.views.decorators.http import require_http_methods
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils.html import strip_tags
import smtplib
from django.core.paginator import Paginator
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import DetailView
from django.db.models import F
from django.db.models import Q, Count
from django.core.paginator import Paginator
import re
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

def signup(request):
    if request.method == 'POST':
        form = SignupForm(request.POST, request.FILES)
        
        if form.is_valid():
            try:
                user = form.save(commit=False)
                user.username = form.cleaned_data['email']
                user.is_active = False
                user.email_verified = False
                user.save()

                # Send verification email
                token = default_token_generator.make_token(user)
                uid = urlsafe_base64_encode(force_bytes(user.pk))
                verification_url = request.build_absolute_uri(
                    reverse('verify_email', kwargs={'uidb64': uid, 'token': token})
                )

                # Render HTML email content
                html_content = render_to_string('base/verification_email.html', {
                    'verification_url': verification_url,
                    'user': user,
                })
                text_content = strip_tags(html_content)

                # Send email using Django's send_mail
                try:
                    send_mail(
                        'Verify Your Email - Gobonimo Marketplace',
                        text_content,
                        settings.DEFAULT_FROM_EMAIL,
                        [user.email],
                        html_message=html_content,
                        fail_silently=False,
                    )
                    
                    # Log successful registration
                    logger.info(f"New user registered: {user.email} (ID: {user.id})")
                    
                    # Add success message for the next page
                    messages.success(request, f"Verification email sent to {user.email}. Please check your inbox.")
                    return render(request, 'base/verification_sent.html')
                    
                except Exception as e:
                    logger.error(f"Failed to send verification email to {user.email}: {e}")
                    
                    # Fallback to console email backend for debugging
                    if settings.DEBUG:
                        from django.core.mail.backends.console import EmailBackend
                        backend = EmailBackend()
                        backend.send_messages([EmailMultiAlternatives(
                            'Verify Your Email - Gobonimo Marketplace',
                            text_content,
                            settings.DEFAULT_FROM_EMAIL,
                            [user.email],
                            alternatives=[(html_content, 'text/html')]
                        )])
                        messages.success(request, f"Verification email sent to {user.email}. Please check your inbox.")
                        return render(request, 'base/verification_sent.html')
                    else:
                        # Delete the user if email sending fails in production
                        user.delete()
                        messages.error(request, 
                            "We encountered an issue sending the verification email. "
                            "Please try again later or contact support if the problem persists."
                        )
                        return render(request, 'base/signup.html', {'form': form})
                        
            except Exception as e:
                logger.error(f"Error during user registration: {e}")
                messages.error(request, 
                    "An unexpected error occurred during registration. "
                    "Please try again or contact support if the problem continues."
                )
                return render(request, 'base/signup.html', {'form': form})
                
        else:
            # Let the form handle its own error messages
            # The form errors will be displayed in the template automatically
            logger.warning(f"Form validation failed: {form.errors}")
            
    else:
        form = SignupForm()
    
    return render(request, 'base/signup.html', {'form': form})

def verify_email(request, uidb64, token):
    try:
        uid = urlsafe_base64_decode(uidb64).decode()
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None
    if user is not None and default_token_generator.check_token(user, token):
        user.is_active = True
        user.email_verified = True
        user.save()
        return render(request, 'base/verification_success.html')
    return render(request, 'base/verification_failed.html')


class CustomPasswordResetView(PasswordResetView):
    template_name = 'base/auth/custom_reset.html'
    
    def form_valid(self, form):
        # Add custom logic here
        return super().form_valid(form)
@require_http_methods(["GET", "POST"])
def login_view(request):
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            password = form.cleaned_data['password']
            user = authenticate(request, email=email, password=password)
            if user is not None:
                if user.email_verified and user.is_active:
                    login(request, user)
                    return redirect('index')  # Redirect to home page
                elif not user.email_verified:
                    form.add_error(None, "Please verify your email before logging in.")
                else:
                    form.add_error(None, "Your account is inactive. Contact support.")
            else:
                form.add_error(None, "Invalid email or password.")
        return render(request, 'base/login.html', {'form': form})
    else:
        form = LoginForm()
    return render(request, 'base/login.html', {'form': form})

def logout_user(request):
    logout(request)
    return redirect('index')

def index(request):
    # Get featured ads
    featured_ads = Ad.objects.filter(
        status='approved',  # Use status instead of is_approved
        featuredad__featured_start_date__lte=timezone.now(),
        featuredad__featured_expiry_date__gte=timezone.now()
    ).prefetch_related('images')
    
    # Get all categories with approved ads
    categories = Category.objects.annotate(
        approved_ads_count=Count('ad', filter=Q(ad__status='approved'))
    ).prefetch_related(
        Prefetch(
            'ad_set',
            queryset=Ad.objects.filter(status='approved').order_by('-created_at')[:20],  # Show 20 ads
            to_attr='approved_ads'
        )
    )
    
    return render(request, 'base/index.html', {
        'categories': categories,
        'featured_products': featured_ads,
    })
def category_detail(request, category_id):
    """
    View to display all ads for a specific category, grouped by their type fields
    """
    category = get_object_or_404(Category, id=category_id)
    categories = Category.objects.all()

    # Get approved ads for this specific category
    ads = Ad.objects.filter(
        category=category, 
        status='approved'
    ).select_related('category').prefetch_related('images').order_by('-created_at')
    
    # Group ads by their type based on the category
    subcategories = group_ads_by_type(category.name, ads)
    
    context = {
        'category': category,
        'ads': ads,
        'subcategories': subcategories,
        'categories': categories,
    }
    return render(request, 'base/category_detail.html', context)

def group_ads_by_type(category_name, ads):
    """
    Group ads by their specific type fields based on category
    """
    if not ads:
        return {}
    
    subcategories = {}
    
    # Map category names to their respective type fields and choices
    category_type_mapping = {
        'Vehicles': {
            'field': 'vehicle_type',
            'choices': dict(Ad.VEHICLE_TYPE_CHOICES),
            'default_name': 'Other Vehicles'
        },
        'Electronics': {
            'field': 'electronics_type', 
            'choices': dict(Ad.ELECTRONICS_TYPE_CHOICES),
            'default_name': 'Other Electronics'
        },
        'Property': {
            'field': 'property_type',
            'choices': dict(Ad.PROPERTY_TYPE_CHOICES),
            'default_name': 'Other Property'
        },
        'Lands': {
            'field': 'land_type',
            'choices': dict(Ad.LAND_TYPE_CHOICES),
            'default_name': 'Other Land'
        },
        'Fashion': {
            'field': 'fashion_type',
            'choices': dict(Ad.FASHION_TYPE_CHOICES),
            'default_name': 'Other Fashion'
        },
        'Services': {
            'field': 'service_type',
            'choices': dict(Ad.SERVICE_TYPE_CHOICES),
            'default_name': 'Other Services'
        },
        'Jobs': {
            'field': 'job_type',
            'choices': dict(Ad.JOB_TYPE_CHOICES),
            'default_name': 'Other Jobs'
        },
        'Beauty & Salons': {
            'field': 'service_type',  # Beauty services use service_type
            'choices': dict(Ad.SERVICE_TYPE_CHOICES),
            'default_name': 'Other Beauty Services'
        },
        'Decoration': {
            'field': 'service_type',  # Decoration might use service_type or other
            'choices': dict(Ad.SERVICE_TYPE_CHOICES),
            'default_name': 'Other Decoration'
        }
    }
    
    # Get the type configuration for this category
    type_config = category_type_mapping.get(category_name)
    
    if not type_config:
        return {}  # No type grouping for this category
    
    field_name = type_config['field']
    choices = type_config['choices']
    default_name = type_config['default_name']
    
    # Initialize subcategories with all possible choices
    for choice_value, choice_name in choices.items():
        subcategories[choice_name] = []
    
    # Add the default category for items without a type
    subcategories[default_name] = []
    
    # Group ads by their type
    for ad in ads:
        type_value = getattr(ad, field_name)
        
        if type_value and type_value in choices:
            type_name = choices[type_value]
            subcategories[type_name].append(ad)
        else:
            # No type specified or invalid type
            subcategories[default_name].append(ad)
    
    # Remove empty subcategories
    subcategories = {k: v for k, v in subcategories.items() if v}
    
    return subcategories

def get_subcategories_for_category(category_name, ads):
    """
    Dynamically determine subcategories based on the main category
    """
    subcategory_config = {
        'Vehicles': {
            'Cars': ['car', 'sedan', 'hatchback', 'suv', 'coupe', 'jeep', 'vehicle', 'auto', 'automobile'],
            'Motorcycles': ['motorcycle', 'bike', 'scooter', 'motorbike', 'yamaha', 'honda', 'kawasaki'],
            'Buses & Vans': ['bus', 'coaster', 'minibus', 'van', 'minivan', 'transport'],
            'Trucks': ['truck', 'lorry', 'pickup', 'pick-up', 'isuzu', 'nissan'],
            'Other Vehicles': []
        },
        'Electronics': {
            'Phones': ['phone', 'smartphone', 'iphone', 'samsung', 'huawei', 'techno', 'infinix'],
            'Laptops': ['laptop', 'notebook', 'macbook', 'dell', 'hp', 'lenovo'],
            'TVs': ['tv', 'television', 'smart tv', 'led', 'oled'],
            'Audio': ['headphone', 'earphone', 'speaker', 'sound', 'airpods'],
            'Other Electronics': []
        },
        'Property': {
            'Apartments': ['apartment', 'flat', 'studio'],
            'Houses': ['house', 'bungalow', 'mansion', 'villa'],
            'Commercial': ['office', 'shop', 'store', 'commercial'],
            'Land': ['land', 'plot', 'acre'],
            'Other Property': []
        },
    }
    
    # Get the subcategory mapping for this category, or return empty if no mapping
    category_mapping = subcategory_config.get(category_name, {})
    
    # If no subcategories defined for this category, return empty dict
    if not category_mapping:
        return {}
    
    # Initialize subcategories
    subcategories = {subcat_name: [] for subcat_name in category_mapping.keys()}
    
    # Group ads into subcategories
    for ad in ads:
        ad_name_lower = ad.name.lower()
        ad_description_lower = getattr(ad, 'description', '').lower()
        
        # Combine name and description for better matching
        search_text = ad_name_lower + " " + ad_description_lower
        matched = False
        
        for subcat_name, keywords in category_mapping.items():
            if subcat_name == 'Other Vehicles' or subcat_name.startswith('Other'):
                continue  # Skip "Other" category during initial matching
                
            if any(keyword in search_text for keyword in keywords):
                subcategories[subcat_name].append(ad)
                matched = True
                break
        
        # If no match found, put in "Other" category
        if not matched:
            # Find the "Other" category for this main category
            other_key = next((key for key in category_mapping.keys() if 'Other' in key), None)
            if other_key:
                subcategories[other_key].append(ad)
            else:
                # If no "Other" category, put in the first available subcategory
                first_key = next(iter(category_mapping.keys()))
                subcategories[first_key].append(ad)
    
    # Remove empty subcategories
    subcategories = {k: v for k, v in subcategories.items() if v}
    
    return subcategories

def handle_redirect(request, category_id):
    """
    Redirect to the category detail page
    This is the function your sidebar is currently using
    """
    return category_detail(request, category_id)
def menu(request):
    # Get approved ads that are currently featured
    featured_ads = Ad.objects.filter(
        is_approved=True,
        featuredad__featured_start_date__lte=timezone.now(),
        featuredad__featured_expiry_date__gte=timezone.now()
    ).prefetch_related('featuredad')

    # Handle 'is_paid' from GET parameters
    is_paid = request.GET.get('is_paid', 'false').lower() == 'true'
    request.session['is_paid'] = is_paid

    # Get all categories with approved ads count
    categories = Category.objects.annotate(
        approved_ads_count=Count('ad', filter=Q(ad__is_approved=True))
    ).order_by('name')

    return render(
        request,
        'base/post_ad_categories.html',
        {
            'categories': categories,
            'featured_products': featured_ads,
        }
    )

def about_us(request):
    categories = Category.objects.all()
    return render(request, 'base/aboutus.html', {
       
        'categories': categories,
    })
logger = logging.getLogger(__name__)
@login_required(login_url='login')
def ad_form(request, category_id=None):   # <-- make category_id optional
       # If a category_id was provided in the URL, load that Category
    category = None
    if category_id is not None:
        category = get_object_or_404(Category, id=category_id)

    categories = Category.objects.all()
    show_success = False  # Default to False

    if request.method == 'POST':
        form = AdForm(request.POST, request.FILES)

        # If no category from the URL, try to read from hidden input in POST
        if category is None:
            posted_cat = request.POST.get('category')
            if posted_cat:
                try:
                    category = Category.objects.get(id=posted_cat)
                except Category.DoesNotExist:
                    category = None

        # If still no category, attach a non-field error so the template shows it
        if category is None:
            form.add_error(None, 'Please select a category for your ad.')

        if form.is_valid():
            try:
                # Save Ad
                ad = form.save(commit=False)
                ad.category = category
                ad.advertiser = request.user
                ad.is_approved = False
                ad.save()

                # Save images
                images = request.FILES.getlist('images')
                if images:
                    for img in images:
                        AdImage.objects.create(ad=ad, image=img)

                # Create PendingFeaturedAd
               

                messages.success(request, "Your digital masterpiece is now soaring through our approval cosmos!")
                show_success = True  # Set to True on success
                form = AdForm()  # Reset form
            except Exception as e:
                messages.error(request, f"Error: {str(e)}")
        else:
            messages.error(request, "Invalid form data. Please check fields.")
    else:
        form = AdForm()

    return render(request, 'base/upload.html', {
        'form': form,
        'category': category,
        'show_success': show_success,
        'categories': categories,
    })

@login_required(login_url='login')
def create_ad_form(request, category_id=None):   # <-- make category_id optional
    # If a category_id was provided in the URL, load that Category
    category = None
    if category_id is not None:
        category = get_object_or_404(Category, id=category_id)

    categories = Category.objects.all()
    show_success = False  # Default to False

    if request.method == 'POST':
        form = AdPaidForm(request.POST, request.FILES)

        # If no category from the URL, try to read from hidden input in POST
        if category is None:
            posted_cat = request.POST.get('category')
            if posted_cat:
                try:
                    category = Category.objects.get(id=posted_cat)
                except Category.DoesNotExist:
                    category = None

        # If still no category, attach a non-field error so the template shows it
        if category is None:
            form.add_error(None, 'Please select a category for your ad.')

        if form.is_valid():
            try:
                # Save Ad
                ad = form.save(commit=False)
                ad.category = category
                ad.advertiser = request.user
                ad.is_approved = False
                ad.save()

                # Save images
                images = request.FILES.getlist('images')
                if images:
                    for img in images:
                        AdImage.objects.create(ad=ad, image=img)

                # Create PendingFeaturedAd
                PendingFeaturedAd.objects.create(
                    ad=ad,
                    payment_screenshot=form.cleaned_data['payment_screenshot'],
                    featured_start_date=form.cleaned_data['featured_start_date'],
                    featured_expiry_date=form.cleaned_data['featured_expiry_date']
                )

                messages.success(request, "Your digital masterpiece is now soaring through our approval cosmos!")
                show_success = True  # Set to True on success
                form = AdPaidForm()  # Reset form
            except Exception as e:
                messages.error(request, f"Error: {str(e)}")
        else:
            messages.error(request, "Invalid form data. Please check fields.")
    else:
        form = AdPaidForm()

    return render(request, 'base/create_paid_ad.html', {
        'form': form,
        'category': category,
        'show_success': show_success,
        'categories': categories,
    })
@receiver(post_save, sender=Ad)
def handle_ad_approval(sender, instance, created, **kwargs):
    if not created and instance.is_approved:
        # Check if it already has a FeaturedAd
        if not hasattr(instance, 'featuredad'):
            try:
                pending = PendingFeaturedAd.objects.get(ad=instance)
                # Create FeaturedAd using the pending data
                FeaturedAd.objects.create(
                    ad=instance,
                    payment_screenshot=pending.payment_screenshot,
                    featured_start_date=pending.featured_start_date,
                    featured_expiry_date=pending.featured_expiry_date
                )
                # Create FeaturedAdHistory (optional)
                FeaturedAdHistory.objects.create(
                    ad=instance,
                    amount_paid=0.0,
                    payment_screenshot=pending.payment_screenshot,
                    expires_at=pending.featured_expiry_date
                )
                # Delete the pending ad
                pending.delete()
            except PendingFeaturedAd.DoesNotExist:
                pass

            
def handle_ad_redirect(request, subcategory_id):
    is_paid = request.session.get('is_paid', False)

    if is_paid:
        return redirect('create_ad_form', category_id=subcategory_id)
    else:
        return redirect('ad_form', category_id=subcategory_id)
    
@login_required(login_url='login')
def notification_center(request):
    categories = Category.objects.all()

    notifications = Notification.objects.filter(
        user=request.user
    ).order_by('-created_at')
    
    # Get unread IDs before marking as read
    unread_ids = list(notifications.filter(is_read=False).values_list('id', flat=True))
    
    # Pagination
    paginator = Paginator(notifications, 10)  # 10 per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Mark current page notifications as read
    Notification.objects.filter(id__in=unread_ids).update(is_read=True)
    
    # Add was_unread flag for styling
    for notification in page_obj:
        notification.was_unread = notification.id in unread_ids
    
    return render(request, 'base/notification_center.html', {'page_obj': page_obj ,'categories': categories,})

@login_required(login_url='login')
def delete_notification(request, pk):
    notification = get_object_or_404(
        Notification, 
        id=pk, 
        user=request.user
    )
    notification.delete()
    return redirect('notification_center')

@login_required(login_url='login')
def mark_all_read(request):
    Notification.objects.filter(
        user=request.user, 
        is_read=False
    ).update(is_read=True)
    return redirect('notification_center')

@login_required(login_url='login')
def toggle_favorite(request, ad_id):
    ad = get_object_or_404(Ad, pk=ad_id)
    user = request.user

    # Check if favorite exists
    favorite_exists = Favorite.objects.filter(user=user, ad=ad).exists()
    
    if favorite_exists:
        # Delete existing favorite
        Favorite.objects.filter(user=user, ad=ad).delete()
        favorited = False
    else:
        # Create new favorite
        Favorite.objects.create(user=user, ad=ad)
        favorited = True

    # Handle AJAX requests (for JavaScript fetch)
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({
            'favorited': favorited,
            'favorite_count': ad.favorited_by.count()
        })
    else:
        # Redirect to current page or ad detail
        return redirect(request.META.get('HTTP_REFERER', 'home'))  # Go back to previous page
 

@login_required(login_url='login')
def my_favorites(request):
    categories = Category.objects.all()
    # Get user's favorites with related ad data and prefetch images
    favorites = Favorite.objects.filter(user=request.user).select_related(
        'ad__category'
    ).prefetch_related(
        'ad__images'
    )
    

    # Create a set of favorited ad IDs for template checks
    user_favorites = set(favorites.values_list('ad_id', flat=True))
    categories = Category.objects.all()
    return render(request, 'base/favorites.html', {
        'favorites': favorites,
        'categories': categories,
        'user_favorites': user_favorites,
        
    })

def product_detail(request, ad_id):
    ad = get_object_or_404(Ad, pk=ad_id)
    categories = Category.objects.all()
    
    # Increment view count
    Ad.objects.filter(pk=ad.pk).update(views=F('views') + 1)
    
    # Get similar items
    similar_items = Ad.objects.filter(
        category=ad.category, 
        status='approved'
    ).exclude(id=ad.id).order_by('-created_at')[:6]
    
    # Get user's favorites if authenticated
    if request.user.is_authenticated:
        user_favorites = set(request.user.favorites.values_list('ad_id', flat=True))
        
        # Check if user has already rated this seller
        user_rating = None
        if request.user != ad.advertiser:
            try:
                user_rating = SellerRating.objects.get(
                    seller=ad.advertiser, 
                    rater=request.user
                )
            except SellerRating.DoesNotExist:
                user_rating = None
    else:
        user_favorites = set()
        user_rating = None
    
    # Get seller stats
    seller_stats = ad.advertiser.get_seller_stats()
    
    # Get recent ratings for this seller
    recent_ratings = SellerRating.objects.filter(
        seller=ad.advertiser
    ).select_related('rater').order_by('-created_at')[:5]
    
    # Rating form handling
    rating_form = RatingForm()
    if request.method == 'POST' and 'submit_rating' in request.POST:
        if not request.user.is_authenticated:
            messages.error(request, 'Please log in to rate this seller.')
            return redirect('login')
        
        if request.user == ad.advertiser:
            messages.error(request, 'You cannot rate yourself.')
        else:
            rating_form = RatingForm(request.POST)
            if rating_form.is_valid():
                # Check if user already rated this seller
                existing_rating = SellerRating.objects.filter(
                    seller=ad.advertiser,
                    rater=request.user
                ).first()
                
                if existing_rating:
                    # Update existing rating
                    existing_rating.rating = rating_form.cleaned_data['rating']
                    existing_rating.comment = rating_form.cleaned_data['comment']
                    existing_rating.save()
                    messages.success(request, 'Your rating has been updated.')
                else:
                    # Create new rating
                    rating = rating_form.save(commit=False)
                    rating.seller = ad.advertiser
                    rating.rater = request.user
                    rating.save()
                    messages.success(request, 'Thank you for your rating!')
                
                # Update seller stats
                seller_stats.update_stats()
                return redirect('product_detail', ad_id=ad_id)
    
    # Comment form handling (your existing code)
    if request.method == 'POST' and 'submit_comment' in request.POST:
        form = CommentForm(request.POST)
        if form.is_valid():
            comment = form.save(commit=False)
            comment.user = request.user
            comment.ad = ad
            comment.save()
            return redirect('product_detail', ad_id=ad_id)
    else:
        form = CommentForm()
        
    comments = Comment.objects.filter(ad=ad, parent=None)
    
    return render(request, 'base/ad_detail.html', {
        'ad': ad,
        'categories': categories,
        'form': form,
        'comments': comments,
        'user_favorites': user_favorites,
        'similar_items': similar_items,
        'seller_stats': seller_stats,
        'recent_ratings': recent_ratings,
        'rating_form': rating_form,
        'user_rating': user_rating,
    })
@login_required
def delete_rating(request, rating_id):
    rating = get_object_or_404(SellerRating, id=rating_id, rater=request.user)
    seller = rating.seller
    rating.delete()
    
    # Update seller stats
    seller_stats = seller.get_seller_stats()
    seller_stats.update_stats()
    
    messages.success(request, 'Your rating has been deleted.')
    return redirect('base/product_detail', ad_id=request.GET.get('next', ''))
def search_ads(request):
    # Get search parameters
    categories = Category.objects.all()
    keyword = request.GET.get('q', '').strip()
    location = request.GET.get('location', '').strip()
    category_id = request.GET.get('category', '').strip()
    
    # Start with approved ads only
    base_query = Ad.objects.filter(status='approved')
    ads = base_query
    has_exact = False
    has_similar = False
    
    # Extract state from location if possible
    state = None
    if location:
        state_match = re.search(r'\b([A-Z]{2})\b', location, re.IGNORECASE)
        state = state_match.group(1).upper() if state_match else None
    
    # Build dynamic filters for exact matches
    exact_filters = Q()
    
    # Keyword search (search multiple fields)
    if keyword:
        keyword_query = Q()
        for word in keyword.split():
            keyword_query |= (
                Q(name__icontains=word) |
                Q(description__icontains=word) |
                Q(motortype__icontains=word) |
                Q(geartype__icontains=word) |
                Q(color__icontains=word)
            )
        exact_filters &= keyword_query
    
    # Location search
    if location:
        location_query = Q()
        location_query |= Q(location__icontains=location)
        
        if state:
            location_query |= Q(location__icontains=state)
        
        exact_filters &= location_query
    
    # Category search (direct category only - no subcategories)
    if category_id:
        try:
            # Filter by direct category only
            exact_filters &= Q(category__id=category_id)
        except (ValueError, Category.DoesNotExist):
            # Handle invalid category IDs gracefully
            pass
    
    # Apply all filters for exact matches
    ads = base_query.filter(exact_filters).order_by('-is_featured', '-created_at')
    has_exact = ads.exists()
    
    # SIMILAR ADS - Only show same category vehicles
    similar_ads = base_query.none()
    if not has_exact or ads.count() < 5:
        similar_query = Q()
        
        # Maintain the same category filter for similar listings
        if category_id:
            try:
                # Filter by direct category only
                similar_query &= Q(category__id=category_id)
            except (ValueError, Category.DoesNotExist):
                pass
        
        # Keyword similarity (match any word)
        if keyword:
            keyword_similar = Q()
            for word in keyword.split()[:3]:  # Limit to first 3 words
                keyword_similar |= (
                    Q(name__icontains=word) |
                    Q(description__icontains=word)
                )
            similar_query &= keyword_similar
        
        # Apply similar query and exclude exact matches
        similar_ads = base_query.filter(similar_query).exclude(id__in=ads.values_list('id', flat=True))
        
        # Order by featured and date
        similar_ads = similar_ads.order_by('-is_featured', '-created_at')[:8]
        
        has_similar = similar_ads.exists()
    
    # Get category name if exists
    category_name = ""
    if category_id:
        try:
            category_name = Category.objects.get(id=category_id).name
        except (ValueError, Category.DoesNotExist):
            pass

    # Pagination
    paginator = Paginator(ads, 12)
    page_number = request.GET.get('page')
    page_ads = paginator.get_page(page_number)
    
    return render(request, 'base/search_results.html', {
        'ads': page_ads,
        'similar_ads': similar_ads,
        'keyword': keyword,
        'location': location,
        'categories': categories,
        'category_name': category_name,
        'has_exact': has_exact,
        'has_similar': has_similar,
        'has_results': has_exact or has_similar
    })

@login_required(login_url='login')
def add_comment(request, ad_id):
    ad = get_object_or_404(Ad, pk=ad_id)
    if request.method == 'POST':
        form = CommentForm(request.POST)
        if form.is_valid():
            comment = form.save(commit=False)
            comment.user = request.user
            comment.ad = ad
            comment.save()
            return redirect('product_detail', ad_id=ad_id)
    return redirect('product_detail', ad_id=ad_id)




def view_profile(request, username):
    user = get_object_or_404(User, username=username)
    ads = Ad.objects.filter(advertiser=user)
    return render(request, 'base/profile.html', {'user': user, 'ads': ads})


def view_advertiser_profile(request, username):
    user = User.objects.get(username=username)
    ads = Ad.objects.filter(advertiser=user)
    
    return render(request, 'base/view_advertiser_profile.html', {'advertiser': user, 'ads': ads})

@csrf_exempt
@login_required(login_url='login')
@require_http_methods(["DELETE"])
def delete_comment(request, comment_id):
    try:
        comment = Comment.objects.get(id=comment_id, user=request.user)
        comment.delete()
        return JsonResponse({'status': 'success'}, status=200)
    except Comment.DoesNotExist:
        return JsonResponse({'error': 'Comment not found or not authorized'}, status=403)


def product_list(request, category_id):
    category = get_object_or_404(Category, pk=category_id)
    categories = Category.objects.all()

    ads = Ad.objects.filter(category=category)
    return render(request, 'base/product_list.html', {'categories': categories,'category': category, 'ads': ads})

@login_required(login_url='login')
def deleteComment(request, pk):
    comment = Comment.objects.get(id=pk)

    if request.user != comment.user:
        return HttpResponse('Your are not allowed here!!')

    if request.method == 'POST':
        comment.delete()
        return redirect('index')
    return render(request, 'base/delete.html', {'obj': comment})

@login_required(login_url='login')
def reply_to_comment(request, comment_id):
    comment = get_object_or_404(Comment, id=comment_id)
    if request.method == 'POST':
        form = CommentForm(request.POST)
        if form.is_valid():
            reply = form.save(commit=False)
            reply.user = request.user
            reply.ad = comment.ad
            reply.parent = comment
            reply.save()
            return redirect('product_detail', ad_id=comment.ad.id)
    return redirect('product_detail', ad_id=comment.ad.id)

@login_required
def dashboard(request):
    user = request.user
    categories = Category.objects.all()
    ads = Ad.objects.filter(advertiser=user).order_by('-created_at')

    if request.method == 'POST':
        form = UserProfileForm(request.POST, request.FILES, instance=user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Your profile has been updated successfully!')
            return redirect('dashboard')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = UserProfileForm(instance=user)

    context = {
        'user': user,
        'ads': ads,
        'form': form,
    }
    return render(request, 'base/dashboard.html', {
    'categories': categories})
@login_required
def delete_ad(request, ad_id):
    ad = get_object_or_404(Ad, id=ad_id, advertiser=request.user)
    if request.method == 'POST':
        ad.delete()
        messages.success(request, 'Ad deleted successfully!')
        return redirect('dashboard')
    return redirect('dashboard')


class AdDetailView(DetailView):
    model = Ad
    template_name = 'ad_detail.html'
    context_object_name = 'ad'

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        Ad.objects.filter(pk=obj.pk).update(views=F('views') + 1)
        return obj
    


    