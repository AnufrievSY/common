import telebot

def send_error_traceback(bot: telebot.TeleBot, chat_id: int, message_thread_id: int, message_text: str, traceback, **kwargs):
    message = (
        f"{message_text}\n"
        f"<blockquote><b>traceback</b>:\n{traceback}</blockquote>"
    )

    bot.send_message(
        chat_id=chat_id,
        message_thread_id=message_thread_id,
        text=message,
        parse_mode="HTML",
    )

