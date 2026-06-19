from django.shortcuts import render, redirect, get_object_or_404
from .models import Category, AdImage, Ad, User, Comment, FeaturedAd, FeaturedAdHistory, PendingFeaturedAd, Notification, Favorite, SellerRating, SellerStats
from .forms import AdForm, SignupForm, LoginForm, AuthenticationForm, CommentForm, AdPaidForm, UserProfileForm, CompleteProfileForm
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
from django.core.mail.backends.console import EmailBackend
import re
from django.template import TemplateDoesNotExist
from django.db import IntegrityError
from django.core.mail.message import EmailMultiAlternatives
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
import threading
import traceback


logger = logging.getLogger(__name__)


def send_email_in_thread(subject, text_content, html_content, from_email, recipient_email, user_id, debug=False):
    """Helper function to send email using SendGrid API in a separate thread."""
    try:
        if not settings.SENDGRID_API_KEY:
            raise ValueError("SENDGRID_API_KEY is not set")
        if not from_email:
            raise ValueError("DEFAULT_FROM_EMAIL is not set")

        logger.debug(f"Attempting to send email to {recipient_email} (ID: {user_id})")

        message = Mail(
            from_email=from_email,
            to_emails=recipient_email,
            subject=subject,
            plain_text_content=text_content,
            html_content=html_content
        )

        sg = SendGridAPIClient(settings.SENDGRID_API_KEY)
        response = sg.send(message)
        if response.status_code != 202:
            raise Exception(f"SendGrid returned status code {response.status_code}: {response.body}")

        logger.info(f"Verification email sent successfully to {recipient_email} (ID: {user_id})")
    except Exception as e:
        logger.error(f"Failed to send verification email to {recipient_email}: {str(e)}\n{traceback.format_exc()}")
        if debug:
            try:
                backend = EmailBackend()
                email = EmailMultiAlternatives(
                    subject, text_content, from_email, [recipient_email],
                    alternatives=[(html_content, 'text/html')]
                )
                backend.send_messages([email])
                logger.info(f"Console backend used for verification email to {recipient_email}")
            except Exception as e:
                logger.error(f"Console backend failed for {recipient_email}: {str(e)}\n{traceback.format_exc()}")


# ── STEP 1 — SIGNUP ───────────────────────────────────────────────────────────
def signup(request):
    if request.method == 'POST':
        form = SignupForm(request.POST, request.FILES)

        if form.is_valid():
            try:
                user = form.save(commit=False)

                # Check if email is already registered
                if User.objects.filter(email=user.email).exists():
                    logger.warning(f"Email already exists: {user.email}")
                    messages.error(request, "This email is already registered. Please use a different email or log in.")
                    return render(request, 'base/signup.html', {'form': form})

                # Save user — is_active=True, profile_completed=False (set in form.save())
                user.save()

                # Log in immediately — no email gate
                login(request, user)

                logger.info(f"New user registered: {user.email} (ID: {user.id})")

                # Redirect to Step 2 — complete profile
                messages.success(request, f"Welcome {user.get_short_name()}! Please complete your profile to start posting.")
                return redirect('complete_profile')

            except IntegrityError as e:
                logger.error(f"Database error during user registration: {str(e)}\n{traceback.format_exc()}")
                messages.error(request, "This email is already in use. Please try a different one.")
                return render(request, 'base/signup.html', {'form': form})
            except Exception as e:
                logger.error(f"Unexpected error during user registration: {str(e)}\n{traceback.format_exc()}")
                messages.error(request, f"An unexpected error occurred: {str(e)}. Please try again.")
                return render(request, 'base/signup.html', {'form': form})
        else:
            logger.warning(f"Form validation failed: {form.errors}")
    else:
        form = SignupForm()

    return render(request, 'base/signup.html', {'form': form})


# ── STEP 2 — COMPLETE PROFILE ─────────────────────────────────────────────────
@login_required(login_url='login')
def complete_profile(request):
    # If already completed, send to home
    if request.user.profile_completed:
        return redirect('index')

    if request.method == 'POST':
        form = CompleteProfileForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()  # sets profile_completed=True inside form.save()
            messages.success(request, "Profile complete! You now have full access.")
            return redirect('index')
        else:
            messages.error(request, "Please fill in all required fields.")
    else:
        form = CompleteProfileForm(instance=request.user)

    return render(request, 'base/complete_profile.html', {'form': form})


# ── EMAIL VERIFICATION (kept for future use) ──────────────────────────────────
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
        return super().form_valid(form)


