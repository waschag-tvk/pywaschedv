from wasch.models import WashingMachine
from wasch.auth import GodOnlyBackend


def setup():
    """Create WashUser god, groups enduser, waschag,
    add god to both groups, create machines 1, 2, 3 if not exist

    :return list(django.db.models.Model): created objects
    """
    created = []
    for group, was_created in GodOnlyBackend.get_or_create_wash_groups():
        if was_created:
            created.append(group)
    god, was_created = GodOnlyBackend.get_or_create_god(create_washgod=True)
    if was_created:
        created.append(god)
    if not WashingMachine.objects.exists():
        for number in 1, 2, 3:
            machine = WashingMachine(number=number, isAvailable=False)
            machine.save()
            created.append(machine)
    return created
