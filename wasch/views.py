from django.shortcuts import render
from django.http import HttpResponse, HttpResponseRedirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout as auth_logout
from legacymodels import Users, Termine, Waschmaschinen


def index_view(request):
    """Returns the index view page."""
    if request.user.is_authenticated:
        return HttpResponseRedirect('/wasch/stats/')
    else:
        return render(request, 'wasch/index.html')


def check_login_view(request):
    """Authenticates the users login credentials."""
    username = request.POST['username']
    password = request.POST['password']
    user = authenticate(request, username=username, password=password)
    if user is not None:
        login(request, user)
        return HttpResponse('this is a test response')
    else:
        return HttpResponse('unauthorized', status=401)

@login_required
def stats(request):
    """Show usage stats"""
    users = Users.select().execute()
    machines = Waschmaschinen.select().execute()
    appointents = Termine.select().execute()
    context = {
        'userscount': len(users),
        'machinescount': len(machines),
        'appointmentscount': len(appointents),
    }
    return render(request, 'wasch/stats.html', context)
