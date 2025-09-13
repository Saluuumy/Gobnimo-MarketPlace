from django.contrib import admin, messages
from django.utils.safestring import mark_safe
import logging

from .models import (
    User,
    Comment,
    Category,
    Ad,
    AdImage,
    PendingFeaturedAd,
    FeaturedAd,
    FeaturedAdHistory,
)

logger = logging.getLogger(__name__)

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ['email', 'full_name', 'phone_number', 'location', 'avatar', 'email_verified', 'date_joined']
    list_filter = ['email_verified']
    actions = ['mark_email_verified']

    def mark_email_verified(self, request, queryset):
        queryset.update(email_verified=True, is_active=True)
        self.message_user(request, "Selected users' emails have been verified.")
    mark_email_verified.short_description = "Mark selected users' emails as verified"

@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ('user', 'ad', 'timestamp')
    search_fields = ('user__username', 'ad__name')

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name',)

class AdImageInline(admin.TabularInline):
    model = AdImage
    extra = 1

class CommentInline(admin.TabularInline):
    model = Comment
    extra = 0

@admin.register(Ad)
class AdAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'advertiser', 'is_approved', 'created_at', 'price']
    list_filter = ['is_approved', 'category']
    actions = ['approve_ads']
    inlines = [AdImageInline, CommentInline]

    def approve_ads(self, request, queryset):
        approved = 0
        errors = []

        for ad in queryset:
            if not ad.is_approved:
                try:
                    ad.is_approved = True
                    ad.save(update_fields=['is_approved'])
                    logger.info(f"Ad {ad.name} approved")

                    # Check for existing FeaturedAd
                    if hasattr(ad, 'featuredad'):
                        logger.warning(f"FeaturedAd already exists for {ad.name}")
                        errors.append(f"FeaturedAd already exists for {ad.name}")
                        continue

                    # Check for PendingFeaturedAd
                    if not hasattr(ad, 'pending_featured'):
                        logger.info(f"No PendingFeaturedAd for {ad.name}")
                        errors.append(f"No PendingFeaturedAd for {ad.name}")
                        approved += 1
                        continue

                    pending = ad.pending_featured

                    # Create FeaturedAd
                    try:
                        FeaturedAd.objects.create(
                            ad=ad,
                            payment_screenshot=pending.payment_screenshot,
                            featured_start_date=pending.featured_start_date,
                            featured_expiry_date=pending.featured_expiry_date
                        )
                        logger.info(f"Created FeaturedAd for {ad.name}")

                        FeaturedAdHistory.objects.create(
                            ad=ad,
                            amount_paid=0.00,
                            payment_screenshot=pending.payment_screenshot,
                            expires_at=pending.featured_expiry_date
                        )
                        logger.info(f"Created FeaturedAdHistory for {ad.name}")

                        pending.delete()
                        logger.info(f"Deleted PendingFeaturedAd for {ad.name}")
                        approved += 1

                    except Exception as e:
                        logger.error(f"Error creating FeaturedAd for {ad.name}: {str(e)}")
                        errors.append(f"Error creating FeaturedAd for {ad.name}: {str(e)}")

                except Exception as e:
                    logger.error(f"Error approving {ad.name}: {str(e)}")
                    errors.append(f"Error approving {ad.name}: {str(e)}")

        if approved:
            self.message_user(
                request,
                f"{approved} ad(s) approved and featured where applicable.",
                messages.SUCCESS
            )
        if errors:
            self.message_user(
                request,
                f"Errors occurred: {'; '.join(errors)}",
                messages.ERROR
            )

    approve_ads.short_description = "Approve selected ads (and feature paid ones)"


@admin.register(PendingFeaturedAd)
class PendingFeaturedAdAdmin(admin.ModelAdmin):
    list_display = ('ad', 'featured_start_date', 'featured_expiry_date')
    actions = ['approve_featured_ads']

    def approve_featured_ads(self, request, queryset):
        for pending_ad in queryset:
            # Approve the ad first
            ad = pending_ad.ad
            ad.is_approved = True
            ad.save()

            # Create the FeaturedAd
            FeaturedAd.objects.create(
                ad=ad,
                payment_screenshot=pending_ad.payment_screenshot,
                featured_start_date=pending_ad.featured_start_date,
                featured_expiry_date=pending_ad.featured_expiry_date
            )

            # Optional: Create history record
            FeaturedAdHistory.objects.create(
                ad=ad,
                amount_paid=0,  # You might want to add amount to PendingFeaturedAd
                payment_screenshot=pending_ad.payment_screenshot,
                expires_at=pending_ad.featured_expiry_date
            )

            # Delete the pending record
            pending_ad.delete()

        self.message_user(request, f"Successfully approved {queryset.count()} featured ads.")
    approve_featured_ads.short_description = "Approve selected featured ads"

@admin.register(FeaturedAd)
class FeaturedAdAdmin(admin.ModelAdmin):
    list_display = ('ad', 'featured_start_date', 'featured_expiry_date', 'is_active_display')

    def is_active_display(self, obj):
        return obj.is_active()
    is_active_display.boolean = True
    is_active_display.short_description = 'Active?'

@admin.register(FeaturedAdHistory)
class FeaturedAdHistoryAdmin(admin.ModelAdmin):
    list_display = ('ad', 'featured_date', 'expires_at', 'payment_screenshot')

@admin.register(AdImage)
class AdImageAdmin(admin.ModelAdmin):
    list_display = ('ad', 'image_thumbnail')

    def image_thumbnail(self, obj):
        if obj.image:
            try:
                return mark_safe(f'<img src="{obj.image.url}" style="max-width:80px; max-height:80px;" />')
            except ValueError:
                return '(Invalid image)'
        return '(No image)'


