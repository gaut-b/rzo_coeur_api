from django.contrib import admin
from django.contrib.auth.models import Group
from django.contrib.auth.admin import GroupAdmin

from django.db import models

from .models import Shop
from .models import SocialCenter
from .models import Recipient
from .models import Client
from .models import User
from .models import Cart
# Register your models here.

admin.site.register(Shop)
admin.site.register(SocialCenter)
admin.site.register(Recipient)
admin.site.register(Client)
admin.site.register(User)
admin.site.register(Cart)
