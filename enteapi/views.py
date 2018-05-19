import datetime
import json
import traceback
from django.contrib.auth.models import User
# from django.views.decorators.csrf import csrf_exempt
from rest_framework import viewsets
from rest_framework.decorators import detail_route, list_route
from rest_framework.parsers import JSONParser
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from wasch.models import (
    Appointment, STATUS_CHOICES, WashingMachine, WashUser, AppointmentError,
)
from wasch.serializers import AppointmentSerializer
from legacymodels import (
    Termine, DoesNotExist, Waschmaschinen, Users as LegacyUser,
)


def machine_ready(machineId, legacy=False):
    '''can throw WashingMachine.DoesNotExist if machineId wrong
    if legacy: legacymodels.DoesNotExist
    '''
    if legacy:
        state = Waschmaschinen.get(Waschmaschinen.id == machineId).status
        return state == 1
    return WashingMachine.objects.get(number=machineId).isAvailable


def time_from_legacy_zeit(zeit):
    hour = (zeit * 3) // 2
    minute = 30 * (zeit % 2)
    return datetime.time(hour, minute)


def appointment_from_legacy(Termine):
    time = datetime.datetime.combine(
            Termine.datum, time_from_legacy_zeit(Termine.zeit))
    # time = datetime.datetime(
    #        Termine.year, Termine.month, Termine.day, hour, minute)
    print('Termin found at {}'.format(time))
    # not reading from or writing to django database since id's might be
    # assigned differently
    legacy_user = LegacyUser.get(LegacyUser.id == Termine.user)
    user = WashUser(
        user=User(username=legacy_user.login),
        isActivated=not legacy_user.gesperrt,
    )
    status = legacy_user.status
    if any(status == choice for choice, _ in STATUS_CHOICES):
        user.status = status
    machine = WashingMachine(number=Termine.maschine)
    appointment = Appointment(time=time, user=user, machine=machine)
    if Termine.wochentag >= 8:
        appointment.wasUsed = True
    return appointment


def _legacy_use(reference):
    '''
    :param int bookingId:
    '''
    try:
        appointment = Appointment.from_reference(
            reference, allow_unsaved_machine=True)
    except ValueError:
        traceback.print_exc()
        return 'LEGACY_DATE_OUT_OF_RANGE'
    try:
        item = Termine.get(
            Termine.maschine == appointment.machine.number,
            Termine.zeit == appointment.appointment_number,
            Termine.datum == appointment.time.date(),
        )
    except DoesNotExist:
        return 'UNKNOWN_APPOINTMENT'
    if item.wochentag >= 8:
        return 'ALREADY_USED'
    try:
        if not machine_ready(item.maschine):
            return 'MACHINE_UNAVAILABLE'
    except DoesNotExist:
        return 'UNKNOWN_MACHINE'
    query = Termine.update(wochentag=8).where(
            Termine.maschine == item.maschine,
            Termine.zeit == item.zeit,
            Termine.datum == item.datum,
            Termine.wochentag < 8,
            )  # marks as used
    n = query.execute()
    if n != 1:
        print('query: {}'.format(n))
        return 'UNEXPECTED'
    return 'OK'


def _use(reference, enteId, user=None):
    enten = [
            1,
            ]
    try:
        r = reference  # int(reference, base=16)
        e = enteId  # int(enteId, base=16)
        if e not in enten:
            return 'UNKNOWN_ENTE'
    except ValueError:
        return 'INVALID_ID'
    if user is not None:
        try:
            appointment = Appointment.from_reference(reference, user)
        except ValueError:  # reference invalid for current system
            try_legacy = False
            if try_legacy:
                # for legacy appointment reference
                return _legacy_use(r)
            else:
                raise
    try:
        appointment.use()
    except AppointmentError as ae:
        if ae.reason == 21:
            return 'MACHINE_UNAVAILABLE'
        elif ae.reason == 61:
            return 'ALREADY_USED'
        return 'UNEXPECTED'  # TODO better distinction
    return 'OK'


ACTIVATE_PERIOD = datetime.timedelta(seconds=150*60)
# ACTIVATE_PERIOD = datetime.timedelta(days=27)  # XXX easy testing!


# TODO last appointment


class AppointmentViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = AppointmentSerializer
    parser_classes = (JSONParser,)
    renderer_classes = (JSONRenderer, )

    @detail_route(methods=['POST'], permission_classes=[IsAuthenticated])
    def activate(self, request, pk=None):
        allowed_remotes = [
                '127.0.0.1',
                ]
        remote = request.META['REMOTE_ADDR']
        if remote not in allowed_remotes:
            return Response({
                'error': 'remote {} not allowed'.format(remote)
                }, status=403)
        action = 'activate'
        reqdata = request.data
        if not isinstance(reqdata, dict):
            reqdata = json.loads(reqdata)
        enteId = reqdata['enteId']
        reference = Appointment.objects.get(pk=pk).reference
        error = _use(reference, enteId, request.user)
        print('activated appointment {} from ente {}@{} --> {}'.format(
            reference, enteId, request.META['REMOTE_ADDR'], error))
        return Response({
            'reference': reference,
            'ente-id': enteId,
            'action': action,
            'error': error,
            }, status=200 if error == 'OK' else 400)

    @list_route()
    def legacy_list(self, request):
        end = datetime.datetime.now()
        start = end - ACTIVATE_PERIOD
        # endzeit = (end.hour * 2 + start.minute // 30) // 3
        # startzeit = (start.hour * 2 + start.minute // 30) // 3
        # aday = datetime.timedelta(days=1)
        termine = Termine.select().where(
                Termine.datum.between(start.date(), end.date())
                # | (
                #     Termine.datum.between(start.date(), end.date() - aday)
                #     & Termine.zeit > startzeit
                # ) | (
                #     Termine.datum.between(start.date() + aday, end.date())
                #     & Termine.zeit < endzeit
                # ) | (
                #     Termine.datum.between(start.date(), end.date())
                #     & Termine.zeit.between(startzeit, endzeit)
                # )
                ).execute()
        appomts = [appointment_from_legacy(a) for a in termine if (
            (datetime.datetime.combine(
                a.datum, time_from_legacy_zeit(a.zeit)) < end)
            and (datetime.datetime.combine(
                a.datum, time_from_legacy_zeit(a.zeit)) > start))]
        return Response(self.get_serializer(appomts, many=True).data)

    def get_queryset(self):
        end = datetime.datetime.now()
        start = end - ACTIVATE_PERIOD
        return Appointment.objects.filter(time__range=(start, end))
