from django.shortcuts import render
from django.views.generic import ListView, CreateView
from django.urls import reverse_lazy
from .models import Observation
from .forms import ObservationForm

# Главная страница с лентой наблюдений
class ObservationListView(ListView):
    model = Observation
    template_name = 'myapp/observation_list.html'
    context_object_name = 'observations'
    ordering = ['-created_at']  # Сортируем от новых к старым

# Страница добавления нового наблюдения
class ObservationCreateView(CreateView):
    model = Observation
    form_class = ObservationForm
    template_name = 'myapp/observation_form.html'
    success_url = reverse_lazy('myapp:observation_list') # После добавления вернет в ленту