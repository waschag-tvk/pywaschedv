from django.shortcuts import render
from django.http import HttpResponse


def index_view(request):
    """Returns the index view page."""
    return render(request, 'wasch/index.html')


def login_view(request):
    """Returns the login page."""
    return render(request, 'wasch/login.html')


def check_login_view(request):
    """Authenticates the users login credentials."""
    return HttpResponse('this is a test response')
