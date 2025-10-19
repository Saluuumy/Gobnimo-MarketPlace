from allauth.account.adapter import DefaultAccountAdapter
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
import threading
import logging

logger = logging.getLogger(__name__)

class EmailThread(threading.Thread):
    """Thread for sending emails asynchronously"""
    def __init__(self, subject, message, from_email, recipient_list, html_message=None):
        self.subject = subject
        self.message = message
        self.from_email = from_email
        self.recipient_list = recipient_list
        self.html_message = html_message
        super().__init__()

    def run(self):
        try:
            send_mail(
                self.subject,
                self.message,
                self.from_email,
                self.recipient_list,
                html_message=self.html_message,
                fail_silently=False,
            )
        except Exception as e:
            logger.error(f"Error sending email: {e}")

class CustomAccountAdapter(DefaultAccountAdapter):
    def send_mail(self, template_prefix, email, context):
        """Override to send emails asynchronously"""
        try:
            subject = self.get_subject(template_prefix)
            from_email = self.get_from_email()
            
            # Get email templates
            templates = self.get_email_templates(template_prefix)
            template_name, ext = templates
            html_template_name = f"{template_name}_message.{ext}"
            txt_template_name = f"{template_name}_message.txt"
            
            # Render templates
            context.update({
                'site_name': self.request.site.name if self.request else 'Adver Platform'
            })
            
            html_message = render_to_string(html_template_name, context)
            message = render_to_string(txt_template_name, context)
            
            # Send email in background thread
            email_thread = EmailThread(
                subject=subject,
                message=message,
                from_email=from_email,
                recipient_list=[email],
                html_message=html_message
            )
            email_thread.start()
            
        except Exception as e:
            logger.error(f"Error in send_mail: {e}")
            # Fallback to parent method if async fails
            super().send_mail(template_prefix, email, context)

    def save_user(self, request, user, form, commit=True):
        """Override to save user without waiting for email"""
        user = super().save_user(request, user, form, commit=False)
        if commit:
            user.save()
        return user