from django.urls import path
from django.contrib.auth import views as auth_views

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
    CreateCartView,
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
    path("attri/add_cart", CreateCartView.as_view(), name="attri-cart-add"),
    path("attri/login/", auth_views.LoginView.as_view()),
]
