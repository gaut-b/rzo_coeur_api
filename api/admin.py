from django.contrib import admin
from django.contrib.auth.models import Group
from django.contrib.auth.admin import GroupAdmin

from django.db import models

from .models import Magasin
from .models import Centre_social
from .models import Beneficiaire
from .models import Client
from .models import Utilisateur
# Register your models here.

admin.site.register(Magasin)
admin.site.register(Centre_social)
admin.site.register(Beneficiaire)
admin.site.register(Client)
admin.site.register(Utilisateur)
admin.site.register(Panier)