# ── LOGIN ─────────────────────────────────────────────────────────────────────
@require_http_methods(["GET", "POST"])
def login_view(request):
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            password = form.cleaned_data['password']
            user = authenticate(request, email=email, password=password)
            if user is not None:
                if user.is_active:
                    login(request, user)
                    # If profile not completed, send to Step 2
                    if not user.profile_completed:
                        messages.info(request, "Please complete your profile to start posting.")
                        return redirect('complete_profile')
                    return redirect('index')
                else:
                    form.add_error(None, "Your account is inactive. Contact support.")
            else:
                form.add_error(None, "Invalid email or password.")
        return render(request, 'base/login.html', {'form': form})
    else:
        form = LoginForm()
    return render(request, 'base/login.html', {'form': form})


# ── LOGOUT ────────────────────────────────────────────────────────────────────
def logout_user(request):
    logout(request)
    return redirect('index')


# ── INDEX ─────────────────────────────────────────────────────────────────────
def index(request):
    featured_ads = Ad.objects.filter(
        status='approved',
        featuredad__featured_start_date__lte=timezone.now(),
        featuredad__featured_expiry_date__gte=timezone.now()
    ).prefetch_related('images')

    categories = Category.objects.annotate(
        approved_ads_count=Count('ad', filter=Q(ad__status='approved'))
    ).prefetch_related(
        Prefetch(
            'ad_set',
            queryset=Ad.objects.filter(status='approved').order_by('-created_at')[:20],
            to_attr='approved_ads'
        )
    )

    return render(request, 'base/index.html', {
        'categories': categories,
        'featured_products': featured_ads,
    })


def category_detail(request, category_id):
    category = get_object_or_404(Category, id=category_id)
    categories = Category.objects.all()

    ads = Ad.objects.filter(
        category=category,
        status='approved'
    ).select_related('category').prefetch_related('images').order_by('-created_at')

    subcategories = group_ads_by_type(category.name, ads)

    context = {
        'category': category,
        'ads': ads,
        'subcategories': subcategories,
        'categories': categories,
    }
    return render(request, 'base/category_detail.html', context)


def group_ads_by_type(category_name, ads):
    if not ads:
        return {}

    subcategories = {}

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
            'field': 'service_type',
            'choices': dict(Ad.SERVICE_TYPE_CHOICES),
            'default_name': 'Other Beauty Services'
        },
        'Decoration': {
            'field': 'service_type',
            'choices': dict(Ad.SERVICE_TYPE_CHOICES),
            'default_name': 'Other Decoration'
        }
    }

    type_config = category_type_mapping.get(category_name)
    if not type_config:
        return {}

    field_name = type_config['field']
    choices = type_config['choices']
    default_name = type_config['default_name']

    for choice_value, choice_name in choices.items():
        subcategories[choice_name] = []
    subcategories[default_name] = []

    for ad in ads:
        type_value = getattr(ad, field_name)
        if type_value and type_value in choices:
            subcategories[choices[type_value]].append(ad)
        else:
            subcategories[default_name].append(ad)

    subcategories = {k: v for k, v in subcategories.items() if v}
    return subcategories


def get_subcategories_for_category(category_name, ads):
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

    category_mapping = subcategory_config.get(category_name, {})
    if not category_mapping:
        return {}

    subcategories = {subcat_name: [] for subcat_name in category_mapping.keys()}

    for ad in ads:
        ad_name_lower = ad.name.lower()
        ad_description_lower = getattr(ad, 'description', '').lower()
        search_text = ad_name_lower + " " + ad_description_lower
        matched = False

        for subcat_name, keywords in category_mapping.items():
            if subcat_name.startswith('Other'):
                continue
            if any(keyword in search_text for keyword in keywords):
                subcategories[subcat_name].append(ad)
                matched = True
                break

        if not matched:
            other_key = next((key for key in category_mapping.keys() if 'Other' in key), None)
            if other_key:
                subcategories[other_key].append(ad)
            else:
                first_key = next(iter(category_mapping.keys()))
                subcategories[first_key].append(ad)

    subcategories = {k: v for k, v in subcategories.items() if v}
    return subcategories


def handle_redirect(request, category_id):
    return category_detail(request, category_id)


