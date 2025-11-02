from django.db import models
from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    role = models.CharField(
        max_length=100
        roles=[
            ('SUPER_ADMIN', 'super admin'),
            ('DONOR', 'Donor'),
            ('RECIPIENT', 'Recipient'),
            ('CASHIER', 'Cashier'),
            ('STORE_OWNER', 'Store owner')
            ('SOCIAL_DIRECTOR', 'Social Director'),
            ('SOCIAL_WORKER', 'Social Worker'),
        ]
    ),

    class Meta:
        permissions = [
            ("can_create_shop", "Can create a shop in DB"),
            ("can_create_cashier", "Can create a cashier in DB")
            ("can_create_social_center", "Can create a social center in DB")
            ("can_create_social_worker", "Can create a social worker in DB")
            ("can_create_recipient", "Can create a recipient in DB")
            ("can_create_article", "Can create a article in DB")
            ("can_create_cart", "Can create cart in DB")
        ]

    def __str__(self):
        return self.name


class Client(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)

    def __str__(self):
        return self.name


class SocialWorker(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    social_center = models.OneToOneField(SocialCenter, on_delete=models.CASCADE, "worker")

    def __str__(self):
        return self.name


class Cashier(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    shop = models.OneToOneField(Shop, on_delete=models.CASCADE, "cashier")

    def __str__(self):
        return self.name


class Recipient(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    social_center = models.ForeignKey(SocialCenter, on_delete=models.CASCADE)
    # Methods proposal
    # - register panier

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


class Shop(models.Model):
    name = models.CharField(max_length=100)
    address = models.CharField(max_length=200)
    social_center = models.ForeignKey(SocialCenter, on_delete=models.CASCADE)
    # Methods proposal
    # - create article list
    # - notify list suspendus

    return self.name


class Article(models.Model):
    name = models.CharField(max_length=50)
    barcode = models.BigIntegerField()
    client = models.ForeignKey(Client, on_delete=models.CASCADE, "articles")
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, "articles")
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, "articles")

    class Meta:
        indexes = [
            Models.Index(fields=['barcode'])
        ]

    def __str__(self):
        return self.name


class Cart(models.Model):
    article_assigne = models.ForeignKey(
        AssignedArticle, on_delete=models.CASCADE)
    magasin = models.ForeignKey(Shop, on_delete=models.CASCADE)
    recipient = models.ForeignKey(Client, on_delete=models.CASCADE, "carts")
    status = models.Charfield(
        max_length=20
        states=[
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
