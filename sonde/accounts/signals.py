from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Profile, APIKey
from django.core.mail import send_mail

@receiver(post_save, sender=User)
def create_user_data(sender, instance, created, **kwargs):
    if created:
        profile, _ = Profile.objects.get_or_create(user=instance)
        api, _ = APIKey.objects.get_or_create(user=instance)

        send_mail(
            subject="Your API Key",
            message=f"API Key: {api.key}",
            from_email="080bct041.kushal@pcampus.edu.np",
            recipient_list=[instance.email or ""],
        )