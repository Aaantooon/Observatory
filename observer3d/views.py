from django.shortcuts import render

def babylon_world(request):
    return render(request, 'observer3d/world_babylon.html')
