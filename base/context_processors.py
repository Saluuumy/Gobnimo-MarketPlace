# context_processors.py
from .models import Favorite,Notification

def unread_notifications(request):
    if request.user.is_authenticated:
        return {'unread_count': request.user.notifications.filter(is_read=False).count()}
    return {'unread_count': 0}


def user_counts(request):
    context = {
        'favorites_count': 0,
        'unread_count': 0
    }
    
    if request.user.is_authenticated:
        try:
            # Favorites: Always show total count (never clears)
            context['favorites_count'] = Favorite.objects.filter(user=request.user).count()
            
            # Notifications: Only show unread count (clears when marked read)
            context['unread_count'] = Notification.objects.filter(
                user=request.user, 
                is_read=False
            ).count()
            
        except Exception as e:
            # Handle any database issues gracefully
            print(f"Error in user_counts context processor: {e}")
    
    return context


def notification_context(request):
    if request.user.is_authenticated:
        return {
            'notifications': Notification.objects.filter(user=request.user).order_by('-created_at')[:10],
            'unread_count': Notification.objects.filter(user=request.user, is_read=False).count(),
        }
    return {
        'notifications': [],
        'unread_count': 0,
    }