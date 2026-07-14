from django.db import models

class Sonde(models.Model):
    sonde_id = models.CharField(max_length=50, unique=True)

    type = models.CharField(max_length=20, null=True)
    subtype = models.CharField(max_length=20, null=True)
    frequency = models.CharField(max_length=20, null=True)

    date = models.DateTimeField(auto_now_add=True)


class Telemetry(models.Model):
    sonde = models.ForeignKey(Sonde, on_delete=models.CASCADE)

    frame = models.IntegerField()
    datetime = models.DateTimeField()

    lat = models.FloatField()
    lon = models.FloatField()
    alt = models.FloatField()

    vel_h = models.FloatField(null=True)
    vel_v = models.FloatField(null=True)
    heading = models.FloatField(null=True)

    temp = models.FloatField(null=True)
    humidity = models.FloatField(null=True)
    pressure = models.FloatField(null=True)

    battery = models.FloatField(null=True)

    f_centre = models.FloatField(null=True)
    snr = models.FloatField(null=True)

    raw = models.JSONField()  # keep everything

    class Meta:
        indexes = [
            models.Index(fields=['datetime']),        
            models.Index(fields=['sonde']),
            models.Index(fields=['sonde', 'datetime']) 
        ]

class Prediction(models.Model):
    sonde = models.ForeignKey(Sonde, on_delete=models.CASCADE, related_name='predictions')
    raw = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['sonde']),
        ]