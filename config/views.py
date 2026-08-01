from django.http import HttpResponse
from django.shortcuts import render


def home(request):
    return render(request, 'home.html')


def about(request):
    return HttpResponse("Это сайт «Путь наблюдателя». Здесь будут курсы, форум и ментальные карты.")

def map_view(request):
    return render(request, 'map.html')