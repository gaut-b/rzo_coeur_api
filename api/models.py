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

    def __str__(self):
        return self.name

class Magasin(models.Model):
    id_magasin = models.BigIntegerField(primary_key=True)
    name = models.CharField(max_length=100)
    address = models.CharField(max_length=200)
    centre_social = models.ForeignKey(Centre_social, on_delete=models.CASCADE)

    def __str__(self):
        return self.name


class Beneficiaire(models.Model):
    #TODO: id must be generated 
    id_beneficiaire = models.BigIntegerField(primary_key=True)
    name = models.CharField(max_length=50)
    email = models.EmailField(max_length=50)
    centre_social = models.ForeignKey(Centre_social, on_delete=models.CASCADE)

    def __str__(self):
        return self.name


class Article_scanned(models.Model):
    name = models.CharField(max_length=50)
    code_barre = models.BigIntegerField(primary_key=True)
    qte_suspendus = models.IntegerField()
    client_origine = models.ForeignKey(Client, on_delete=models.CASCADE)
    magasin_origine = models.ForeignKey(Magasin, on_delete=models.CASCADE)

    def __str__(self):
        return self.name

class ArticleAssigne(models.Model):
    article = models.ForeignKey(Article_scanned, on_delete=models.CASCADE)
    centre_social = models.ForeignKey(Centre_social, on_delete=models.CASCADE)

class Panier(models.Model):
    id_panier = models.BigIntegerField(primary_key=True)
    article_assigne = models.ForeignKey(ArticleAssigne, on_delete=models.CASCADE)
    magasin = models.ForeignKey(Magasin, on_delete=models.CASCADE)

    def __str__(self):
        return self.id_panier
