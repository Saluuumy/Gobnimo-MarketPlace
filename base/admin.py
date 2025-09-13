from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from django.urls import reverse
from django.db import transaction
from .models import User, Ad, Comment, Category, AdImage, PendingFeaturedAd, FeaturedAd, FeaturedAdHistory, Notification
import logging

logger = logging.getLogger(__name__)

# Unregister default User if needed
try:
    admin.site.unregister(User)
except admin.sites.NotRegistered:
    pass

@admin.register(User)
class CustomUserAdmin(BaseUserAdmin):
    list_display = ['email', 'full_name', 'phone_number', 'location', 'avatar_preview', 'email_verified', 'date_joined']
    list_filter = ['email_verified', 'is_staff', 'is_superuser']
    actions = ['mark_email_verified']
    
    # Add custom fields to fieldsets
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal Info', {'fields': ('full_name', 'bio', 'phone_number', 'avatar', 'location')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
        ('Verification', {'fields': ('email_verified',)}),
    )
    
    # Add custom fields to add_fieldsets
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2', 'full_name'),
        }),
    )
    
    ordering = ['email']
    filter_horizontal = ()
    readonly_fields = ['avatar_preview']
    
    def avatar_preview(self, obj):
        if obj.avatar and hasattr(obj.avatar, 'url'):
            return format_html('<img src="{}" style="max-height:100px;"/>', obj.avatar.url)
        return "-"
    avatar_preview.short_description = 'Avatar Preview'

    def mark_email_verified(self, request, queryset):
        queryset.update(email_verified=True, is_active=True)
        self.message_user(request, "Selected users' emails have been verified.", messages.SUCCESS)
    mark_email_verified.short_description = "Mark selected users' emails as verified"

@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ('user', 'ad', 'timestamp')
    search_fields = ('user__email', 'ad__name')

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)
    
class AdImageInline(admin.TabularInline):
    model = AdImage
    extra = 1
    readonly_fields = ['image_preview']
    
    def image_preview(self, obj):
        if obj.image and obj.image.storage.exists(obj.image.name):
            return format_html(
                '<img src="{}" style="max-height:100px; max-width:100px;"/>', 
                obj.image.url
            )
        return "Image not found"
    
    image_preview.short_description = 'Preview'

class CommentInline(admin.TabularInline):
    model = Comment
    extra = 0
    readonly_fields = ['text', 'user', 'timestamp']

@admin.register(Ad)
class AdAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'advertiser', 'is_approved', 'created_at', 'price', 'status_indicator']
    list_filter = ['is_approved', 'category', 'status']
    actions = ['approve_ads', 'reject_ads', 'send_notification']
    inlines = [AdImageInline, CommentInline]
    readonly_fields = ['created_at', 'views']
    date_hierarchy = 'created_at'
    search_fields = ['name', 'advertiser__email']
    
    def status_indicator(self, obj):
        if obj.status == 'approved':
            return format_html('<span style="color: green; font-weight: bold;">✓ Approved</span>')
        elif obj.status == 'rejected':
            return format_html('<span style="color: red; font-weight: bold;">✗ Rejected</span>')
        return format_html('<span style="color: orange; font-weight: bold;">⧗ Pending</span>')
    status_indicator.short_description = 'Status'
    status_indicator.admin_order_field = 'status'

    def approve_ads(self, request, queryset):
        approved = 0
        errors = []

        for ad in queryset:
            if not ad.is_approved or ad.status != 'approved':
                try:
                    with transaction.atomic():
                        ad.is_approved = True
                        ad.status = 'approved'
                        ad.save(update_fields=['is_approved', 'status'])
                        
                        # Handle featured ad promotion if exists
                        pending_featured = PendingFeaturedAd.objects.filter(ad=ad).first()
                        if pending_featured:
                            FeaturedAd.objects.create(
                                ad=ad,
                                payment_screenshot=pending_featured.payment_screenshot,
                                featured_start_date=pending_featured.featured_start_date,
                                featured_expiry_date=pending_featured.featured_expiry_date
                            )
                            pending_featured.delete()
                            ad.is_featured = True
                            ad.save(update_fields=['is_featured'])
                        
                        approved += 1
                        logger.info(f"Ad {ad.name} approved and featured status handled")
                except Exception as e:
                    errors.append(f"Error approving {ad.name}: {str(e)}")
                    logger.error(f"Error approving ad {ad.name}: {str(e)}", exc_info=True)

        if approved:
            self.message_user(request, f"{approved} ad(s) approved successfully", messages.SUCCESS)
        if errors:
            self.message_user(request, f"Errors occurred: {'; '.join(errors)}", messages.ERROR)
    approve_ads.short_description = "Approve selected ads (and feature paid ones)"
    
    def reject_ads(self, request, queryset):
        rejected = 0
        for ad in queryset:
            if ad.status != 'rejected':
                ad.status = 'rejected'
                ad.save(update_fields=['status'])
                rejected += 1
        if rejected:
            self.message_user(request, f"{rejected} ad(s) rejected", messages.SUCCESS)
    reject_ads.short_description = "Reject selected ads"
    
    def send_notification(self, request, queryset):
        notifications_sent = 0
        errors = []
        
        for ad in queryset:
            try:
                Notification.objects.create(
                    user=ad.advertiser,
                    ad=ad,
                    message=f'Admin notification about your ad "{ad.name}"',
                    notification_type='info'
                )
                notifications_sent += 1
            except Exception as e:
                errors.append(f"Notification error for {ad.name}: {str(e)}")
        
        if notifications_sent:
            self.message_user(
                request,
                f"{notifications_sent} notification(s) sent successfully",
                messages.SUCCESS
            )
        if errors:
            self.message_user(
                request,
                f"Errors occurred: {'; '.join(errors)}",
                messages.ERROR
            )
    send_notification.short_description = "Send custom notification to advertiser"