def menu(request):
    featured_ads = Ad.objects.filter(
        is_approved=True,
        featuredad__featured_start_date__lte=timezone.now(),
        featuredad__featured_expiry_date__gte=timezone.now()
    ).prefetch_related('featuredad')

    is_paid = request.GET.get('is_paid', 'false').lower() == 'true'
    request.session['is_paid'] = is_paid

    categories = Category.objects.annotate(
        approved_ads_count=Count('ad', filter=Q(ad__is_approved=True))
    ).order_by('name')

    return render(request, 'base/post_ad_categories.html', {
        'categories': categories,
        'featured_products': featured_ads,
    })


def about_us(request):
    categories = Category.objects.all()
    return render(request, 'base/aboutus.html', {'categories': categories})


logger = logging.getLogger(__name__)


@login_required(login_url='login')
def ad_form(request, category_id=None):
    category = None
    if category_id is not None:
        category = get_object_or_404(Category, id=category_id)

    categories = Category.objects.all()
    show_success = False

    if request.method == 'POST':
        form = AdForm(request.POST, request.FILES)

        if category is None:
            posted_cat = request.POST.get('category')
            if posted_cat:
                try:
                    category = Category.objects.get(id=posted_cat)
                except Category.DoesNotExist:
                    category = None

        if category is None:
            form.add_error(None, 'Please select a category for your ad.')

        if form.is_valid():
            try:
                ad = form.save(commit=False)
                ad.category = category
                ad.advertiser = request.user
                ad.is_approved = False
                ad.save()

                images = request.FILES.getlist('images')
                if images:
                    for img in images:
                        AdImage.objects.create(ad=ad, image=img)

                messages.success(request, "Your digital masterpiece is now soaring through our approval cosmos!")
                show_success = True
                form = AdForm()
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
def create_ad_form(request, category_id=None):
    category = None
    if category_id is not None:
        category = get_object_or_404(Category, id=category_id)

    categories = Category.objects.all()
    show_success = False

    if request.method == 'POST':
        form = AdPaidForm(request.POST, request.FILES)

        if category is None:
            posted_cat = request.POST.get('category')
            if posted_cat:
                try:
                    category = Category.objects.get(id=posted_cat)
                except Category.DoesNotExist:
                    category = None

        if category is None:
            form.add_error(None, 'Please select a category for your ad.')

        if form.is_valid():
            try:
                ad = form.save(commit=False)
                ad.category = category
                ad.advertiser = request.user
                ad.is_approved = False
                ad.save()

                images = request.FILES.getlist('images')
                if images:
                    for img in images:
                        AdImage.objects.create(ad=ad, image=img)

                PendingFeaturedAd.objects.create(
                    ad=ad,
                    payment_screenshot=form.cleaned_data['payment_screenshot'],
                    featured_start_date=form.cleaned_data['featured_start_date'],
                    featured_expiry_date=form.cleaned_data['featured_expiry_date']
                )

                messages.success(request, "Your digital masterpiece is now soaring through our approval cosmos!")
                show_success = True
                form = AdPaidForm()
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
        if not hasattr(instance, 'featuredad'):
            try:
                pending = PendingFeaturedAd.objects.get(ad=instance)
                FeaturedAd.objects.create(
                    ad=instance,
                    payment_screenshot=pending.payment_screenshot,
                    featured_start_date=pending.featured_start_date,
                    featured_expiry_date=pending.featured_expiry_date
                )
                FeaturedAdHistory.objects.create(
                    ad=instance,
                    amount_paid=0.0,
                    payment_screenshot=pending.payment_screenshot,
                    expires_at=pending.featured_expiry_date
                )
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
    notifications = Notification.objects.filter(user=request.user).order_by('-created_at')
    unread_ids = list(notifications.filter(is_read=False).values_list('id', flat=True))

    paginator = Paginator(notifications, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    Notification.objects.filter(id__in=unread_ids).update(is_read=True)

    for notification in page_obj:
        notification.was_unread = notification.id in unread_ids

    return render(request, 'base/notification_center.html', {
        'page_obj': page_obj,
        'categories': categories,
    })


@login_required(login_url='login')
def delete_notification(request, pk):
    notification = get_object_or_404(Notification, id=pk, user=request.user)
    notification.delete()
    return redirect('notification_center')


@login_required(login_url='login')
def mark_all_read(request):
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    return redirect('notification_center')


@login_required(login_url='login')
def toggle_favorite(request, ad_id):
    ad = get_object_or_404(Ad, pk=ad_id)
    user = request.user

    favorite_exists = Favorite.objects.filter(user=user, ad=ad).exists()

    if favorite_exists:
        Favorite.objects.filter(user=user, ad=ad).delete()
        favorited = False
    else:
        Favorite.objects.create(user=user, ad=ad)
        favorited = True

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({
            'favorited': favorited,
            'favorite_count': ad.favorited_by.count()
        })
    else:
        return redirect(request.META.get('HTTP_REFERER', 'home'))


@login_required(login_url='login')
def my_favorites(request):
    categories = Category.objects.all()
    favorites = Favorite.objects.filter(user=request.user).select_related(
        'ad__category'
    ).prefetch_related('ad__images')

    user_favorites = set(favorites.values_list('ad_id', flat=True))

    return render(request, 'base/favorites.html', {
        'favorites': favorites,
        'categories': categories,
        'user_favorites': user_favorites,
    })


def product_detail(request, ad_id):
    ad = get_object_or_404(Ad, pk=ad_id)
    categories = Category.objects.all()

    Ad.objects.filter(pk=ad.pk).update(views=F('views') + 1)

    similar_items = Ad.objects.filter(
        category=ad.category,
        status='approved'
    ).exclude(id=ad.id).order_by('-created_at')[:6]

    if request.user.is_authenticated:
        user_favorites = set(request.user.favorites.values_list('ad_id', flat=True))
        user_rating = None
        if request.user != ad.advertiser:
            try:
                user_rating = SellerRating.objects.get(seller=ad.advertiser, rater=request.user)
            except SellerRating.DoesNotExist:
                user_rating = None
    else:
        user_favorites = set()
        user_rating = None

    seller_stats = ad.advertiser.get_seller_stats()
    recent_ratings = SellerRating.objects.filter(
        seller=ad.advertiser
    ).select_related('rater').order_by('-created_at')[:5]

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
                existing_rating = SellerRating.objects.filter(
                    seller=ad.advertiser, rater=request.user
                ).first()

                if existing_rating:
                    existing_rating.rating = rating_form.cleaned_data['rating']
                    existing_rating.comment = rating_form.cleaned_data['comment']
                    existing_rating.save()
                    messages.success(request, 'Your rating has been updated.')
                else:
                    rating = rating_form.save(commit=False)
                    rating.seller = ad.advertiser
                    rating.rater = request.user
                    rating.save()
                    messages.success(request, 'Thank you for your rating!')

                seller_stats.update_stats()
                return redirect('product_detail', ad_id=ad_id)

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
    seller_stats = seller.get_seller_stats()
    seller_stats.update_stats()
    messages.success(request, 'Your rating has been deleted.')
    return redirect('base/product_detail', ad_id=request.GET.get('next', ''))


def search_ads(request):
    categories = Category.objects.all()
    keyword = request.GET.get('q', '').strip()
    location = request.GET.get('location', '').strip()
    category_id = request.GET.get('category', '').strip()

    base_query = Ad.objects.filter(status='approved')
    ads = base_query
    has_exact = False
    has_similar = False

    state = None
    if location:
        state_match = re.search(r'\b([A-Z]{2})\b', location, re.IGNORECASE)
        state = state_match.group(1).upper() if state_match else None

    exact_filters = Q()

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

    if location:
        location_query = Q()
        location_query |= Q(location__icontains=location)
        if state:
            location_query |= Q(location__icontains=state)
        exact_filters &= location_query

    if category_id:
        try:
            exact_filters &= Q(category__id=category_id)
        except (ValueError, Category.DoesNotExist):
            pass

    ads = base_query.filter(exact_filters).order_by('-is_featured', '-created_at')
    has_exact = ads.exists()

    similar_ads = base_query.none()
    if not has_exact or ads.count() < 5:
        similar_query = Q()

        if category_id:
            try:
                similar_query &= Q(category__id=category_id)
            except (ValueError, Category.DoesNotExist):
                pass

        if keyword:
            keyword_similar = Q()
            for word in keyword.split()[:3]:
                keyword_similar |= (
                    Q(name__icontains=word) |
                    Q(description__icontains=word)
                )
            similar_query &= keyword_similar

        similar_ads = base_query.filter(similar_query).exclude(
            id__in=ads.values_list('id', flat=True)
        ).order_by('-is_featured', '-created_at')[:8]

        has_similar = similar_ads.exists()

    category_name = ""
    if category_id:
        try:
            category_name = Category.objects.get(id=category_id).name
        except (ValueError, Category.DoesNotExist):
            pass

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
    return render(request, 'base/product_list.html', {
        'categories': categories,
        'category': category,
        'ads': ads
    })


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

    return render(request, 'base/dashboard.html', {'categories': categories})


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