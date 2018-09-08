from django_q.tasks import schedule
from django_q.models import Schedule

# run `manage.py clearsession` every hour
schedule(
        'django.core.management.call_command',
        'autorefund',
        schedule_type=Schedule.MINUTES,
        minutes=15,
        )
