import secrets
from django.db import models
from django.contrib.auth.models import User


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    is_api_user = models.BooleanField(default=True)
    is_contributor = models.BooleanField(default=False)

    def __str__(self):
        return self.user.username


class APIKey(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)  # IMPORTANT FIX
    key = models.CharField(max_length=64, unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.key:
            self.key = secrets.token_hex(32)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user.username} - {self.key}"


class ContributorInfo(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    lat = models.FloatField(null=True, blank=True)
    lon = models.FloatField(null=True, blank=True)
    alt = models.FloatField(null=True, blank=True)