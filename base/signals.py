# signals.py
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.db import transaction
from django.utils import timezone
from datetime import timedelta
from .models import Ad, FeaturedAd, PendingFeaturedAd, User, Notification, Comment
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
            instance._original_is_featured = original.is_featured
        except Ad.DoesNotExist:
            instance._original_status = None
            instance._original_is_approved = None
            instance._original_is_featured = None

@receiver(post_save, sender=Ad)
def handle_ad_status_change(sender, instance, created, **kwargs):
    """Handle notifications for ad status changes"""
    try:
        if created:
            Notification.objects.create(
                user=instance.advertiser,
                ad=instance,
                message=f'Your ad "{instance.name}" is pending admin approval',
                notification_type='info'
            )
            logger.info(f"New ad created: {instance.name} by {instance.advertiser.email}")
            return
        
        original_status = getattr(instance, '_original_status', None)
        original_is_approved = getattr(instance, '_original_is_approved', None)
            
        # Approval notification
        if instance.is_approved and not original_is_approved:
            Notification.objects.create(
                user=instance.advertiser,
                ad=instance,
                message=f'Your ad "{instance.name}" has been approved and is now live!',
                notification_type='approval'
            )
            logger.info(f"Ad approved: {instance.name}")
        
        # Rejection notification
        if not instance.is_approved and original_is_approved:
            Notification.objects.create(
                user=instance.advertiser,
                ad=instance,
                message=f'Your ad "{instance.name}" has been rejected. Please review guidelines.',
                notification_type='rejection'
            )
            logger.info(f"Ad rejected: {instance.name}")
        
        # Featured ad handling
        if instance.status == 'approved' and original_status != 'approved':
            with transaction.atomic():
                pending_featured = PendingFeaturedAd.objects.filter(ad=instance).first()
                if pending_featured:
                    # Use update to avoid triggering save signal
                    Ad.objects.filter(pk=instance.pk).update(is_featured=True)
                    
                    FeaturedAd.objects.create(
                        ad=instance,
                        payment_screenshot=pending_featured.payment_screenshot,
                        featured_start_date=pending_featured.featured_start_date,
                        featured_expiry_date=pending_featured.featured_expiry_date
                    )
                    pending_featured.delete()
                    logger.info(f"Featured ad created from pending: {instance.name}")
                    
    except Exception as e:
        logger.error(f"Error handling ad status change for ad {instance.id}: {str(e)}")

@receiver(post_save, sender=FeaturedAd)
def handle_featured_ad_creation(sender, instance, created, **kwargs):
    """Handle notifications for featured ad creation and expiry"""
    try:
        if created:
            Notification.objects.create(
                user=instance.ad.advertiser,
                ad=instance.ad,
                message=f'Your ad "{instance.ad.name}" is now featured!',
                notification_type='featured'
            )
            logger.info(f"Featured ad created: {instance.ad.name}")
        
        # Check if featured ad is expiring soon (within 3 days)
        days_until_expiry = (instance.featured_expiry_date - timezone.now().date()).days
        if 0 <= days_until_expiry <= 3:
            Notification.objects.create(
                user=instance.ad.advertiser,
                ad=instance.ad,
                message=f'Your featured ad "{instance.ad.name}" is expiring in {days_until_expiry} day(s)!',
                notification_type='warning'
            )
            
    except Exception as e:
        logger.error(f"Error handling featured ad creation for ad {instance.ad.id}: {str(e)}")

@receiver(post_save, sender=PendingFeaturedAd)
def handle_pending_featured(sender, instance, created, **kwargs):
    """Handle notifications for pending featured ad payment"""
    try:
        if created:
            Notification.objects.create(
                user=instance.ad.advertiser,
                ad=instance.ad,
                message=f'Payment received for featuring ad "{instance.ad.name}". Awaiting approval.',
                notification_type='info'
            )
            logger.info(f"Pending featured ad created: {instance.ad.name}")
            
    except Exception as e:
        logger.error(f"Error handling pending featured ad for ad {instance.ad.id}: {str(e)}")

@receiver(pre_save, sender=User)
def track_user_changes(sender, instance, **kwargs):
    """Track changes to User verification state"""
    if instance.pk:
        try:
            original = User.objects.get(pk=instance.pk)
            instance._original_email_verified = original.email_verified
            instance._original_is_active = original.is_active
        except User.DoesNotExist:
            instance._original_email_verified = None
            instance._original_is_active = None

