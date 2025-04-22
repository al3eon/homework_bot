import logging
import os
import sys
import time
from logging import StreamHandler

import requests
from dotenv import load_dotenv
from telebot import TeleBot, apihelper

from exceptions import APIResponseError

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


def check_tokens():
    """Проверяет доступность обязательных переменных окружения."""
    token_list = ('PRACTICUM_TOKEN', 'TELEGRAM_TOKEN', 'TELEGRAM_CHAT_ID')
    missing_tokens = [token for token in token_list
                      if not globals()[token]]
    if missing_tokens:
        tokens_str = ', '.join(missing_tokens)
        message = ('Отсутствуют обязательные переменные окружения: '
                   f'{tokens_str}')
        logging.critical(message)
        raise ValueError(message)


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    logging.debug('Начало отправки сообщения в чат')
    bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
    logging.info('Сообщение успешно отправлено')


def get_api_answer(timestamp):
    """Получение ответа от API."""
    logging.debug(f'Отправляем запрос к {ENDPOINT} '
                  f'с параметрами: from_date={timestamp}')
    try:
        response = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params={'from_date': timestamp}
        )
    except requests.RequestException as error:
        raise ConnectionError(f"Ошибка при попытке подключения к API: {error}")

    if response.status_code != requests.codes.ok:
        raise APIResponseError(f"API вернул код {response.status_code}")

    logging.debug("Успешно получен ответ от API.")
    return response.json()


def check_response(response):
    """Проверка ответа."""
    logging.debug('Начало проверки ответа API')

    if not isinstance(response, dict):
        raise TypeError(f'Ожидался тип dict, '
                        f'получен: {type(response).__name__}')

    if 'homeworks' not in response:
        raise KeyError('Отсутствует ключ "homeworks"')

    if not isinstance(response['homeworks'], list):
        raise TypeError(f'Ожидался тип list, '
                        f'получен: {type(response["homeworks"]).__name__}')

    logging.debug('Проверка ответа API успешно завершена')
    return response['homeworks']


def parse_status(homework):
    """Проверка статуса."""
    logging.debug('Начало проверки статуса домашней работы"')
    missing_keys = [
        key for key in ['homework_name', 'status']
        if key not in homework
    ]
    if missing_keys:
        raise KeyError('Отсутствуют обязательные ключи:'
                       f' {", ".join(missing_keys)}')

    status = homework['status']
    if status not in HOMEWORK_VERDICTS.keys():
        raise ValueError(f'Неизвестный статус: {status}')

    homework_name = homework["homework_name"]
    verdict = HOMEWORK_VERDICTS[status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    check_tokens()
    bot = TeleBot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    last_message = ''

    while True:
        try:
            response = get_api_answer(timestamp)
            homework = check_response(response)
            if not homework:
                logging.debug('Статус не менялся')
                continue

            new_message = parse_status(homework[0])
            if new_message != last_message:
                send_message(bot, new_message)
                last_message = new_message
                timestamp = response.get('current_date', timestamp)

        except (requests.exceptions.RequestException,
                apihelper.ApiException) as error:
            logging.exception(f'Ошибка при отправке сообщения: {error}')

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.exception(message)
            if last_message != error:
                try:
                    send_message(bot, message)
                    last_message = error
                except (requests.exceptions.RequestException,
                        apihelper.ApiException) as send_error:
                    logging.exception('Ошибка при отправке сообщения'
                                      f' об ошибке: {send_error}')
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
        format=('%(asctime)s, %(levelname)s, %(message)s, '
                '%(name)s, %(funcName)s, %(lineno)d'),
        handlers=[StreamHandler(sys.stdout)]
    )
    main()
