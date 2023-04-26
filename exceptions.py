class SendMessageException(Exception):
    """Ошибка при отправке сообщения."""

    pass


class GetAPIAnswerException(Exception):
    """Ошибка при получении API."""

    pass


class CheckResponseException(Exception):
    """Ошибка в ответе."""

    pass


class ParseStatusException(Exception):
    """Ошибка  формата статуса."""

    pass