@receiver(post_save, sender=User)
def handle_user_verification(sender, instance, created, **kwargs):
    """Handle user creation and verification"""
    try:
        original_email_verified = getattr(instance, '_original_email_verified', None)
        original_is_active = getattr(instance, '_original_is_active', None)
        
        if created:
            logger.info(f"New user created: {instance.email}")
            # Send welcome notification
            Notification.objects.create(
                user=instance,
                message='Welcome to our marketplace! Get started by creating your first ad.',
                notification_type='info'
            )
        
        # Check if email verification status changed
        if instance.email_verified and not original_email_verified:
            logger.info(f"User verified: {instance.email}")
            Notification.objects.create(
                user=instance,
                message='Your email has been verified successfully!',
                notification_type='info'
            )
        
        # Check if user was activated/deactivated
        if instance.is_active and not original_is_active:
            logger.info(f"User activated: {instance.email}")
            Notification.objects.create(
                user=instance,
                message='Your account has been activated!',
                notification_type='info'
            )
        elif not instance.is_active and original_is_active:
            logger.info(f"User deactivated: {instance.email}")
            Notification.objects.create(
                user=instance,
                message='Your account has been deactivated. Please contact support.',
                notification_type='warning'
            )
            
    except Exception as e:
        logger.error(f"Error handling user verification for user {instance.id}: {str(e)}")

@receiver(post_save, sender=Comment)
def handle_comment_notifications(sender, instance, created, **kwargs):
    """Handle notifications for comments and replies"""
    try:
        if created:
            # Case 1: New comment on an ad (not a reply)
            if instance.parent is None:
                # Notify the ad owner if it's not their own comment
                if instance.user != instance.ad.advertiser:
                    Notification.objects.create(
                        user=instance.ad.advertiser,
                        ad=instance.ad,
                        message=f'@{instance.user.get_short_name()} commented on your ad "{instance.ad.name}"',
                        notification_type='info'
                    )
                    logger.info(f"New comment notification sent to ad owner: {instance.ad.advertiser.email}")
            
            # Case 2: Reply to a comment
            else:
                # Notify the parent comment's author if it's not their own reply
                if instance.user != instance.parent.user:
                    Notification.objects.create(
                        user=instance.parent.user,
                        ad=instance.ad,
                        message=f'@{instance.user.get_short_name()} replied to your comment on "{instance.ad.name}"',
                        notification_type='info'
                    )
                    logger.info(f"Reply notification sent to comment author: {instance.parent.user.email}")
                
                # Also notify the ad owner if they are not the one replying and it's not the same as parent comment author
                if (instance.user != instance.ad.advertiser and 
                    instance.parent.user != instance.ad.advertiser):
                    Notification.objects.create(
                        user=instance.ad.advertiser,
                        ad=instance.ad,
                        message=f'@{instance.user.get_short_name()} replied to a comment on your ad "{instance.ad.name}"',
                        notification_type='info'
                    )
                    logger.info(f"Reply notification sent to ad owner: {instance.ad.advertiser.email}")
                    
    except Exception as e:
        logger.error(f"Error handling comment notification for comment {instance.id}: {str(e)}")

# Signal to handle featured ad expiry checks (optional - can be run via cron job)
@receiver(post_save, sender=FeaturedAd)
def check_featured_ad_expiry(sender, instance, **kwargs):
    """Check and handle expired featured ads"""
    try:
        if instance.featured_expiry_date < timezone.now().date():
            # Featured ad has expired
            instance.ad.is_featured = False
            # Use update to avoid signal recursion
            Ad.objects.filter(pk=instance.ad.pk).update(is_featured=False)
            
            Notification.objects.create(
                user=instance.ad.advertiser,
                ad=instance.ad,
                message=f'Your featured ad "{instance.ad.name}" has expired.',
                notification_type='info'
            )
            logger.info(f"Featured ad expired: {instance.ad.name}")
            
    except Exception as e:
        logger.error(f"Error checking featured ad expiry for ad {instance.ad.id}: {str(e)}")

# Utility functions for testing
def disconnect_signals():
    """Disconnect signals for testing purposes"""
    pre_save.disconnect(track_ad_changes, sender=Ad)
    post_save.disconnect(handle_ad_status_change, sender=Ad)
    post_save.disconnect(handle_featured_ad_creation, sender=FeaturedAd)
    post_save.disconnect(handle_pending_featured, sender=PendingFeaturedAd)
    pre_save.disconnect(track_user_changes, sender=User)
    post_save.disconnect(handle_user_verification, sender=User)
    post_save.disconnect(handle_comment_notifications, sender=Comment)
    logger.info("All signals disconnected for testing")

def reconnect_signals():
    """Reconnect signals after testing"""
    pre_save.connect(track_ad_changes, sender=Ad)
    post_save.connect(handle_ad_status_change, sender=Ad)
    post_save.connect(handle_featured_ad_creation, sender=FeaturedAd)
    post_save.connect(handle_pending_featured, sender=PendingFeaturedAd)
    pre_save.connect(track_user_changes, sender=User)
    post_save.connect(handle_user_verification, sender=User)
    post_save.connect(handle_comment_notifications, sender=Comment)
    logger.info("All signals reconnected")