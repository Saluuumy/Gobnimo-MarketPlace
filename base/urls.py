from django.urls import path ,include 
from . import views 
from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy
urlpatterns = [
   # Ads
path('ad/redirect/<int:subcategory_id>/', views.handle_ad_redirect, name='handle_ad_redirect'),
path('ad/create/', views.create_ad_form, name='create_ad_form'),
path('ad/create/<int:category_id>/', views.create_ad_form, name='create_ad_form'),

path('ad/free/<int:category_id>/', views.ad_form, name='ad_form'),
path('ad/free/', views.ad_form, name='ad_form'),
path('category/<int:category_id>/', views.category_detail, name='category_detail'),
    # Make sure you have this for the redirect too
    #  path('ad/redirect/<int:category_id>/', views.handle_ad_redirect, name='handle_ad_redirect'),
path('delete-ad/<int:ad_id>/', views.delete_ad, name='delete_ad'),

# Product
path('product/<int:ad_id>/', views.product_detail, name='product_detail'),
path('product/<int:ad_id>/comment/', views.add_comment, name='add_comment'),
path('comment/<int:comment_id>/delete/', views.delete_comment, name='delete_comment'),
path('reply_to_comment/<int:comment_id>/', views.reply_to_comment, name='reply_to_comment'),

# User
path('signup/', views.signup, name='signup'),
path('login/', views.login_view, name='login'),
path('logout/', views.logout_user, name='logout'),
   path('password-reset/',
         auth_views.PasswordResetView.as_view(
             template_name='base/password_reset.html',
             email_template_name='base/password_reset_email.html',
             subject_template_name='base/password_reset_subject.txt',
             success_url=reverse_lazy('password_reset_done'),
             html_email_template_name='base/password_reset_email.html',
             extra_context={'site_name': 'Gobonimo-Mart'}
         ),
         name='password_reset'),
    
    path('password-reset/done/',
         auth_views.PasswordResetDoneView.as_view(
             template_name='base/password_reset_done.html',
             extra_context={'site_name': 'Gobonimo-Mart'}
         ),
         name='password_reset_done'),
    
    path('password-reset-confirm/<uidb64>/<token>/',
         auth_views.PasswordResetConfirmView.as_view(
             template_name='base/password_reset_confirm.html',
             success_url=reverse_lazy('password_reset_complete'),
             extra_context={'site_name': 'Gobonimo-Mart'}
         ),
         name='password_reset_confirm'),
    
    path('password-reset-complete/',
         auth_views.PasswordResetCompleteView.as_view(
             template_name='base/password_reset_complete.html',
             extra_context={'site_name': 'Gobonimo-Mart'}
         ),
         name='password_reset_complete'),
path('verify-email/<uidb64>/<token>/', views.verify_email, name='verify_email'),
path('view_advertiser_profile/<str:username>/', views.view_advertiser_profile, name='view_advertiser_profile'),

# Dashboard & Navigation
path('', views.index, name='index'),
path('about/', views.about_us, name='about_us'),
path('menu/', views.menu, name='menu'),
path('dashboard/', views.dashboard, name='dashboard'),
path('search/', views.search_ads, name='search_ads'),
path('categories/<int:category_id>/', views.product_list, name='product_list'),

# Notifications
path('notifications/', views.notification_center, name='notification_center'),
path('notifications/delete/<int:pk>/', views.delete_notification, name='delete_notification'),
path('notifications/mark-all-read/', views.mark_all_read, name='mark_all_read'),

# Favorites

path('toggle_favorite/<int:ad_id>/', views.toggle_favorite, name='toggle_favorite'),
path('favorites/', views.my_favorites, name='my_favorites'),
]