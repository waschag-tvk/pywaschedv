from django.core.management.base import BaseCommand, CommandError
from wasch.models import Appointment
from wasch import payment


class Command(BaseCommand):
    help = 'Refunds all appointments that was not used and cannot be used'

    def handle(self, *args, **options):
        try:
            Appointment.manager.auto_refund_all()
        except payment.PaymentError as e:
            raise CommandError('Refund transaction failed: {}'.format(str(e)))
        self.stderr.write(self.style.SUCCESS('Successfully refunded all'))
