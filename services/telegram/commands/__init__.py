import telebot
from . import start

def register_private_commands(bot: telebot.TeleBot) -> telebot.TeleBot:
    """Регистрация команд бота для персональных чатов"""
    commands = []

    # Получение баланса пользователя
    bot.register_message_handler(**start.Handler(bot=bot).__dict__())
    commands.append(telebot.types.BotCommand("start", "Старт"))

    bot.set_my_commands(commands=commands, scope=telebot.types.BotCommandScopeAllPrivateChats())

    return bot

__all__ = [register_private_commands]
