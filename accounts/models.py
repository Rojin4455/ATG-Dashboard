# models.py
from django.db import models
from django.utils import timezone
import uuid
from django.contrib.postgres.fields import ArrayField, JSONField


class GHLAuthCredentials(models.Model):
    user_id = models.CharField(max_length=255, unique=True)
    access_token = models.TextField()
    refresh_token = models.TextField()
    expires_in = models.IntegerField()
    scope = models.CharField(max_length=500, null=True, blank=True)
    user_type = models.CharField(max_length=50, null=True, blank=True)
    company_id = models.CharField(max_length=255, null=True, blank=True)
    location_id = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user_id} - {self.company_id}"
    

class Webhook(models.Model):
    event = models.CharField(max_length=100)
    company_id = models.CharField(max_length=100)
    payload = models.JSONField()  # Store the entire raw payload
    received_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.event} - {self.company_id}"
    



class Opportunity(models.Model):
    id = models.CharField(primary_key=True, max_length=50)
    name = models.CharField(max_length=255)
    monetary_value = models.DecimalField(max_digits=12, decimal_places=2)
    pipeline_id = models.CharField(max_length=50)
    pipeline_name = models.CharField(max_length=255, blank=True, null=True)
    pipeline_stage_id = models.CharField(max_length=50)
    pipeline_stage_name = models.CharField(max_length=255, blank=True, null=True)
    assigned_to = models.CharField(max_length=50, blank=True, null=True)
    assigned_user_name = models.CharField(max_length=50, blank=True, null=True)
    assigned_user_email = models.CharField(max_length=50, blank=True, null=True)
    status = models.CharField(max_length=50)


    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    contact_id = models.CharField(max_length=50)
    contact_name = models.CharField(max_length=255)
    contact_company_name = models.CharField(max_length=255, blank=True, null=True)
    contact_email = models.EmailField(blank=True, null=True)
    contact_phone = models.CharField(max_length=20, blank=True, null=True)
    contact_tags = ArrayField(models.CharField(max_length=100), blank=True, default=list)

    location_id = models.CharField(max_length=50, blank=True, null=True)


    def __str__(self):
        return self.name