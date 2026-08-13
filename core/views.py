from django.shortcuts import render

def home(request):
    return render(request, 'home.html')

def about(request):
    return render(request, 'about.html')  # Если есть about.html, иначе просто pass

def map_view(request):
    return render(request, 'map.html')    # Если есть map.html