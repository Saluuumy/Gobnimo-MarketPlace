# context_processors.py
from .models import Favorite,Notification

def unread_notifications(request):
    if request.user.is_authenticated:
        return {'unread_count': request.user.notifications.filter(is_read=False).count()}
    return {'unread_count': 0}


def user_counts(request):
    context = {}
    if request.user.is_authenticated:
        context['favorites_count'] = Favorite.objects.filter(user=request.user).count()
        context['unread_count'] = Notification.objects.filter(user=request.user, is_read=False).count()
    else:
        context['favorites_count'] = 0
        context['unread_count'] = 0
    return context