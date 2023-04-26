import time
import logging
import os
from http import HTTPStatus

import requests
import telegram
import exceptions

from dotenv import load_dotenv

load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logging.basicConfig(
    level=logging.DEBUG,
    filename='program.log',
    filemode='w',
    format='%(asctime)s - %(levelname)s - %(message)s - %(name)s'
)
logger = logging.getLogger(__name__)
logger.addHandler(
    logging.StreamHandler()
)


def check_tokens():
    """Проверка наличия токенов."""
    no_tokens_msg = (
        'Программа принудительно остановлена. '
        'Отсутствует обязательная переменная окружения:')
    tokens_bool = True
    if PRACTICUM_TOKEN is None:
        tokens_bool = False
        logger.critical(
            f'{no_tokens_msg} PRACTICUM_TOKEN')
    if TELEGRAM_TOKEN is None:
        tokens_bool = False
        logger.critical(
            f'{no_tokens_msg} TELEGRAM_TOKEN')
    if TELEGRAM_CHAT_ID is None:
        tokens_bool = False
        logger.critical(
            f'{no_tokens_msg} TELEGRAM_CHAT_ID')
    return tokens_bool


def send_message(bot, message):
    """Отправка сообщения в Телеграм."""
    try:
        logger.debug(f'Бот отправил сообщение: "{message}"')
        return bot.send_message(TELEGRAM_CHAT_ID, message)
    except telegram.error.TelegramError as error:
        logger.error(f'Боту не удалось отправить сообщение: "{error}"')
        raise exceptions.SendMessageException(error)


def get_api_answer(timestamp):
    """Получение данных с API Яндекс Практикума."""
    current_timestamp = int(time.time())
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        homework_statuses = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params=params
        )
    except Exception as error:
        message = f'Эндпоинт {ENDPOINT} недоступен: {error}'
        logger.error(message)
        raise exceptions.GetAPIAnswerException(message)
    if homework_statuses.status_code != HTTPStatus.OK:
        message = f'Код ответа API: {homework_statuses.status_code}'
        logger.error(message)
        raise exceptions.GetAPIAnswerException(message)
    try:
        return homework_statuses.json()
    except Exception as error:
        message = f'Ошибка преобразования к формату json: {error}'
        logger.error(message)
        raise exceptions.GetAPIAnswerException(message)


def check_response(response):
    """Проверяем данные в response."""
    if type(response) != dict:
        message = \
            f'Тип данных в ответе от API не соотвествует ожидаемому.' \
            f' Получен: {type(response)}'
        logger.error(message)
        raise TypeError(message)
    if 'homeworks' not in response:
        message = 'Ключ homeworks недоступен'
        logger.error(message)
        raise exceptions.CheckResponseException(message)
    homeworks_list = response['homeworks']
    if type(homeworks_list) != list:
        message = \
            f'В ответе от API домашки приходят не в виде списка. ' \
            f'Получен: {type(homeworks_list)}'
        logger.error(message)
        raise TypeError(message)
    return homeworks_list


def parse_status(homework):
    """Анализируем статус если изменился."""
    if 'homework_name' not in homework:
        message = 'Ключ homework_name недоступен'
        logger.error(message)
        raise KeyError(message)
    if 'status' not in homework:
        message = 'Ключ status недоступен'
        logger.error(message)
        raise KeyError(message)
    homework_name = homework['homework_name']
    homework_status = homework['status']
    if homework_status in HOMEWORK_VERDICTS:
        verdict = HOMEWORK_VERDICTS[homework_status]
        return f'Изменился статус проверки работы ' \
               f'"{homework_name}". {verdict}'
    else:
        message = \
            f'Передан неизвестный статус домашней работы "{homework_status}"'
        logger.error(message)
        raise exceptions.ParseStatusException(message)


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        raise ValueError('Проверьте переменные окружения')

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    current_status = ''
    current_error = ''
    while True:
        try:
            response = get_api_answer(current_timestamp)
            homework = check_response(response)
            if not len(homework):
                logger.info('Статус не обновлен')
            else:
                homework_status = parse_status(homework[0])
                if current_status == homework_status:
                    logger.info(homework_status)
                else:
                    current_status = homework_status
                    send_message(bot, homework_status)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
            if current_error != str(error):
                current_error = str(error)
                send_message(bot, message)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
