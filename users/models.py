import os
import uuid
from django.db import models
from django.conf import settings
from settings.models import *
from django.contrib.auth.models import AbstractUser

class Person(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True, null=True, blank=True)
    # role = models.ForeignKey(UserRole, on_delete=models.SET_NULL, null=True, blank=True, db_column="role_id", related_name="users")
    # personType = models.ForeignKey(PersonType, on_delete=models.SET_NULL, null=True, blank=True, db_column="person_type_id", related_name="users")
    # employmentMode = models.ForeignKey(EmploymentMode, on_delete=models.SET_NULL, null=True, blank=True,db_column="employment_model_id", related_name="users")
    # rateType = models.ForeignKey(RateType, on_delete=models.SET_NULL, null=True, blank=True, db_column="rate_type_id", related_name="users")
    # status = models.ForeignKey(Status, on_delete=models.SET_NULL, null=True, blank=True, db_column="status_id", related_name="users")
    dateStarted = models.DateField(null=True, blank=True)
    dateEnded = models.DateField(null=True, blank=True)
    deleted = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']


