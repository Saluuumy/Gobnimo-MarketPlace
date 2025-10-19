from allauth.account.adapter import DefaultAccountAdapter
from threading import Thread

class CustomAccountAdapter(DefaultAccountAdapter):
    def send_mail(self, template_prefix, email, context):
        def _send_mail():
            super().send_mail(template_prefix, email, context)
        Thread(target=_send_mail).start()