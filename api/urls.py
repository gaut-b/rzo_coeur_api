from django.urls import path

from .views import ArticleCreateView

urlpatterns = [
    path("articles/", ArticleCreateView.as_view(), name="article-create"),
]
