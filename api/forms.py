from django import forms
from .models import Cart, Shop


class CreateCartForm(forms.Form):
    shop = forms.ModelChoiceField(queryset=Shop.objects.all(), widget=forms.Select(attrs={"class": "form-control"}))

    class Meta:
        model = Cart
        fields = ["shop"]
