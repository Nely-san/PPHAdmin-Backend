from django.db import models
from core.models import BaseModel

class Company(BaseModel):
    """
    Company Entity representing the corporate organization or subsidiary.
    """
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=50, unique=True, null=True, blank=True)

    class Meta:
        db_table = 'companies'
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.code})" if self.code else self.name


class Department(BaseModel):
    """
    Department or Branch under a Company.
    """
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='departments')
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=50, null=True, blank=True)

    class Meta:
        db_table = 'departments'
        ordering = ['company', 'name']

    def __str__(self):
        return f"{self.company.name} - {self.name}"
