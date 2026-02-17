from .executor import *
import logging
import telebot
import requests
import time
from . import commands

def run(bot: telebot.TeleBot, log: logging.Logger = logging.getLogger("TgBot")) -> None:
    """Запускает телеграм-бота"""
    bot = commands.register_private_commands(bot=bot)

    while True:
        try:
            log.info("Бот запущен. Ожидаем сообщения...")
            bot.polling(none_stop=True, interval=1)
        except requests.exceptions.ReadTimeout:
            log.warning(f'ReadTimeout: restart...')
            bot.stop_polling()
            time.sleep(5)
        except requests.exceptions.ConnectionError:
            log.warning(f'ConnectionError: restart...')
            bot.stop_polling()
            time.sleep(10)
        except KeyboardInterrupt:
            log.info("Остановка бота по Ctrl+C.")
            bot.stop_polling()
            break
        else:
            log.error(f"Ошибка в работе бота", exc_info=True)
            bot.stop_polling()
            time.sleep(5)
