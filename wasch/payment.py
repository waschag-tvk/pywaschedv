class PaymentError(RuntimeError):
    pass


class InfinitePayment:
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
    'infinite': InfinitePayment(),
    'empty': EmptyPayment(),
}


def coverage(value, user, method, bonusMethod=None):
    remaining = value
    methodP = METHODS[method]
    bonusMethodP = METHODS['empty' if bonusMethod is None else bonusMethod]
    if bonusMethod is not None:
        remaining -= bonusMethodP.coverage(value, user)
    if remaining > 0:
        remaining -= methodP.coverage(value, user)
    return value - remaining


def pay(value, fromUser, toUser, method, bonusMethod=None, notes=''):
    remaining = value
    reference = ''
    bonusReference = ''
    methodP = METHODS[method]
    bonusMethodP = METHODS['empty' if bonusMethod is None else bonusMethod]
    if bonusMethod is not None:
        bonusCoverage = bonusMethodP.coverage(value, fromUser)
        if bonusCoverage > 0:
            bonusCoverage, bonusReference = bonusMethodP.pay(
                bonusCoverage, fromUser, toUser, notes)
            remaining -= bonusCoverage
    else:
        bonusCoverage = 0
    if remaining > 0:
        methodCoverage, reference = methodP.pay(
            remaining, fromUser, toUser, notes)
        remaining -= methodCoverage
    else:
        methodCoverage = bonusCoverage if methodP == bonusMethodP else 0
    if remaining == 0:
        return methodCoverage, reference  # XXX discarding bonusReference
    if bonusCoverage > 0:
        bonusMethodP.refund(bonusReference)
    if methodCoverage > 0:
        methodP.refund(methodCoverage)
    raise PaymentError("Full payment wasn't achieved")


def refund(method, reference, value=None):
    return METHODS[method].refund(reference, value)
