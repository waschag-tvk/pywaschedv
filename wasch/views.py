import datetime
from django.shortcuts import render
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout as auth_logout
from chartjs.views.lines import BaseLineChartView
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
    users = Users.select(Users.login).execute()
    machines = Waschmaschinen.select(Waschmaschinen.id).execute()
    appointents = Termine.select(Termine.user).execute()
    context = {
        'userscount': len(users),
        'machinescount': len(machines),
        'appointmentscount': len(appointents),
    }
    return render(request, 'wasch/stats.html', context)


def _appointments_per_day(day, used=None):
    query = Termine.select(Termine.datum, Termine.wochentag).where(
        Termine.datum.year == day.year,
        Termine.datum.month == day.month,
        Termine.datum.day == day.day,
    )
    if used is not None:
        query = query.where(
            (Termine.wochentag == 8) == used,
        )
    return len(query.execute())


def _appointments_per_floor(floor, used=None):
    users = Users.select(Users.id).where(
        Users.zimmer > 100 * floor,
        Users.zimmer < 100 * (floor + 1),
    )
    count = 0
    for user in users:
        query = Termine.select(Termine.wochentag).where(Termine.user == user)
        if used is not None:
            query = query.where(
                (Termine.wochentag == 8) == used,
            )
        count += len(query.execute())
    return count


class AppointmentsPerDayChart(BaseLineChartView):
    def __init__(self, *args, **kwargs):
        BaseLineChartView.__init__(self, *args, **kwargs)
        end = datetime.date.today()
        self.steps = 3
        self.duration = 30
        self.days = [
            end + datetime.timedelta(days=d) for d in range(-self.duration, 0, self.steps)]

    def get_labels(self):
        """Return 10 labels for the x-axis."""
        return [str(d) for d in self.days]

    def get_providers(self):
        """Return names of datasets."""
        return ["Appointments", "Used"]

    def get_data(self):
        """Return 2 datasets to plot."""
        return [
            [sum(_appointments_per_day(start - datetime.timedelta(days=i)) for i in range(self.steps)) for start in self.days],
            [sum(_appointments_per_day(start - datetime.timedelta(days=i), used=True) for i in range(self.steps)) for start in self.days],
        ]


class AppointmentsPerFloorChart(BaseLineChartView):
    floors = list(range(0, 17))

    def get_labels(self):
        """Return 10 labels for the x-axis."""
        return [str(f) for f in self.floors]

    def get_providers(self):
        """Return names of datasets."""
        return ["Appointments", "Used"]

    def get_data(self):
        """Return 2 datasets to plot."""
        return [
            [_appointments_per_floor(floor) for floor in self.floors],
            [_appointments_per_floor(floor, used=True) for floor in self.floors],
        ]
