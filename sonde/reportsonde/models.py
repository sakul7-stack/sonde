from django.db import models

class UserSubmit(models.Model):
    email = models.EmailField()

    phone = models.CharField(max_length=15) 

    lat = models.FloatField()
    lon = models.FloatField()

    photo = models.ImageField(upload_to='user_submission/')  

    note = models.TextField(null=True, blank=True)

    def __str__(self): 
        return self.email