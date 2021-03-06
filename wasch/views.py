import datetime
from django.shortcuts import render
from django.urls import reverse
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.views.decorators.http import require_http_methods
from django.utils.html import format_html
from django.contrib.auth.decorators import login_required
from django.contrib.auth import (
    authenticate, login, logout as auth_logout, models as auth_models,
)
from django.contrib.admin.views.decorators import staff_member_required
from django.utils.six import BytesIO
from django.conf import settings
from rest_framework.parsers import JSONParser
from rest_framework.renderers import JSONRenderer
from chartjs.views.lines import BaseLineChartView
import django_tables2
from wasch.models import WashingMachine, Appointment, WashUser, WashParameters
from wasch.models import AppointmentError  # not models
from wasch.serializers import AppointmentSerializer
from wasch import tvkutils
from wasch import payment

if settings.WASCH_USE_LEGACY:
    from legacymodels import Users, Termine, Waschmaschinen
    from peewee import OperationalError


def _user_alerts(user):
    try:
        if WashUser.objects.get(pk=user).isActivated:
            return []  # everything fine
    except WashUser.DoesNotExist:
        pass
    return [{
        'text':
            'You ({}) are not active! '
            'Please contact a staff to get activated.'.format(user.username),
        'class': 'warning',
    }]


class PersonalAppointmentsTable(django_tables2.Table):
    """Personal, thus not showing username"""
    class Meta:
        template = 'django_tables2/bootstrap.html'
        model = Appointment
        fields = ('time', 'machine', 'wasUsed', 'canceled')


@login_required
def index_view(request):
    """Returns the index view page."""
    myAppointments = Appointment.objects.filter(user=request.user)
    context = {
        'waschAlerts': _status_alerts() + _user_alerts(request.user),
        'my_appointments_table': PersonalAppointmentsTable(myAppointments)
    }
    return render(request, 'wasch/index.html', context)


def welcome_view(request):
    """Returns the welcome page."""
    return render(request, 'wasch/welcome.html')


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


def legacy_method(
        method, retval=HttpResponse('Legacy feature unavailable', status=500)):
    if not settings.WASCH_USE_LEGACY:
        return method
    def quiet_method(*args, **kwargs):
        try:
            return method(*args, **kwargs)
        except OperationalError:
            print('legacy_method got OperationalError')
            return retval
    return quiet_method


@login_required
@legacy_method
def stats(request):
    """Show usage stats"""
    if settings.WASCH_USE_LEGACY:
        users_count = len(Users.select(Users.login).execute())
        machines_count = len(
            Waschmaschinen.select(Waschmaschinen.id).execute())
        appointents_count = len(Termine.select(Termine.user).execute())
    else:
        users_count = WashUser.objects.count()
        machines_count = WashingMachine.objects.count()
        appointents_count = Appointment.objects.filter(canceled=False).count()
    context = {
        'userscount': users_count,
        'machinescount': machines_count,
        'appointmentscount': appointents_count,
    }
    return render(request, 'wasch/stats.html', context)


class WashingMachineTable(django_tables2.Table):
    class Meta:
        model = WashingMachine
        template = 'django_tables2/bootstrap.html'


@login_required
def status(request):
    """Show service status"""
    machines = WashingMachineTable(WashingMachine.objects.all())
    django_tables2.RequestConfig(request).configure(machines)
    context = {
        'machines_table': machines,
    }
    return render(request, 'wasch/status.html', context)


APPOINTMENT_ATTR_TEMPLATE = 'appointment_m{:d}'


class AppointmentColumn(django_tables2.Column):
    def render(self, value):
        """
        :param value tuple: time, machine, user
        """
        time, machine, user = value
        if Appointment.manager.bookable(time=time, machine=machine, user=user):
            appointment = Appointment(time=time, user=user, machine=machine)
            appointment_serial = AppointmentSerializer(appointment)
            apjson = JSONRenderer().render(appointment_serial.data)
            book_link = reverse('wasch:do_book', args=[apjson])
            return format_html(
                '<a href="{}?confirm">Book now</a>',
                book_link, machine.number)
        try:  # if it's my appointment
            appointment = Appointment.objects.get(
                time=time, user=user, machine=machine)
            cancel_link = reverse('wasch:do_cancel', args=[appointment.pk])
            return format_html(
                'You booked this! '
                '<a href="{}" class="btn btn-danger btn-sm">'
                'Cancel appointment</a>'.format(cancel_link))
        except Appointment.DoesNotExist:
            return 'Not available'


class AppointmentTable(django_tables2.Table):
    time = django_tables2.Column()
    appointment_m1 = AppointmentColumn()
    appointment_m2 = AppointmentColumn()
    appointment_m3 = AppointmentColumn()

    class Meta:
        template = 'django_tables2/bootstrap.html'


