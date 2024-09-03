import logging
import os
import sys
import time
from logging import StreamHandler

import requests
import telebot
from dotenv import load_dotenv

from errors import StatusCodeIsNot200

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


def check_tokens():
    """Проверяет доступность переменных окружения."""
    tokens = {
        'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
        'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
        'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID
    }
    blank_token_flag = True
    for token, value in tokens.items():
        if not value:
            logging.debug(f"Токен {token} не найден.")
            blank_token_flag = False
    return blank_token_flag


def send_message(bot, message):
    """Отправляет сообщение в Telegram-чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.debug('Выполнена отправка сообщения')
        return True
    except Exception as error:
        logging.error(f'Ошибка при отправке сообщения {error}')
        return False


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
        raise f'Ошибка при запросе к основному API: {error}'
    if status_code != 200:
        raise StatusCodeIsNot200(
            f'Некоректный статус '
            f'ответа API:{status_code}'
        )
    return response.json()


def check_response(response):
    """Проверяет ответ API на соответствие документации из урока."""
    if not isinstance(response, dict):
        raise TypeError('Ошибка: в овете приходит неожиданный тип данных')
    if 'homeworks' not in response:
        raise KeyError('Отсутствует ключь: "homeworks"')
    if not isinstance(response['homeworks'], list):
        raise TypeError(
            'Ошибка: в ответе приходит '
            'иной тип данных для ключа "homeworks"'
        )


def parse_status(homework):
    """Достает статус проверки работы и ее названия из словаря."""
    keys_list = ['homework_name', 'status']
    missing_keys = [key for key in keys_list if key not in homework]
    if missing_keys:
        raise KeyError(f'Отсутствуют ключи: {", ".join(missing_keys)}')
    homework_name = homework['homework_name']
    homework_status = homework['status']
    if homework_status not in HOMEWORK_VERDICTS:

        raise KeyError(
            'Неожиданный статус домашней работы, '
            'обнаруженный в ответе API'
        )
    verdict = HOMEWORK_VERDICTS[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    logger = logging.getLogger(__name__)
    handler = StreamHandler(stream=sys.stdout)
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
            resp = get_api_answer(timestamp)
            check_response(resp)
            for homework in resp.get('homeworks'):
                status_message = parse_status(homework)
                send_message(bot, status_message)
            timestamp = resp.get('current_date', timestamp)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.error(message)
            if message != error_message:
                send_message(bot, message)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
