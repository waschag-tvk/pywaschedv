from accounts import facade
from wasch.models import WashUser
from wasch.payment import PaymentError

service_washuser, _ = WashUser.objects.get_or_create_service_user()
god, _ = WashUser.objects.get_or_create_god()
BONUS_SOURCE_NAME = 'bonus-source-{}'.format(service_washuser.user.username)
BONUS_SINK_NAME = 'bonus-sink-{}'.format(service_washuser.user.username)


def _get_bonus_source():
    bonus_source, _ = facade.Account.objects.get_or_create(
            defaults={'credit_limit': None},
            primary_user=god.user, name=BONUS_SOURCE_NAME)
    return bonus_source


def _get_bonus_sink():
    bonus_sink, _ = facade.Account.objects.get_or_create(
            primary_user=service_washuser.user, name=BONUS_SINK_NAME)
    return bonus_sink


class BonusPayment:

    @classmethod
    def _class_init(cls):
        if not hasattr(cls, 'bonus_source'):
            cls.bonus_source = _get_bonus_source()
            cls.bonus_sink = _get_bonus_sink()

    def __getattr__(self, name):
        if name in ('bonus_source', 'bonus_sink'):
            self._class_init()
        return self.__getattribute__(name)

    @staticmethod
    def bonus_account_of(user):
        return facade.Account.objects.exclude(
                name__endswith=service_washuser.user.username
                ).get(primary_user=user)

    @classmethod
    def award_bonus(cls, value, user, authorized_by=None, notes=''):
        cls._class_init()
        try:
            destination = cls.bonus_account_of(user)
        except facade.Account.DoesNotExist:
            destination = facade.Account.objects.create(
                primary_user=user, name='bonus-{}'.format(user.username),
                credit_limit=None)
        transfer = facade.Transfer.objects.create(
                source=cls.bonus_source,
                destination=destination, amount=value,
                user=authorized_by, description=notes)
        return value, str(transfer.reference)

    @classmethod
    def coverage(cls, value, user):
        '''amount that can be paid by user up to the given value'''
        try:
            return min(value, cls.bonus_account_of(user).balance)
        except facade.Account.DoesNotExist:
            return 0

    @classmethod
    def pay(cls, value, fromUser, toUser, notes=''):
        cls._class_init()
        if toUser is not None and toUser != service_washuser.user:
            raise PaymentError(
                    'Bonus can only be transferred to service_washuser; '
                    'please set toUser=None!')
        transfer = facade.transfer(
                source=cls.bonus_account_of(fromUser),
                destination=cls.bonus_sink, amount=value,
                user=fromUser, description=notes)
        return value, str(transfer.reference)

    @classmethod
    def refund(cls, reference, value=None):
        '''
        :param reference str: reference of original payment
        :param value int: value to be refunded (<= original value);
            defaults to None, meaning the whole original amount
        '''
        transfer = facade.Transfer.objects.get(reference=reference)
        refundable_value = transfer.max_refund()
        description = 'refund {:s}'.format(reference)
        if value is None:
            value = transfer.amount
        if refundable_value < value:
            raise PaymentError(
                    'Only maximum {:d} is refundable! {:d} given.'.format(
                        refundable_value, value))
        # not facade.reverse(transfer, description=description)
        # because it doesn’t set Transfer.parent
        refund_transfer = facade.Transfer.objects.create(
                source=transfer.destination,
                destination=transfer.source,
                amount=value,
                parent=transfer,
                description=description)
        return value, str(refund_transfer.reference)
