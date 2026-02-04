"""
Blog Views - Server-side rendered views for SEO
"""

from django.shortcuts import render, get_object_or_404
from django.views.generic import ListView, DetailView
from django.db.models import Q
from .models import Post, Category, Tag


def custom_404(request, exception=None):
    """Custom 404 page with nice styling."""
    return render(request, '404.html', status=404)


class PostListView(ListView):
    """Homepage listing all published posts."""
    model = Post
    template_name = 'blog/post_list.html'
    context_object_name = 'posts'
    paginate_by = 10
    
    def get_queryset(self):
        return Post.objects.filter(status='published').select_related(
            'author', 'category'
        ).prefetch_related('tags')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['categories'] = Category.objects.all()
        context['page_title'] = 'Fynda Fashion Blog'
        context['page_description'] = 'Your ultimate destination for fashion deals, style tips, and shopping inspiration.'
        return context


class PostDetailView(DetailView):
    """Individual blog post page."""
    model = Post
    template_name = 'blog/post_detail.html'
    context_object_name = 'post'
    
    def get_queryset(self):
        return Post.objects.filter(status='published').select_related(
            'author', 'category'
        ).prefetch_related('tags')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        post = self.object
        
        # Related posts (same category, excluding current)
        if post.category:
            context['related_posts'] = Post.objects.filter(
                status='published',
                category=post.category
            ).exclude(pk=post.pk)[:3]
        else:
            context['related_posts'] = Post.objects.filter(
                status='published'
            ).exclude(pk=post.pk)[:3]
        
        return context


class CategoryPostsView(ListView):
    """Posts filtered by category."""
    model = Post
    template_name = 'blog/category_posts.html'
    context_object_name = 'posts'
    paginate_by = 10
    
    def get_queryset(self):
        self.category = get_object_or_404(Category, slug=self.kwargs['slug'])
        return Post.objects.filter(
            status='published',
            category=self.category
        ).select_related('author', 'category').prefetch_related('tags')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['category'] = self.category
        context['categories'] = Category.objects.all()
        context['page_title'] = f'{self.category.name} | Fynda Blog'
        context['page_description'] = self.category.description or f'Browse {self.category.name} posts on Fynda Blog.'
        return context


class TagPostsView(ListView):
    """Posts filtered by tag."""
    model = Post
    template_name = 'blog/tag_posts.html'
    context_object_name = 'posts'
    paginate_by = 10
    
    def get_queryset(self):
        self.tag = get_object_or_404(Tag, slug=self.kwargs['slug'])
        return Post.objects.filter(
            status='published',
            tags=self.tag
        ).select_related('author', 'category').prefetch_related('tags')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['tag'] = self.tag
        context['categories'] = Category.objects.all()
        context['page_title'] = f'#{self.tag.name} | Fynda Blog'
        context['page_description'] = f'Posts tagged with {self.tag.name} on Fynda Blog.'
        return context


class SearchView(ListView):
    """Search blog posts."""
    model = Post
    template_name = 'blog/search.html'
    context_object_name = 'posts'
    paginate_by = 10
    
    def get_queryset(self):
        query = self.request.GET.get('q', '')
        if query:
            return Post.objects.filter(
                status='published'
            ).filter(
                Q(title__icontains=query) |
                Q(content__icontains=query) |
                Q(excerpt__icontains=query)
            ).select_related('author', 'category').prefetch_related('tags')
        return Post.objects.none()
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['query'] = self.request.GET.get('q', '')
        context['page_title'] = f"Search: {context['query']} | Fynda Blog"
        return context
