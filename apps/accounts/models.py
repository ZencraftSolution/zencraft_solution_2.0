from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    job_title = models.CharField(max_length=120, blank=True)
    phone = models.CharField(max_length=40, blank=True)

    class Meta:
        ordering = ["first_name", "username"]

    def __str__(self):
        return self.get_full_name() or self.username
