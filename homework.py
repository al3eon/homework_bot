import logging
import os
import time
import requests
import sys

from dotenv import load_dotenv
from telebot import TeleBot
from logging import StreamHandler

load_dotenv()

logger = logging.getLogger(__name__)

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s, %(levelname)s, %(message)s, %(name)s',
    handlers=[StreamHandler(sys.stdout)]
)

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
    for token in (PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID):
        if token is None:
            logger.critical(f'Отсутствует {token}')
            raise ValueError(f'Отсутствует {token}')


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logger.debug('Сообщение успешно отправлено')
    except Exception as error:
        logger.error('Ошибка при отправке сообщения: "%s": %s', message, error)


def get_api_answer(timestamp):
    """Получение ответа от API."""
    try:
        response = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params={'from_date': timestamp}
        )
        if response.status_code != requests.codes.ok:
            raise requests.HTTPError(f"API вернул {response.status_code}")
        return response.json()

    except requests.HTTPError as error:
        logging.error(f"Ошибка API: {error}")
        raise
    except requests.RequestException as error:
        logging.error(f"Сетевая ошибка: {error}")
        return None


def check_response(response):
    """Проверка ответа."""
    if not isinstance(response, dict):
        raise TypeError('Ответ не словарь')

    if 'current_date' not in response:
        raise KeyError('Отсутствует ключ')

    if 'homeworks' not in response:
        raise KeyError('Отсутствует ключ')

    if not isinstance(response['current_date'], int):
        raise TypeError('current_date не число')

    if not isinstance(response['homeworks'], list):
        raise TypeError('homeworks не список')

    return response['homeworks']


def parse_status(homework):
    """Проверка статуса."""
    if 'homework_name' not in homework:
        raise KeyError('Нет ключа "homework_name"')
    if 'status' not in homework:
        raise KeyError('Нет ключа "status"')
    if homework['status'] not in HOMEWORK_VERDICTS.keys():
        raise KeyError(f'Неизвестный статус:{homework["status"]}')
    homework_name = homework["homework_name"]
    verdict = HOMEWORK_VERDICTS[homework['status']]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    check_tokens()
    bot = TeleBot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())

    while True:
        try:
            response = get_api_answer(timestamp)
            homework = check_response(response)
            if not homework:
                logger.debug('Статус не менялся')
                continue
            if send_message(bot, parse_status(homework[0])):
                timestamp = response.get('current_date', timestamp)

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
