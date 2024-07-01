from django.http import HttpResponse
from django.urls import re_path


def home(request):
    return HttpResponse("WE LOVE DJANGO")


urlpatterns = [
    re_path(r"^$", home, name="homepage"),
]
