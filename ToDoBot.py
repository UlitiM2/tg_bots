import telebot
import sqlite3
import threading
from datetime import datetime
from telebot import types


DB_FILE = "todos.db"
db_lock = threading.Lock()


def init_db():
    with db_lock:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                user_id INTEGER,
                date TEXT,
                task TEXT,
                PRIMARY KEY (user_id, date, task)
            )
        """)
        conn.commit()
        conn.close()


init_db()
TOKEN = "7964240820:AAE_QtSklQubGxt1mQbp3wPSS_BPI3MmVpE"
bot = telebot.TeleBot(TOKEN)

HELP = '''
Список доступных команд:
* Показать задачи - показать все задачи на дату (формат: ДД.ММ.ГГГГ или ДД-ММ-ГГГГ)
* Добавить задачу - добавить задачу на определенную дату
* Помощь - показать это сообщение
'''


def create_main_keyboard():
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(types.KeyboardButton("Показать задачи"))
    keyboard.add(types.KeyboardButton("Добавить задачу"))
    keyboard.add(types.KeyboardButton("Помощь"))
    return keyboard


def is_valid_date(date_str):
    for separator in ['.', '-']:
        try:
            day, month, year = map(int, date_str.split(separator))
            datetime(year=year, month=month, day=day)
            return True
        except (ValueError, IndexError):
            continue
    return False


def add_todo(user_id, date, task):
    with db_lock:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO tasks VALUES (?, ?, ?)", (user_id, date.lower(), task))
            conn.commit()
        except sqlite3.IntegrityError:
            pass
        finally:
            conn.close()


def get_tasks(user_id, date):
    with db_lock:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT task FROM tasks WHERE user_id = ? AND date = ?", (user_id, date.lower()))
        tasks = [row[0] for row in cursor.fetchall()]
        conn.close()
        return tasks


@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.send_message(message.chat.id, HELP, reply_markup=create_main_keyboard())


@bot.message_handler(func=lambda message: message.text == "Помощь")
def help(message):
    bot.reply_to(message, HELP, reply_markup=create_main_keyboard())


@bot.message_handler(func=lambda message: message.text == "Добавить задачу")
def ask_for_date(message):
    msg = bot.reply_to(message, "Введите дату в формате ДД.ММ.ГГГГ или ДД-ММ-ГГГГ:")
    bot.register_next_step_handler(msg, process_date_step)


def process_date_step(message):
    try:
        date = message.text
        if not is_valid_date(date):
            bot.reply_to(message, "Ошибка: неверный формат даты. Используйте ДД.ММ.ГГГГ или ДД-ММ-ГГГГ", reply_markup=create_main_keyboard())
            return

        msg = bot.reply_to(message, "Введите задачу:")
        bot.register_next_step_handler(msg, process_task_step, date)
    except Exception as e:
        bot.reply_to(message, f"Ошибка: {e}", reply_markup=create_main_keyboard())


def process_task_step(message, date):
    try:
        task = message.text
        add_todo(message.from_user.id, date, task)
        bot.reply_to(message, f'Задача "{task}" добавлена на дату {date}', reply_markup=create_main_keyboard())
    except Exception as e:
        bot.reply_to(message, f"Ошибка: {e}", reply_markup=create_main_keyboard())


@bot.message_handler(func=lambda message: message.text == "Показать задачи")
def ask_for_date_to_print(message):
    msg = bot.reply_to(message, "Введите дату для просмотра задач в формате ДД.ММ.ГГГГ или ДД-ММ-ГГГГ:")
    bot.register_next_step_handler(msg, print_tasks)


def print_tasks(message):
    try:
        date = message.text
        if not is_valid_date(date):
            bot.reply_to(message, "Ошибка: неверный формат даты. Используйте ДД.ММ.ГГГГ или ДД-ММ-ГГГГ", reply_markup=create_main_keyboard())
            return

        tasks = get_tasks(message.from_user.id, date)
        if tasks:
            tasks_text = "\n".join([f"• {task}" for task in tasks])
            reply = f"Задачи на {date}:\n{tasks_text}"
        else:
            reply = f"На {date} нет задач"
        bot.reply_to(message, reply, reply_markup=create_main_keyboard())
    except Exception as e:
        bot.reply_to(message, f"Ошибка: {e}", reply_markup=create_main_keyboard())


@bot.message_handler(func=lambda message: True)
def handle_unknown(message):
    if message.text.startswith('/'):
        bot.reply_to(message, "Неизвестная команда. Введите /help для списка команд", reply_markup=create_main_keyboard())
    else:
        bot.reply_to(message, "Я понимаю только команды. Нажмите кнопку 'Помощь' для справки", reply_markup=create_main_keyboard())


bot.polling(none_stop=True)
