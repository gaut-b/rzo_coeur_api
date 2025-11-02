from django.db import models
from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    pass


class Client(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)

    def __str__(self):
        return self.name


class SocialCenter(models.Model):
    name = models.CharField(max_length=50)
    address = models.CharField(max_length=200)
    mail = models.CharField(max_length=200)

    # def switch from scanned to assigned
    # register list article to magasin
    # create_panier : get from article_scanned list to article_assigned, create a panier
    #

    def __str__(self):
        return self.name


class SocialWorker(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    social_center = models.OneToOneField(
        SocialCenter, on_delete=models.CASCADE, related_name="worker")

    def __str__(self):
        return self.name


class Recipient(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    social_center = models.ForeignKey(SocialCenter, on_delete=models.CASCADE)
    # Methods proposal
    # - register panier

    def __str__(self):
        return self.name


class Shop(models.Model):
    name = models.CharField(max_length=100)
    address = models.CharField(max_length=200)
    social_center = models.ForeignKey(SocialCenter, on_delete=models.CASCADE)
    # Methods proposal
    # - create article list
    # - notify list suspendus

    def __str__(self):
        return self.name


class Cashier(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    shop = models.OneToOneField(
        Shop, on_delete=models.CASCADE, related_name="cashier")

    def __str__(self):
        return self.name


class Cart(models.Model):
    magasin = models.ForeignKey(Shop, on_delete=models.CASCADE)
    recipient = models.ForeignKey(
        Client, on_delete=models.CASCADE, related_name="carts")
    status = models.CharField(
        max_length=20,
        choices=[
            ('PENDING', 'Pending assignment'),
            ('ASSIGNED', 'Assigned to beneficiary'),
            ('COLLECTED', 'Collected'),
        ],
        default='PENDING'
    )

    # Methods proposal
    # -

    def __str__(self):
        return self.id_panier


class Article(models.Model):
    name = models.CharField(max_length=50)
    barcode = models.BigIntegerField()
    client = models.ForeignKey(
        Client, on_delete=models.CASCADE, related_name="articles")
    shop = models.ForeignKey(
        Shop, on_delete=models.CASCADE, related_name="articles")
    cart = models.ForeignKey(
        Cart, on_delete=models.CASCADE, related_name="articles")

    class Meta:
        indexes = [
            models.Index(fields=['barcode'])
        ]

    def __str__(self):
        return self.name
