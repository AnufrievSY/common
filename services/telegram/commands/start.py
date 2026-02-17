import telebot

class Handler:
    commands: list[str] = ["start"]
    def __init__(self, bot: telebot.TeleBot):
        self.bot = bot

    @staticmethod
    def _get_answer(username: str, chat_id: int) -> str:
        answer_text = f'Доброе пожаловать {username}\nИдентификатор чата: {chat_id}'
        return answer_text
    def __dict__(self) -> dict:
        return {
            "callback": self.__call__,
            "commands": self.commands
        }
    def __call__(self, message: telebot.types.Message) -> None:
        """Обработка команды /start: возвращает актуальный баланс пользователя"""
        try:
            answer = self._get_answer(username=message.from_user.username, chat_id=message.chat.id)
        except Exception:
            raise
        self.bot.delete_message(chat_id=message.chat.id, message_id=message.message_id)
        self.bot.send_message(chat_id=message.chat.id, message_thread_id=message.message_thread_id, text=answer)
