from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.db import transaction
from .models import Ad, FeaturedAd, PendingFeaturedAd, User, Notification
import logging

logger = logging.getLogger(__name__)

@receiver(pre_save, sender=Ad)
def track_ad_changes(sender, instance, **kwargs):
    """Track changes to Ad status and approval state"""
    if instance.pk:
        try:
            original = Ad.objects.get(pk=instance.pk)
            instance._original_status = original.status
            instance._original_is_approved = original.is_approved
        except Ad.DoesNotExist:
            instance._original_status = None
            instance._original_is_approved = None

@receiver(post_save, sender=Ad)
def handle_ad_status_change(sender, instance, created, **kwargs):
    """Handle notifications for ad status changes"""
    if created:
        # Notification for newly created ad (pending approval)
        Notification.objects.create(
            user=instance.advertiser,
            ad=instance,
            message=f'Your ad "{instance.name}" is pending admin approval',
            notification_type='info'
        )
        return
    
    # Handle status changes
    if not hasattr(instance, '_original_status') or not hasattr(instance, '_original_is_approved'):
        return
        
    # Approval notification
    if instance.is_approved and not instance._original_is_approved:
        Notification.objects.create(
            user=instance.advertiser,
            ad=instance,
            message=f'Your ad "{instance.name}" has been approved and is now live!',
            notification_type='approval'
        )
    
    # Rejection notification
    if not instance.is_approved and instance._original_is_approved:
        Notification.objects.create(
            user=instance.advertiser,
            ad=instance,
            message=f'Your ad "{instance.name}" has been rejected. Please review guidelines.',
            notification_type='rejection'
        )
    
    # Featured ad handling
    if instance.status == 'approved' and instance._original_status != 'approved':
        with transaction.atomic():
            pending_featured = PendingFeaturedAd.objects.filter(ad=instance).first()
            if pending_featured:
                # FeaturedAd creation will trigger its own notification via post_save
                FeaturedAd.objects.create(
                    ad=instance,
                    payment_screenshot=pending_featured.payment_screenshot,
                    featured_start_date=pending_featured.featured_start_date,
                    featured_expiry_date=pending_featured.featured_expiry_date
                )
                pending_featured.delete()
                instance.is_featured = True
                instance.save(update_fields=['is_featured'])

@receiver(post_save, sender=FeaturedAd)
def handle_featured_ad_creation(sender, instance, created, **kwargs):
    """Handle notifications for featured ad creation"""
    if created:
        Notification.objects.create(
            user=instance.ad.advertiser,
            ad=instance.ad,
            message=f'Your ad "{instance.ad.name}" is now featured!',
            notification_type='featured'
        )

@receiver(post_save, sender=PendingFeaturedAd)
def handle_pending_featured(sender, instance, created, **kwargs):
    """Handle notifications for pending featured ad payment"""
    if created:
        Notification.objects.create(
            user=instance.ad.advertiser,
            ad=instance.ad,
            message=f'Payment received for featuring ad "{instance.ad.name}". Awaiting approval.',
            notification_type='info'
        )

@receiver(post_save, sender=User)
def handle_user_verification(sender, instance, created, **kwargs):
    """Log user creation and verification"""
    if created:
        logger.info(f"New user created: {instance.email}")
        # Send welcome notification
        Notification.objects.create(
            user=instance,
            message='Welcome to our marketplace! Get started by creating your first ad.',
            notification_type='info'
        )
    
    if instance.email_verified and instance.is_active:
        logger.info(f"User verified: {instance.email}")
        Notification.objects.create(
            user=instance,
            message='Your email has been verified successfully!',
            notification_type='info'
        )