import logging
import os
import sys
import time

from http import HTTPStatus
from json import JSONDecodeError

import requests
import telegram
from dotenv import load_dotenv

import exceptions

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

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - %(name)s - '
               '%(funcName)s - %(lineno)d - %(message)s',
        handlers=[
            logging.FileHandler('program.log', mode='w'),
            logging.StreamHandler(sys.stdout)
        ]
    )

logger = logging.getLogger(__name__)


def check_tokens():
    """Проверка наличия токенов."""
    no_token_msg = 'Программа принудительно остановлена.'
    'Отсутствует переменная окружения: {}'
    tokens = {
        "PRACTICUM_TOKEN": PRACTICUM_TOKEN,
        "TELEGRAM_TOKEN": TELEGRAM_TOKEN,
        "TELEGRAM_CHAT_ID": TELEGRAM_CHAT_ID
    }
    for token, value in tokens.items():
        if value is None:
            logger.critical(no_token_msg.format(token))
            return False
    return True


def send_message(bot, message):
    """Отправка сообщения в Телеграм."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug(f'Бот отправил сообщение: "{message}"')
    except telegram.error.TelegramError as error:
        logger.error(f'Боту не удалось отправить сообщение: "{error}"')


def get_api_answer(timestamp):
    """Получение данных с API Яндекс Практикума."""
    timestamp = timestamp or int(time.time())
    params = {'from_date': timestamp}
    logger.info(f'Запрос к API {ENDPOINT} с параметрами {params}')
    try:
        homework_statuses = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params=params
        )
        logger.info('Запрос выполнен успешно')
    except requests.RequestException as error:
        message = ('Не удалось получить данные с {ENDPOINT} '
                   f'с параметрами {params}: {error}')
        raise ConnectionError(message)
    if homework_statuses.status_code != HTTPStatus.OK:
        message = f'Код ответа API: {homework_statuses.status_code}'
        raise exceptions.GetAPIAnswerException(message)
    try:
        return homework_statuses.json()
    except JSONDecodeError as error:
        message = f'Ошибка преобразования к формату json: {error}'
        raise exceptions.GetAPIAnswerException(message)
    except Exception as error:
        message = f'Не удалось прочитать ответ: {error}'
        raise exceptions.GetAPIAnswerException(message)


def check_response(response):
    """Проверяем данные в response."""
    logger.info('Начинаем проверку ответа API')
    if not isinstance(response, dict):
        message = ('Тип данных в ответе от API не соответствует ожидаемому. '
                   f'Получен: {type(response)}')
        raise TypeError(message)
    if 'current_date' not in response:
        raise KeyError('Ключ current_date недоступен в ответе API.')
    if 'homeworks' not in response:
        raise KeyError('Ключ homeworks недоступен в ответе API.')
    homeworks_list = response['homeworks']
    if not isinstance(homeworks_list, list):
        message = ('Список домашних заданий в ответе API приходит некорректно.'
                   f' Получен: {type(homeworks_list)}')
        raise TypeError(message)
    logger.info('Проверка ответа API успешно завершена')
    return homeworks_list


def parse_status(homework):
    """Анализируем статус если изменился."""
    logger.info(f'Начинаем анализ статуса работы '
                f'"{homework.get("homework_name")}".')
    homework_name = homework.get('homework_name')
    if not homework_name:
        message = 'Ключ homework_name недоступен в ответе API.'
        logger.error(message)
        raise KeyError(message)
    homework_status = homework.get('status')
    if not homework_status:
        message = 'Ключ status недоступен в ответе API.'
        raise KeyError(message)
    if homework_status not in HOMEWORK_VERDICTS:
        message = ('Передан неизвестный статус домашней работы '
                   f'"{homework_status}".')
        raise exceptions.ParseStatusException(message)
    verdict = HOMEWORK_VERDICTS[homework_status]
    logger.info(f'Статус работы "{homework_name}" изменился на {verdict}.')
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        raise ValueError('Проверьте переменные окружения')

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    last_message = ''
    while True:
        try:
            response = get_api_answer(current_timestamp)
            current_timestamp = response['current_date']
            homework = check_response(response)
            if homework:
                homework_status = parse_status(homework[0])
                if last_message != homework_status:
                    last_message = homework_status
                    send_message(bot, homework_status)
                    logger.info(homework_status)
            else:
                logger.info('Статус не обновлен')
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message, exc_info=True)
            if last_message != message:
                last_message = message
                send_message(bot, message)
        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
