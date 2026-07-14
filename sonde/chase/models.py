from django.db import models
from django.contrib.auth.models import User

class ActiveChaser(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    lat = models.FloatField(null=True, blank=True)
    lng = models.FloatField(null=True, blank=True)
    chase_name = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=False)   # Changed default
    last_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} - {self.chase_name}"
