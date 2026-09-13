from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, render

from .models import BlogCategory, BlogPost


def post_list(request, category=None):
    posts = BlogPost.objects.filter(is_published=True).select_related("category", "author")
    active_category = None
    if category:
        active_category = get_object_or_404(BlogCategory, slug=category)
        posts = posts.filter(category=active_category)
    q = request.GET.get("q", "").strip()
    if q:
        query = SearchQuery(q, search_type="websearch")
        vector = SearchVector("title", weight="A") + SearchVector("excerpt", "tags", weight="B") + SearchVector("body", weight="C")
        posts = posts.annotate(rank=SearchRank(vector, query)).filter(rank__gt=0.01).order_by("-rank")
    page = Paginator(posts, 9).get_page(request.GET.get("page"))
    return render(request, "blog/list.html", {
        "page": page,
        "categories": BlogCategory.objects.all(),
        "active_category": active_category,
        "q": q,
        "lead": page.object_list[0] if page.number == 1 and not q and not category and page.object_list else None,
    })


def post_detail(request, slug):
    post = get_object_or_404(BlogPost.objects.select_related("category", "author"), slug=slug, is_published=True)
    related = BlogPost.objects.filter(is_published=True, category=post.category).exclude(pk=post.pk)[:3]
    return render(request, "blog/detail.html", {"post": post, "related": related})
