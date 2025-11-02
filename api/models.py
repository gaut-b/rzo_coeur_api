from django.db import models


class User(models.Model):
    role = models.CharField(max_length=100)

    ROLES = [
        ('SUPER_ADMIN', 'super admin'),
        ('DONOR', 'Donor'),
        ('RECIPIENT', 'Recipient'),
        ('CASHIER', 'Cashier'),
        ('STORE_OWNER', 'Store owner')
        ('SOCIAL_DIRECTOR', 'Social Director'),
        ('SOCIAL_WORKER', 'Social Worker'),
    ]

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
    name = models.CharField(max_length=50)
    email = models.EmailField(max_length=50)

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
    centre_social = models.ForeignKey(SocialCenter, on_delete=models.CASCADE)
    # Methods proposal
    # - create article list
    # - notify list suspendus

    class Meta:
        permissions = [
            ("can_create_client", "Can create a client object"),
            ("can_create_article_scanned", "Can create a list of scanned articles"),
        ]

    def __str__(self):
        return self.name


class Recipient(models.Model):
    # TODO: id must be generated
    name = models.CharField(max_length=50)
    email = models.EmailField(max_length=50)
    centre_social = models.ForeignKey(SocialCenter, on_delete=models.CASCADE)
    # Methods proposal
    # - register panier

    def __str__(self):
        return self.name


class ScannedArticle(models.Model):
    name = models.CharField(max_length=50)
    code_barre = models.BigIntegerField(primary_key=True)
    qte_suspendus = models.IntegerField()
    client_origine = models.ForeignKey(Client, on_delete=models.CASCADE)
    magasin_origine = models.ForeignKey(Shop, on_delete=models.CASCADE)
    # Methods proposal
    # - save changes the quantity ? fait un get client & magasin : save est fait par le magasin
    #

    def __str__(self):
        return self.name


class AssignedArticle(models.Model):
    article = models.ForeignKey(ScannedArticle, on_delete=models.CASCADE)
    centre_social = models.ForeignKey(SocialCenter, on_delete=models.CASCADE)
    # Methods proposal
    # -


class Cart(models.Model):
    article_assigne = models.ForeignKey(
        AssignedArticle, on_delete=models.CASCADE)
    magasin = models.ForeignKey(Shop, on_delete=models.CASCADE)

    # Methods proposal
    # -
    def __str__(self):
        return self.id_panier
