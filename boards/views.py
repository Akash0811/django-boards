from django.shortcuts import render , redirect
from django.http import Http404
from .models import Board , Topic , Post
from django.contrib.auth.models import User
from .forms import NewTopicForm , PostForm
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.views.generic import UpdateView
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.generic import ListView
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.urls import reverse_lazy , reverse

class BoardListView(ListView):
    model = Board
    context_object_name = 'boards'
    template_name = 'home.html'


def board_topics(request, board_id):
    try:
        board = Board.objects.get(pk=board_id)
    except Board.DoesNotExist:
        raise Http404
    queryset = board.topics.order_by('-last_updated').annotate(replies=Count('posts') - 1)
    page = request.GET.get('page', 1)

    paginator = Paginator(queryset, 20)

    try:
        topics = paginator.page(page)
    except PageNotAnInteger:
        # fallback to the first page
        topics = paginator.page(1)
    except EmptyPage:
        # probably the user tried to add a page number
        # in the url, so we fallback to the last page
        topics = paginator.page(paginator.num_pages)
    return render(request, 'topics.html', {'board': board, 'topics': topics})

@login_required
def new_topic(request, board_id):
    try:
        board = Board.objects.get(pk=board_id)
    except Board.DoesNotExist:
        raise Http404
    if request.method == 'POST':
        form = NewTopicForm(request.POST)
        if form.is_valid():
            topic = form.save(commit=False)
            topic.board = board
            topic.starter = request.user
            topic.save()
            post = Post.objects.create(
                message=form.cleaned_data.get('message'),
                topic=topic,
                created_by=request.user
            )
            return redirect('topic_posts', board_id = board_id , topic_pk = topic.pk)
    else:
        form = NewTopicForm()
    return render(request, 'new_topic.html', {'board': board , 'form': form})

class PostListView(ListView):
    model = Post
    context_object_name = 'posts'
    template_name = 'topic_posts.html'
    paginate_by = 2

    def get_context_data(self, **kwargs):
        session_key = 'viewed_topic_{}'.format(self.topic.pk)  # <-- here
        if not self.request.session.get(session_key, False):
            self.topic.views += 1
            self.topic.save()
            self.request.session[session_key] = True
        kwargs['topic'] = self.topic
        return super().get_context_data(**kwargs)

    def get_queryset(self):
        try:
            self.topic = Topic.objects.get(board__pk=self.kwargs.get('board_id'), pk=self.kwargs.get('topic_pk'))
        except Board.DoesNotExist:
            raise Http404
        queryset = self.topic.posts.order_by('created_at')
        return queryset

@login_required
def reply_topic(request, board_id, topic_pk):
    try:
        topic = Topic.objects.get(board__pk=board_id, pk=topic_pk)
    except Board.DoesNotExist:
        raise Http404
    if request.method == 'POST':
        form = PostForm(request.POST)
        if form.is_valid():
            post = form.save(commit=False)
            post.topic = topic
            post.created_by = request.user
            post.save()
            topic.last_updated = timezone.now()  # <- here
            topic.save()
            topic_url = reverse('topic_posts', kwargs={'board_id': board_id, 'topic_pk': topic_pk})
            topic_post_url = '{url}?page={page}#{id}'.format(
                url=topic_url,
                id=post.pk,
                page=topic.get_page_count()
            )

            return redirect(topic_post_url)
    else:
        form = PostForm()
    return render(request, 'reply_topic.html', {'topic': topic, 'form': form})

@method_decorator(login_required, name='dispatch')
class PostUpdateView(UpdateView):
    model = Post
    fields = ('message', )
    template_name = 'edit_post.html'
    pk_url_kwarg = 'post_pk'
    context_object_name = 'post'

    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset.filter(created_by=self.request.user)

    def form_valid(self, form):
        post = form.save(commit=False)
        post.updated_by = self.request.user
        post.updated_at = timezone.now()
        post.save()
        return redirect('topic_posts', board_id=post.topic.board.pk, topic_pk=post.topic.pk)
