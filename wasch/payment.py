class PaymentError(RuntimeError):
    pass


class BonusPayment:
    @staticmethod
    def coverage(value, user):
        '''amount that can be paid by user up to the given value'''
        return value

    @staticmethod
    def pay(value, fromUser, toUser, notes=''):
        return value, '0000000000'  # reference

    @staticmethod
    def refund(reference, value=None):
        '''
        :param reference str: reference of original payment
        :param value int: value to be refunded (<= original value);
            defaults to None, meaning the whole original amount
        '''
        return value, '0000000001'  # reference


class EmptyPayment:
    @staticmethod
    def coverage(value, user):
        '''amount that can be paid by user up to the given value'''
        return 0

    @staticmethod
    def pay(value, fromUser, toUser, notes=''):
        raise PaymentError('Account is empty!')

    @staticmethod
    def refund(reference, value=None):
        '''
        :param reference str: reference of original payment
        :param value int: value to be refunded (<= original value);
            defaults to None, meaning the whole original amount
        '''
        raise PaymentError('Account is empty!')


METHODS = {
    'bonus': BonusPayment(),
    'empty': EmptyPayment(),
}

BONUS_METHOD = METHODS['bonus']


def coverage(value, user, method, bonusAllowed=True):
    remaining = value
    methodP = METHODS[method]
    if bonusAllowed:
        remaining -= BONUS_METHOD.coverage(value, user.username)
    if remaining > 0:
        remaining -= methodP.coverage(value, user.username)
    return value - remaining


def pay(value, fromUser, toUser, method, bonusAllowed=True, notes=''):
    remaining = value
    reference = ''
    bonusReference = ''
    methodP = METHODS[method]
    if bonusAllowed:
        bonusCoverage = BONUS_METHOD.coverage(value, fromUser.username)
        if bonusCoverage > 0:
            bonusCoverage, bonusReference = BONUS_METHOD.pay(
                bonusCoverage, fromUser.username, toUser.username, notes)
            remaining -= bonusCoverage
    else:
        bonusCoverage = 0
    if remaining > 0:
        methodCoverage, reference = methodP.pay(
            remaining, fromUser.username, toUser.username, notes)
        remaining -= methodCoverage
    else:
        methodCoverage = bonusCoverage if methodP == BONUS_METHOD else 0
    if remaining == 0:
        return methodCoverage, reference  # XXX discarding bonusReference
    if bonusCoverage > 0:
        BONUS_METHOD.refund(bonusReference)
    if methodCoverage > 0:
        methodP.refund(methodCoverage)
    raise PaymentError("Full payment wasn't achieved")


def refund(method, reference, value=None):
    return METHODS[method].refund(reference, value)
