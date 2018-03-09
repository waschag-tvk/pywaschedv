from wasch.models import WashingMachine, WashUser

DEFAULT_MACHINE_CREATE_KWARGS = {
    'isAvailable': False,
}


def get_or_create_machines(
        create_kwargs=DEFAULT_MACHINE_CREATE_KWARGS, amend=False,
        recreate=False):
    """Create default TvK washing machines 1, 2, 3

    :param create_kwargs dict: keyword arguments for creating
        WashingMachine (apart of number)
    :param amend bool: whether to ignore existing ones and just add ones
        not yet existing; defaults to False, meaning, only the existing
        ones will be returned
    :param recreate bool: whether to force recreating all TvK washing
        machines when they already exist; defaults to False, meaning,
        those will not be touched; amend must be False if recreate is
        True
    """
    mNumbers = 1, 2, 3
    created = []
    if not amend:
        existing = WashingMachine.objects.filter(number__in=mNumbers)
        if existing.exists():
            return list(existing), created
    allTvkMachines = []
    for number in mNumbers:
        machine = None
        try:
            maybeExisting = WashingMachine.objects.filter(number=number)
            if recreate:
                maybeExisting.delete()
            else:
                machine = maybeExisting.get()
        except WashingMachine.DoesNotExist:  # most likely case
            pass
        if machine is None:
            machine = WashingMachine.objects.create(
                number=number, **create_kwargs)
            created.append(machine)
        allTvkMachines.append(machine)
    return allTvkMachines, created


def setup():
    """Create WashUser god, groups enduser, waschag,
    add god to both groups, create machines 1, 2, 3 if not exist

    :return list(django.db.models.Model): created objects
    """
    created = []
    god, was_created = WashUser.objects.get_or_create_god()
    if was_created:
        created.append(god)
    if not WashingMachine.objects.exists():
        _, created_machines = get_or_create_machines()
        created.extend(created_machines)
    return created
