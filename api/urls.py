from django.urls import path

from .views import ArticleCreateView, CartCollectView

urlpatterns = [
    path("articles/", ArticleCreateView.as_view(), name="article-create"),
    path(
        "recipients/<int:recipient_id>/carts/<int:cart_id>/collect/",
        CartCollectView.as_view(),
        name="cart-collect",
    ),
]
