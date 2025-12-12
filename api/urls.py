from django.urls import path

from .views import ArticleCreateView, ArticleGetListView, CartCollectView

urlpatterns = [
    path("articles/", ArticleCreateView.as_view(), name="article-create"),
    path("clients/me/articles/", ArticleGetListView.as_view(), name="client-articles-list"),
    path(
        "recipients/<int:recipient_id>/carts/<int:cart_id>/collect/",
        CartCollectView.as_view(),
        name="cart-collect",
    ),
]