def _appointment_table_row(time, machines, user):
    row = {
        'time': time.isoformat(),
    }
    for machine in machines:
        row[APPOINTMENT_ATTR_TEMPLATE.format(machine.number)] = (
            time, machine, user,
        )
    return row


def _status_alerts():
    unavailableMachines = WashingMachine.objects.filter(isAvailable=False)
    return [{
        'text': '{} is not available!'.format(machine),
        'class': 'warning',
    } for machine in unavailableMachines]


@login_required
def bonus(request):
    maximum_display_value = 499  # XXX this is arbitrary
    method = WashParameters.objects.get_value('bonus-method')
    display_balance = payment.coverage(
            maximum_display_value, request.user, method)
    context = {
        'balance': display_balance,
        'currency': 'EUR',
    }
    return render(request, 'wasch/bonus.html', context)


@login_required
def book(request, appointment=None, cancel_appointment_pk=None):
    """Offer appointments for booking"""
    context = {
        'waschAlerts': _status_alerts(),
    }
    if appointment is not None:
        with BytesIO(appointment.encode()) as apstream:
            apdata = JSONParser().parse(apstream)
        appointment_serial = AppointmentSerializer(data=apdata)
        if appointment_serial.is_valid():
            apval = appointment_serial.validated_data
            if 'confirm' in request.GET:
                context['washer_time'] = str(apval['time'])
                context['price'] = '{:.2f} EUR'.format(
                    int(WashParameters.objects.get_value('price')) / 100.)
                context['appointment_str'] = appointment
                return render(request, 'wasch/book-confirm.html', context)
            try:
                appointment = Appointment.manager.make_appointment(
                    apval['time'], apval['machine'], request.user)
                context['message'] = 'You just booked {} for {}!'.format(
                    appointment.machine, appointment.time)
            except AppointmentError:
                context['message'] = (
                    'Appointment for {} at {} seems no longer available!'
                    .format(apval['machine'], apval['time']))
            except payment.PaymentError:
                context['message'] = 'Payment has failed!'
        else:
            context['message'] = 'Something went wrong!'
    elif cancel_appointment_pk is not None:
        try:
            appointment = Appointment.objects.get(
                pk=cancel_appointment_pk, user=request.user)
            appointment.cancel()
            context['message'] = (
                'Appointment for {} at {} has been canceled!'
                .format(appointment.machine, appointment.time))
        except PaymentError:
            context['message'] = 'Payment has failed!'
        except AppointmentError:
            context['message'] = (
                'Appointment for {} at {} can not be canceled!'
                .format(appointment.machine, appointment.time))
        except Appointment.DoesNotExist:
            context['message'] = 'Something went wrong!'
    machines = tuple(WashingMachine.objects.filter(isAvailable=True))
    table = AppointmentTable([
        _appointment_table_row(appointment_time, machines, request.user)
        for appointment_time
        in Appointment.manager.scheduled_appointment_times()])
    context['appointments_table'] = table
    Appointment.manager.prefetch_bookable(users=(request.user, ))
    return render(request, 'wasch/book.html', context)


def _appointments_per_day(day, used=None):
    if settings.WASCH_USE_LEGACY:
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
    return Appointment.objects.filter(time__date=day).count()


def _appointments_per_floor(floor, used=None):
    if settings.WASCH_USE_LEGACY:
        users = Users.select(Users.id).where(
            Users.zimmer > 100 * floor,
            Users.zimmer < 100 * (floor + 1),
        )
        count = 0
        for user in users:
            query = Termine.select(Termine.wochentag).where(
                Termine.user == user)
            if used is not None:
                query = query.where(
                    (Termine.wochentag == 8) == used,
                )
            count += len(query.execute())
        return count
    elif floor == 0:  # XXX just show everything here
        if used is not None:
            return Appointment.objects.filter(wasUsed=used).count()
        return Appointment.objects.filter(canceled=False).count()
    else:
        return 0


class AppointmentsPerDayChart(BaseLineChartView):
    def __init__(self, *args, **kwargs):
        BaseLineChartView.__init__(self, *args, **kwargs)
        self.steps = 3
        self.duration = 30
        end = datetime.date.today() + datetime.timedelta(days=self.steps)
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


@staff_member_required
def setup(request):
    """Populate database with basic users and machines for TvK"""
    created = tvkutils.setup()
    message = 'created {}'.format(created) if created else 'nothing done'
    context = {
        'title': 'Setup done!',
        'contents': message,
    }
    return render(request, 'wasch/info.html', context)
