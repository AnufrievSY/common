
class TooMuchRetries(BaseException):
    """Срабатывает, если превышено количество попыток"""
    ...

class InvalidUsageError(BaseException):
    """Срабатывает, если пользователь неверно применяет предложенное решение"""
    ...