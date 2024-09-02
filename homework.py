import logging
import os
import sys
import time
from logging import StreamHandler

import requests
import telebot
from dotenv import load_dotenv

logger = logging.getLogger(__name__)
handler = StreamHandler(stream=sys.stdout)

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

required_tokens = {
    'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
    'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
    'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID
}


class StatusCodeisnot200(Exception):
    """When status code is not 200."""


def check_tokens():
    """Проверяет доступность переменных окружения."""
    return all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID])


def send_message(bot, message):
    """Отправляет сообщение в Telegram-чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.debug('Выполнена отправка сообщения')
    except Exception as error:
        logging.error(f'Ошибка при отправке сообщения {error}')


def get_api_answer(timestamp):
    """Делает запрос к единственному эндпоинту API-сервиса."""
    try:
        response = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params={'from_date': timestamp}
        )
        status_code = response.status_code
    except requests.exceptions.RequestException as error:
        logging.error(f'Ошибка при запросе к основному API: {error}')
        raise IndexError
    except Exception as error:
        logging.error(f'Ошибка при обработке ответа API: {error}')
        raise IndexError
    if status_code != 200:
        raise StatusCodeisnot200(f'Некоректный статус '
                                 f'ответа API:{status_code}')
    return response.json()


def check_response(response):
    """Проверяет ответ API на соответствие документации из урока."""
    if not isinstance(response, dict):
        error_message = ('Ошибка: в овете приходит неожиданный тип данных')
        logging.error(error_message)
        raise TypeError(error_message)
    keys_list = {'homeworks': list,
                 'current_date': int}
    for key, key_type in keys_list.items():
        if key not in response:
            error_message = (f'Отсутствует ключ {key}')
            logging.error(error_message)
            raise KeyError(error_message)
        if not isinstance(response[key], key_type):
            error_message = (
                'Ошибка: в ответе приходит '
                'иной тип данных для ключа "homeworks"'
            )
            logging.error(error_message)
            raise TypeError(error_message)
    return True


def parse_status(homework):
    """Достает статус проверки работы и ее названия из словаря."""
    keys_list = ['homework_name', 'status']
    for key in keys_list:
        if key not in homework:
            raise KeyError(f'Отсутствует ключ {key}')
    homework_name = homework['homework_name']
    homework_status = homework['status']
    if homework_status not in HOMEWORK_VERDICTS:
        error_message = ('Неожиданный статус домашней работы, '
                         'обнаруженный в ответе API')
        logging.error(error_message)
        raise KeyError(error_message)
    verdict = HOMEWORK_VERDICTS[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    formatter = '%(asctime)s - %(levelname)s - %(message)s'
    logger.setLevel(logging.DEBUG)
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    if not check_tokens():
        logging.critical('Переменные окружения отсутсвуют')
        exit()
    logging.debug('Переменные окружения присутсвуют')

    bot = telebot.TeleBot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    error_message = ''

    while True:
        try:
            response_api = get_api_answer(timestamp)
            check_response(response_api)
            homeworks = response_api['homeworks']
            for homework in homeworks:
                status_message = parse_status(homework)
                send_message(bot, status_message)
            current_date = response_api['current_date']
            timestamp = current_date if current_date else timestamp
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.error(message)
            if message != error_message:
                send_message(bot, message)
            error_message = message
        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
