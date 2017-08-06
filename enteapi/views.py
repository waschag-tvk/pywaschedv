import json
import datetime
import traceback
from django.shortcuts import render
from django.http import HttpResponse
# from django.views.decorators.csrf import csrf_exempt
from rest_framework import viewsets
from rest_framework.decorators import detail_route, list_route
from rest_framework.parsers import JSONParser
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response
from wasch.models import Appointment, ref_checksum
from wasch.serializers import AppointmentSerializer
from legacymodels import Termine, DoesNotExist, Waschmaschinen


def machine_ready(machineId):
    '''can throw DoesNotExist if machineId wrong
    '''
    state = Waschmaschinen.get(Waschmaschinen.id == machineId).status
    return state == 1


LEGACY_EPOCH = datetime.date(1980, 1, 1)


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
    reference = (
            ((Termine.datum - LEGACY_EPOCH).days)*32+Termine.zeit
            )*4+Termine.maschine
    reference = (reference << 3) + ref_checksum(reference)
    return Appointment(
            time=time, user=None, machine=None, reference=reference)


def _legacy_use(reference):
    '''
    :param int bookingId:
    '''
    tmp = reference
    checksum = tmp % 8
    tmp >>= 3
    machine = tmp % 4
    tmp >>= 2
    time = tmp % 32
    tmp >>= 5
    if 256*64 <= tmp:
        return 'LEGACY_DATE_OUT_OF_RANGE'
    try:
        date = LEGACY_EPOCH + datetime.timedelta(days=tmp)
    except ValueError:
        print('machine: {}, time: {}, ord: {}'.format(machine, time, tmp))
        traceback.print_exc()
        return 'INVALID_LEGACY_ID'
    try:
        item = Termine.get(
                Termine.maschine == machine,
                Termine.zeit == time,
                Termine.datum == date,
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
            Termine.maschine == machine,
            Termine.zeit == time,
            Termine.datum == date,
            Termine.wochentag < 8,
            )  # marks as used
    n = query.execute()
    if n != 1:
        print('query: {}'.format(n))
        return 'UNEXPECTED'
    return 'OK'


def _use(reference, enteId):
    enten = [
            1,
            ]
    try:
        r = int(reference, base=16)
        e = int(enteId, base=16)
        if e not in enten:
            return 'UNKNOWN_ENTE'
    except ValueError:
        return 'INVALID_ID'
    # for legacy appointment reference
    return _legacy_use(r)
    return 'OK'


ACTIVATE_PERIOD = datetime.timedelta(seconds=15*60)
# ACTIVATE_PERIOD = datetime.timedelta(days=27)  # XXX easy testing!


class AppointmentViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = AppointmentSerializer
    parser_classes = (JSONParser,)
    renderer_classes = (JSONRenderer, )

    @detail_route(methods=['POST'])
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
        reqdata = request.data  # JSON
        enteId = reqdata['enteId']
        reference = pk
        error = _use(reference, enteId)
        print('activated appointment {} from ente {}@{} --> {}'.format(
            bookingId, enteId, request.META['REMOTE_ADDR'], error))
        return Response({
            'reference': reference,
            'ente-id': enteId,
            'action': action,
            'error': error,
            }, status=200 if error=='OK' else 400)

    @list_route()
    def legacy_list(self, request):
        end = datetime.datetime.now()
        start = end - ACTIVATE_PERIOD
        # endzeit = (end.hour * 2 + start.minute // 30) // 3
        # startzeit = (start.hour * 2 + start.minute // 30) // 3
        # aday = datetime.timedelta(days=1)
        termine = Termine.select().where(
                Termine.datum.between(start.date(), end.date())).execute()
                # | (
                    # Termine.datum.between(start.date(), end.date() - aday)
                    # & Termine.zeit > startzeit
                # ) | (
                    # Termine.datum.between(start.date() + aday, end.date())
                    # & Termine.zeit < endzeit
                # ) | (
                    # Termine.datum.between(start.date(), end.date())
                    # & Termine.zeit.between(startzeit, endzeit)
                # )).execute()
        appomts = [appointment_from_legacy(a) for a in termine if (
            (datetime.datetime.combine(
                a.datum, time_from_legacy_zeit(a.zeit)) < end)
            and (datetime.datetime.combine(a
                .datum, time_from_legacy_zeit(a.zeit)) > start))]
        return Response(self.get_serializer(appomts, many=True).data)

    def get_queryset(self):
        end = datetime.datetime.now()
        start = end - ACTIVATE_PERIOD
        return Appointment.objects.filter(time__range=(start, end))
