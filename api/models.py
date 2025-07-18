from django.db import models


class Utilisateur(models.Model):
    id_utilisateur = models.BigIntegerField(primary_key=True)
    role = models.CharField(max_length=100)

    def __str__(self):
        return self.name


class Client(models.Model):
    id_client = models.BigIntegerField(primary_key=True)
    name = models.CharField(max_length=50)
    email = models.EmailField(max_length=50)

    def __str__(self):
        return self.name


class Centre_social(models.Model):
    id_centre_social = models.BigIntegerField(primary_key=True)
    name = models.CharField(max_length=50)
    address = models.CharField(max_length=200)
    mail = models.CharField(max_length=200)

    class Meta:
        permissions = [
            ("can_create_magasin", "Can create a magasin object"),
            ("can_create_beneficiaire", "Can create a beneficiaire object"),
            ("can_create_panier", "Can create a panier object"),
            ("can_create_assign_article",
             "Can switch an article from scanned to assigned"),
        ]
    # def switch from scanned to assigned
    # register list article to magasin
    # create_panier : get from article_scanned list to article_assigned, create a panier
    #

    def __str__(self):
        return self.name


class Magasin(models.Model):
    id_magasin = models.BigIntegerField(primary_key=True)
    name = models.CharField(max_length=100)
    address = models.CharField(max_length=200)
    centre_social = models.ForeignKey(Centre_social, on_delete=models.CASCADE)
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


class Beneficiaire(models.Model):
    # TODO: id must be generated
    id_beneficiaire = models.BigIntegerField(primary_key=True)
    name = models.CharField(max_length=50)
    email = models.EmailField(max_length=50)
    centre_social = models.ForeignKey(Centre_social, on_delete=models.CASCADE)
    # Methods proposal
    # - register panier

    def __str__(self):
        return self.name


class Article_scanned(models.Model):
    name = models.CharField(max_length=50)
    code_barre = models.BigIntegerField(primary_key=True)
    qte_suspendus = models.IntegerField()
    client_origine = models.ForeignKey(Client, on_delete=models.CASCADE)
    magasin_origine = models.ForeignKey(Magasin, on_delete=models.CASCADE)
    # Methods proposal
    # - save changes the quantity ? fait un get client & magasin : save est fait par le magasin
    #

    def __str__(self):
        return self.name


class ArticleAssigne(models.Model):
    article = models.ForeignKey(Article_scanned, on_delete=models.CASCADE)
    centre_social = models.ForeignKey(Centre_social, on_delete=models.CASCADE)
    # Methods proposal
    # -


class Panier(models.Model):
    id_panier = models.BigIntegerField(primary_key=True)
    article_assigne = models.ForeignKey(
        ArticleAssigne, on_delete=models.CASCADE)
    magasin = models.ForeignKey(Magasin, on_delete=models.CASCADE)

    # Methods proposal
    # -
    def __str__(self):
        return self.id_panier