@admin.register(PendingFeaturedAd)
class PendingFeaturedAdAdmin(admin.ModelAdmin):
    list_display = ('id', 'ad_link', 'featured_start_date', 'featured_expiry_date', 'payment_status')
    list_select_related = ['ad']  # Optimize database queries
    actions = ['approve_featured_ads']
    readonly_fields = ['ad_link', 'payment_screenshot_preview']
    list_filter = ['featured_start_date']
    search_fields = ['ad__name']
    
    def ad_link(self, obj):
        if not obj.ad:
            return "Ad Deleted"
        try:
            # CORRECTED: Use your actual app name 'base'
            url = reverse('admin:base_ad_change', args=[obj.ad.id])
            return format_html('<a href="{}">{}</a>', url, obj.ad.name)
        except Exception as e:
            logger.error(f"Error generating ad link: {str(e)}")
            return f"Ad ID: {obj.ad.id}"
    ad_link.short_description = 'Ad'
    
    def payment_screenshot_preview(self, obj):
        if obj.payment_screenshot and hasattr(obj.payment_screenshot, 'url'):
            return format_html('<img src="{}" style="max-height:100px;"/>', obj.payment_screenshot.url)
        return "-"
    payment_screenshot_preview.short_description = 'Screenshot Preview'
    
    def payment_status(self, obj):
        if obj.ad and obj.ad.is_approved:
            return format_html('<span style="color: green;">Approved</span>')
        return format_html('<span style="color: orange;">Pending</span>')
    payment_status.short_description = 'Payment Status'
    
    def approve_featured_ads(self, request, queryset):
        approved = 0
        errors = []
        for pending_ad in queryset:
            try:
                # Skip if ad is missing
                if not pending_ad.ad:
                    errors.append(f"Skipping pending ad {pending_ad.id} - ad deleted")
                    continue
                
                # Approve the ad first if not already approved
                ad = pending_ad.ad
                if not ad.is_approved or ad.status != 'approved':
                    ad.is_approved = True
                    ad.status = 'approved'
                    ad.save(update_fields=['is_approved', 'status'])
                
                # Create the FeaturedAd
                FeaturedAd.objects.create(
                    ad=ad,
                    payment_screenshot=pending_ad.payment_screenshot,
                    featured_start_date=pending_ad.featured_start_date,
                    featured_expiry_date=pending_ad.featured_expiry_date
                )
                
                # Create history record
                FeaturedAdHistory.objects.create(
                    ad=ad,
                    amount_paid=0,
                    payment_screenshot=pending_ad.payment_screenshot,
                    expires_at=pending_ad.featured_expiry_date
                )
                
                # Delete the pending record
                pending_ad.delete()
                approved += 1
            except Exception as e:
                errors.append(f"Error approving {pending_ad.id}: {str(e)}")
                logger.error(f"Error approving pending ad {pending_ad.id}: {str(e)}", exc_info=True)
        
        if approved:
            self.message_user(request, f"Successfully approved {approved} featured ads.", messages.SUCCESS)
        if errors:
            self.message_user(request, f"Errors: {'; '.join(errors)}", messages.ERROR)
    approve_featured_ads.short_description = "Approve selected featured ads"


