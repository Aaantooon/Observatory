from django.shortcuts import render

def home(request):
    # Здесь мы поменяли 'index.html' на 'home.html', чтобы работала ваша страница с фонариком!
    return render(request, 'home.html', {
        'title': 'Главная — Путь наблюдателя',
        'subtitle': 'Фонарь рассеивает туман: шаг за шагом мы видим путь'
    })

def about(request):
    return render(request, 'about.html', {
        'title': 'О проекте — Путь наблюдателя'
    })

def map_view(request):
    return render(request, 'map.html', {
        'title': 'Карта пути наблюдателя'
    })

def observer_view(request):
    return render(request, 'observer_map.html')

def put_view(request):
    return render(request, 'put.html')