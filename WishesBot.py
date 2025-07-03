import telebot
import sqlite3
import threading
from telebot import types


DB_FILE = "wishes.db"
db_lock = threading.Lock()


def init_db():
    with db_lock:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS wishes (
                user_id INTEGER,
                wish TEXT,
                PRIMARY KEY (user_id, wish)
            )
        """)
        conn.commit()
        conn.close()


def create_main_keyboard():
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(types.KeyboardButton("Добавить желание"))
    keyboard.add(types.KeyboardButton("Посмотреть желания"))
    keyboard.add(types.KeyboardButton("Удалить желание"))
    keyboard.add(types.KeyboardButton("Узнать ID"))
    keyboard.add(types.KeyboardButton("Посмотреть желания друга"))
    keyboard.add(types.KeyboardButton("Помощь"))
    return keyboard


def get_wishes(user_id):
    with db_lock:
        conn =sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT wish FROM wishes WHERE user_id = ?", (user_id,))
        all_wishes = [row[0] for row in cursor.fetchall()]
        conn.close()
        return all_wishes


def add_wish_to_db(user_id, wish):
    with db_lock:
        conn =sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO wishes VALUES (?, ?)",(user_id, wish))
            conn.commit()
        except sqlite3.IntegrityError:
            pass
        finally:
            conn.close()


init_db()
TOKEN = ""
bot = telebot.TeleBot(TOKEN)
HELP = '''
Список доступных команд:
* Добавить желание - создать новое желание
* Посмотреть желания - посмотреть список всех желаний
* Удалить желание - удалить желание
* Узнать ID - узнать свой ID, чтобы поделиться им с другом
* Посмотреть желания друга - узнайте, какие подарки хочет получить ваш друг, зная его ID
* Помощь - показать это сообщение
'''


@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.send_message(message.chat.id, HELP, reply_markup=create_main_keyboard())


@bot.message_handler(func=lambda message: message.text == "Помощь")
def help(message):
    bot.reply_to(message, HELP, reply_markup=create_main_keyboard())


@bot.message_handler(func=lambda message:message.text == "Посмотреть желания")
def watch_wishes(message):
    try:
        wishes = get_wishes(message.from_user.id)
        if wishes:
            text_of_wishes = "\n".join([f"* {wish}" for wish in wishes])
            reply = f"Желания пользователя: \n {text_of_wishes}"
        else:
            reply = "Желаний пока нет"
        bot.reply_to(message, reply, reply_markup=create_main_keyboard())
    except Exception as e:
        bot.reply_to(message, f"Ошибка: {e}", reply_markup=create_main_keyboard())


@bot.message_handler(func=lambda message:message.text == "Удалить желание")
def delete_wish(message):
    try:
        wishes = get_wishes(message.from_user.id)
        if not wishes:
            bot.reply_to(message, "У вас нет сохранённых желаний для удаления", reply_markup=create_main_keyboard())
            return

        wish_list = "\n".join([f"{i+1}. {wish}" for i, wish in enumerate(wishes)])
        msg = bot.reply_to(message, f"Ваши желания:\n{wish_list}\n\nВведите номер желания для удаления:", reply_markup=create_main_keyboard())
        bot.register_next_step_handler(msg, process_delete_wish, wishes)
    except Exception as e:
        bot.reply_to(message, f"Ошибка: {e}", reply_markup=create_main_keyboard())


def process_delete_wish(message, wishes):
    try:
        choice = int(message.text)
        if 1 <= choice <= len(wishes):
            wish_to_delete = wishes[choice-1]

            with db_lock:
                conn = sqlite3.connect(DB_FILE)
                cursor = conn.cursor()
                cursor.execute("DELETE FROM wishes WHERE user_id = ? AND wish = ?", (message.from_user.id, wish_to_delete))
                conn.commit()
                conn.close()
            bot.reply_to(message, f"Желание '{wish_to_delete}' успешно удалено!", reply_markup=create_main_keyboard())
        else:
            bot.reply_to(message, "Некорректный номер. Попробуйте снова.", reply_markup=create_main_keyboard())
    except ValueError:
        bot.reply_to(message, "Пожалуйста, введите номер желания.", reply_markup=create_main_keyboard())
    except Exception as e:
        bot.reply_to(message, f"Ошибка при удалении: {e}", reply_markup=create_main_keyboard())


@bot.message_handler(func=lambda message:message.text == "Посмотреть желания друга")
def watch_wishes_of_friends(message):
    try:
        msg = bot.reply_to(message, 'Введите ID друга:')
        bot.register_next_step_handler(msg, process_friend_id_step)
    except Exception as e:
        bot.reply_to(message, f"Ошибка: {e}", reply_markup=create_main_keyboard())


def process_friend_id_step(message):
    try:
        friend_id = int(message.text)
        wishes = get_wishes(friend_id)
        if wishes:
            text_of_wishes = "\n".join([f"* {wish}" for wish in wishes])
            reply = f"Желания пользователя {friend_id}:\n{text_of_wishes}"
        else:
            reply = f"У пользователя {friend_id} нет желаний"
        bot.reply_to(message, reply, reply_markup=create_main_keyboard())
    except ValueError:
        bot.reply_to(message, "Некорректный ID. Введите число.", reply_markup=create_main_keyboard())
    except Exception as e:
        bot.reply_to(message, f"Ошибка: {e}", reply_markup=create_main_keyboard())


@bot.message_handler(func=lambda message:message.text == "Узнать ID")
def find_ID(message):
    try:
        bot.reply_to(message, f"Ваш ID: {message.from_user.id}", reply_markup=create_main_keyboard())
    except Exception as e:
        bot.reply_to(message, f"Ошибка: {e}", reply_markup=create_main_keyboard())


@bot.message_handler(func=lambda message:message.text == "Добавить желание")
def add_wish(message):
    msg = bot.reply_to(message, 'Привет! Какое у тебя желание?')
    bot.register_next_step_handler(msg, process_wish_step)


def process_wish_step(message):
    try:
        wish = message.text
        add_wish_to_db(message.from_user.id, wish)
        bot.reply_to(message, f'Желание "{wish}" успешно добавлено!', reply_markup=create_main_keyboard())
    except Exception as e:
        bot.reply_to(message, f"Ошибка: {e}", reply_markup=create_main_keyboard())


bot.polling(none_stop=True)