@admin.register(FeaturedAd)
class FeaturedAdAdmin(admin.ModelAdmin):
    list_display = ('id', 'ad_link', 'featured_start_date', 'featured_expiry_date', 'is_active_display')
    list_select_related = ['ad']  # Optimize database queries
    readonly_fields = ['ad_link', 'payment_screenshot_preview']
    list_filter = ['featured_start_date']
    search_fields = ['ad__name']
    
    def ad_link(self, obj):
        if not obj.ad:
            return "Ad Deleted"
        try:
            url = reverse('admin:base_ad_change', args=[obj.ad.id])
            return format_html('<a href="{}">{}</a>', url, obj.ad.name)
        except Exception as e:
            logger.error(f"Error generating ad link: {str(e)}")
            return f"Ad ID: {obj.ad.id}"
    ad_link.short_description = 'Ad'
    
    def payment_screenshot_preview(self, obj):
        if obj.payment_screenshot and hasattr(obj.payment_screenshot, 'url'):
            return format_html('<img src="{}" style="max-height:100px;"/>', obj.payment_screenshot.url)
        return "-"
    payment_screenshot_preview.short_description = 'Screenshot Preview'
    
    def is_active_display(self, obj):
        return obj.is_active()
    is_active_display.boolean = True
    is_active_display.short_description = 'Active?'


@admin.register(FeaturedAdHistory)
class FeaturedAdHistoryAdmin(admin.ModelAdmin):
    list_display = ('id', 'ad_link', 'featured_date', 'expires_at', 'payment_status')
    list_select_related = ['ad']  # Optimize database queries
    readonly_fields = ['ad_link', 'payment_screenshot_preview']
    list_filter = ['featured_date']
    search_fields = ['ad__name']
    
    def ad_link(self, obj):
        if not obj.ad:
            return "Ad Deleted"
        try:
            url = reverse('admin:base_ad_change', args=[obj.ad.id])
            return format_html('<a href="{}">{}</a>', url, obj.ad.name)
        except Exception as e:
            logger.error(f"Error generating ad link: {str(e)}")
            return f"Ad ID: {obj.ad.id}"
    ad_link.short_description = 'Ad'
    
    def payment_screenshot_preview(self, obj):
        if obj.payment_screenshot and hasattr(obj.payment_screenshot, 'url'):
            return format_html('<img src="{}" style="max-height:100px;"/>', obj.payment_screenshot.url)
        return "-"
    payment_screenshot_preview.short_description = 'Screenshot Preview'
    
    def payment_status(self, obj):
        if obj.ad and obj.ad.is_approved:
            return format_html('<span style="color: green;">Completed</span>')
        return format_html('<span style="color: orange;">Pending</span>')
    payment_status.short_description = 'Payment Status'


@admin.register(AdImage)
class AdImageAdmin(admin.ModelAdmin):
    list_display = ('id', 'ad_link', 'image_preview')
    list_select_related = ['ad']  # Optimize database queries
    readonly_fields = ['ad_link', 'image_preview']
    search_fields = ['ad__name']
    
    def ad_link(self, obj):
        if not obj.ad:
            return "Ad Deleted"
        try:
            url = reverse('admin:base_ad_change', args=[obj.ad.id])
            return format_html('<a href="{}">{}</a>', url, obj.ad.name)
        except Exception as e:
            logger.error(f"Error generating ad link: {str(e)}")
            return f"Ad ID: {obj.ad.id}"
    ad_link.short_description = 'Ad'
    
    def image_preview(self, obj):
        if obj.image and hasattr(obj.image, 'url'):
            return format_html('<img src="{}" style="max-height:200px;"/>', obj.image.url)
        return "(No image)"
    image_preview.short_description = 'Preview'


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'short_message', 'notification_type', 'ad_link', 'is_read', 'created_at']
    list_select_related = ['user', 'ad']  # Optimize database queries
    list_filter = ['notification_type', 'is_read', 'created_at']
    search_fields = ['user__email', 'message', 'ad__name']
    readonly_fields = ['created_at', 'ad_link']
    actions = ['mark_as_read', 'mark_as_unread']
    date_hierarchy = 'created_at'
    
    def short_message(self, obj):
        return obj.message[:80] + '...' if len(obj.message) > 80 else obj.message
    short_message.short_description = 'Message'
    
    def ad_link(self, obj):
        if obj.ad:
            try:
                url = reverse('admin:base_ad_change', args=[obj.ad.id])
                return format_html('<a href="{}">{}</a>', url, obj.ad.name)
            except:
                return obj.ad.name
        return "-"
    ad_link.short_description = 'Related Ad'
    
    def mark_as_read(self, request, queryset):
        updated = queryset.update(is_read=True)
        self.message_user(request, f"{updated} notification(s) marked as read", messages.SUCCESS)
    mark_as_read.short_description = "Mark as read"
    
    def mark_as_unread(self, request, queryset):
        updated = queryset.update(is_read=False)
        self.message_user(request, f"{updated} notification(s) marked as unread", messages.SUCCESS)
    mark_as_unread.short_description = "Mark as unread"