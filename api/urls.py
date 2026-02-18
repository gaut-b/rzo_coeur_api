from django.urls import path

from .views import (
    ArticleBarcodeView,
    ArticleCreateView,
    ArticleGetListView,
    ArticlePhotoUploadView,
    CartCollectView,
    CartDetailView,
    RecipientCartListView,
    ShopDetailView,
    ShopListView,
)

urlpatterns = [
    path("articles/", ArticleCreateView.as_view(), name="article-create"),
    path("articles/barcode/<int:barcode>/", ArticleBarcodeView.as_view(), name="article-barcode"),
    path("articles/photos/", ArticlePhotoUploadView.as_view(), name="article-photo-upload"),
    path("clients/me/articles/", ArticleGetListView.as_view(), name="client-articles-list"),
    path("recipients/me/carts/", RecipientCartListView.as_view(), name="recipient-carts-list"),
    path("carts/<int:cart_id>/", CartDetailView.as_view(), name="cart-detail"),
    path(
        "recipients/<int:recipient_id>/carts/<int:cart_id>/collect/",
        CartCollectView.as_view(),
        name="cart-collect",
    ),
    path("shops/", ShopListView.as_view(), name="shop-list"),
    path("shops/<int:shop_id>/", ShopDetailView.as_view(), name="shop-detail"),
]
