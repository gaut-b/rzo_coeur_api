from django.contrib import admin

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
