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
            print(f"Токен {token} не найден.")
            blank_token_flag = False
    return blank_token_flag


def send_message(bot, message):
    """Отправляет сообщение в Telegram-чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.debug('Выполнена отправка сообщения')
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
        error_message = ('Ошибка: в овете приходит неожиданный тип данных')
        logging.error(error_message)
        raise TypeError(error_message)
    keys = {
        'homeworks': list
    }
    missing_keys = [key for key in keys.keys() if key not in response]
    for key, key_type in keys.items():
        if missing_keys:
            raise KeyError(f'Отсутствуют ключи: {", ".join(missing_keys)}')
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
    missing_keys = [key for key in keys_list if key not in homework]
    if missing_keys:
        raise KeyError(f'Отсутствуют ключи: {", ".join(missing_keys)}')
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
            check_response(get_api_answer(timestamp))
            for homework in get_api_answer(timestamp).get('homeworks'):
                status_message = parse_status(homework)
                if send_message(bot, status_message):
                    error_message = ''
            current_date = get_api_answer(timestamp).get('current_date')
            timestamp = current_date if current_date else timestamp
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.error(message)
            if message != error_message:
                send_message(bot, message)
            error_message = message
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
