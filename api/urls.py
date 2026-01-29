from django.urls import path

from .admin import social_admin_site
from .views import (
    ArticleCreateView,
    ArticleGetListView,
    CartCollectView,
    CartDetailView,
    RecipientCartListView,
    ShopDetailView,
    ShopListView,
    AttributionsView,
)

urlpatterns = [
    path("articles/", ArticleCreateView.as_view(), name="article-create"),
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
    path("social-admin/", social_admin_site.urls),
    path("attri/", AttributionsView.as_view(), name="attri"),
]
