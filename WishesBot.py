import telebot
import sqlite3
import threading
from telebot import types
from datetime import datetime, timedelta
import time

DB_FILE = "wishes.db"
db_lock = threading.Lock()

STATUSES = {
    'available': '🟢 Доступно',
    'booked': '🟡 Забронировано',
    'completed': '🔵 Выполнено'
}


def init_db():
    with db_lock:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS wishes (
                user_id INTEGER,
                wish TEXT,
                status TEXT DEFAULT 'available',
                PRIMARY KEY (user_id, wish)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS friends (
                user_id INTEGER,
                friend_id INTEGER,
                friend_name TEXT,
                birthday TEXT,
                PRIMARY KEY (user_id, friend_id)
            )
        """)

        conn.commit()
        conn.close()


def create_main_keyboard():
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(types.KeyboardButton("Желания друга"))
    keyboard.add(types.KeyboardButton("Управление желаниями"))
    keyboard.add(types.KeyboardButton("Добавить желание"))
    keyboard.add(types.KeyboardButton("Мои желания"))
    keyboard.add(types.KeyboardButton("Узнать ID"))
    keyboard.add(types.KeyboardButton("Мои друзья"))
    keyboard.add(types.KeyboardButton("Помощь"))
    return keyboard

def create_friends_keyboard():
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(types.KeyboardButton("Добавить друга"))
    keyboard.add(types.KeyboardButton("Список друзей"))
    keyboard.add(types.KeyboardButton("Удалить друга"))
    keyboard.add(types.KeyboardButton("Назад"))
    return keyboard

def create_management_keyboard():
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(types.KeyboardButton("Удалить желание"))
    keyboard.add(types.KeyboardButton("Изменить статус"))
    keyboard.add(types.KeyboardButton("Назад"))
    return keyboard


def get_wishes(user_id):
    with db_lock:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT wish, status FROM wishes WHERE user_id = ?", (user_id,))
        wishes = [{"text": row[0], "status": row[1]} for row in cursor.fetchall()]
        conn.close()
        return wishes


def add_wish_to_db(user_id, wish):
    with db_lock:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO wishes (user_id, wish, status) VALUES (?, ?, ?)",
                          (user_id, wish, 'available'))
            conn.commit()
        except sqlite3.IntegrityError:
            pass
        finally:
            conn.close()


def update_wish_status(user_id, wish, new_status):
    with db_lock:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("UPDATE wishes SET status = ? WHERE user_id = ? AND wish = ?",
                      (new_status, user_id, wish))
        conn.commit()
        conn.close()


def add_friend(user_id, friend_id, friend_name, birthday):
    with db_lock:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO friends (user_id, friend_id, friend_name, birthday)
                VALUES (?, ?, ?, ?)
            """, (user_id, friend_id, friend_name, birthday))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False
        finally:
            conn.close()

def get_friends(user_id):
    with db_lock:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT friend_id, friend_name, birthday
            FROM friends
            WHERE user_id = ?
        """, (user_id,))
        friends = [{
            'id': row[0],
            'name': row[1],
            'birthday': row[2]
        } for row in cursor.fetchall()]
        conn.close()
        return friends

def delete_friend(user_id, friend_id):
    with db_lock:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("""
            DELETE FROM friends
            WHERE user_id = ? AND friend_id = ?
        """, (user_id, friend_id))
        conn.commit()
        conn.close()


init_db()
TOKEN = "7968043780:AAFpXUEOab4NgKN27aow7Y09Y-Y07aTVwNY"
bot = telebot.TeleBot(TOKEN)
HELP = '''
Список доступных команд:
* Желания друга - посмотреть желания друга по ID
* Управление желаниями - удаление и изменение статусов
* Добавить желание - добавить новое желание
* Мои желания - посмотреть список всех желаний
* Узнать ID - узнать свой ID
* Мои друзья - управление списком друзей
* Помощь - показать это сообщение
'''


@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.send_message(message.chat.id, HELP, reply_markup=create_main_keyboard())


@bot.message_handler(func=lambda message: message.text == "Помощь")
def help(message):
    bot.reply_to(message, HELP, reply_markup=create_main_keyboard())


@bot.message_handler(func=lambda message: message.text == "Мои желания")
def watch_wishes(message):
    try:
        wishes = get_wishes(message.from_user.id)
        if wishes:
            text_of_wishes = "\n".join(
                [f"{i+1}. {wish['text']} - {STATUSES.get(wish['status'], wish['status'])}"
                 for i, wish in enumerate(wishes)]
            )
            reply = f"Ваши желания:\n{text_of_wishes}"
        else:
            reply = "У вас пока нет желаний"
        bot.reply_to(message, reply, reply_markup=create_main_keyboard())
    except Exception as e:
        bot.reply_to(message, f"Ошибка: {e}", reply_markup=create_main_keyboard())


@bot.message_handler(func=lambda message: message.text == "Управление желаниями")
def manage_wishes(message):
    bot.reply_to(message, "Выберите действие:", reply_markup=create_management_keyboard())

@bot.message_handler(func=lambda message: message.text == "Изменить статус")
def change_status(message):
    try:
        wishes = get_wishes(message.from_user.id)
        if not wishes:
            bot.reply_to(message, "У вас нет желаний для изменения", reply_markup=create_main_keyboard())
            return

        wish_list = "\n".join(
            [f"{i+1}. {wish['text']} - {STATUSES.get(wish['status'], wish['status'])}"
             for i, wish in enumerate(wishes)]
        )
        msg = bot.reply_to(message,
                         f"Ваши желания:\n{wish_list}\n\nВведите номер желания для изменения статуса:",
                         reply_markup=types.ReplyKeyboardRemove())
        bot.register_next_step_handler(msg, process_wish_selection_for_status, wishes)
    except Exception as e:
        bot.reply_to(message, f"Ошибка: {e}", reply_markup=create_main_keyboard())

def process_wish_selection_for_status(message, wishes):
    try:
        choice = int(message.text)
        if 1 <= choice <= len(wishes):
            wish = wishes[choice-1]
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
            for status in STATUSES.values():
                markup.add(types.KeyboardButton(status))
            markup.add(types.KeyboardButton("Отмена"))

            msg = bot.reply_to(message,
                             f"Выберите новый статус для желания '{wish['text']}':",
                             reply_markup=markup)
            bot.register_next_step_handler(msg, process_status_selection, wish)
        else:
            bot.reply_to(message, "Некорректный номер", reply_markup=create_main_keyboard())
    except ValueError:
        bot.reply_to(message, "Пожалуйста, введите номер", reply_markup=create_main_keyboard())
    except Exception as e:
        bot.reply_to(message, f"Ошибка: {e}", reply_markup=create_main_keyboard())

def process_status_selection(message, wish):
    try:
        if message.text == "Отмена":
            bot.reply_to(message, "Отменено", reply_markup=create_main_keyboard())
            return

        status_key = next((k for k, v in STATUSES.items() if v == message.text), None)
        if status_key:
            update_wish_status(message.from_user.id, wish['text'], status_key)
            bot.reply_to(message,
                        f"Статус желания '{wish['text']}' изменен на {message.text}",
                        reply_markup=create_main_keyboard())
        else:
            bot.reply_to(message, "Неизвестный статус", reply_markup=create_main_keyboard())
    except Exception as e:
        bot.reply_to(message, f"Ошибка: {e}", reply_markup=create_main_keyboard())

@bot.message_handler(func=lambda message: message.text == "Назад")
def back_to_main(message):
    bot.reply_to(message, "Главное меню", reply_markup=create_main_keyboard())

@bot.message_handler(func=lambda message: message.text == "Желания друга")
def watch_wishes_of_friends(message):
    try:
        friends = get_friends(message.from_user.id)
        if not friends:
            bot.reply_to(message, "У вас нет сохранённых друзей", reply_markup=create_main_keyboard())
            return

        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        for i, friend in enumerate(friends, 1):
            markup.add(types.KeyboardButton(f"{i}. {friend['name']}"))
        markup.add(types.KeyboardButton("Отмена"))

        msg = bot.reply_to(message,
                          "Выберите друга, чьи желания хотите посмотреть:",
                          reply_markup=markup)
        bot.register_next_step_handler(msg, process_friend_selection_for_wishes, friends)
    except Exception as e:
        bot.reply_to(message, f"Ошибка: {e}", reply_markup=create_main_keyboard())


def process_friend_selection_for_wishes(message, friends):
    try:
        if message.text == "Отмена":
            bot.reply_to(message, "Отменено", reply_markup=create_main_keyboard())
            return

        try:
            choice = int(message.text.split('.')[0])
        except (ValueError, IndexError):
            bot.reply_to(message, "Некорректный формат. Попробуйте снова.",
                        reply_markup=create_main_keyboard())
            return

        if 1 <= choice <= len(friends):
            friend = friends[choice-1]
            wishes = get_wishes(friend['id'])

            if wishes:
                text_of_wishes = "\n".join(
                    [f"{i+1}. {wish['text']} - {STATUSES.get(wish['status'], wish['status'])}"
                     for i, wish in enumerate(wishes)]
                )
                reply = f"Желания {friend['name']} (ID: {friend['id']}):\n{text_of_wishes}"

                markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
                markup.add(types.KeyboardButton(f"Изменить статус желания {friend['name']}"))
                markup.add(types.KeyboardButton("Назад"))

                msg = bot.reply_to(message, reply, reply_markup=markup)
                bot.register_next_step_handler(msg, handle_friend_wishes_action, friend, wishes)
            else:
                reply = f"У {friend['name']} пока нет желаний"
                bot.reply_to(message, reply, reply_markup=create_main_keyboard())
        else:
            bot.reply_to(message,
                        "Некорректный номер. Попробуйте снова.",
                        reply_markup=create_main_keyboard())
    except Exception as e:
        bot.reply_to(message, f"Ошибка: {e}", reply_markup=create_main_keyboard())

def handle_friend_wishes_action(message, friend, wishes):
    try:
        if message.text == "Назад":
            bot.reply_to(message, "Возвращаемся в главное меню", reply_markup=create_main_keyboard())
            return

        if message.text.startswith("Изменить статус желания"):
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
            for i, wish in enumerate(wishes, 1):
                markup.add(types.KeyboardButton(f"{i}. {wish['text']}"))
            markup.add(types.KeyboardButton("Отмена"))

            msg = bot.reply_to(message,
                              f"Выберите желание {friend['name']} для изменения статуса:",
                              reply_markup=markup)
            bot.register_next_step_handler(msg, process_friend_wish_selection, friend, wishes)
        else:
            bot.reply_to(message, "Неизвестная команда", reply_markup=create_main_keyboard())
    except Exception as e:
        bot.reply_to(message, f"Ошибка: {e}", reply_markup=create_main_keyboard())

def process_friend_wish_selection(message, friend, wishes):
    try:
        if message.text == "Отмена":
            bot.reply_to(message, "Отменено", reply_markup=create_main_keyboard())
            return

        try:
            choice = int(message.text.split('.')[0])
        except (ValueError, IndexError):
            bot.reply_to(message, "Некорректный формат. Попробуйте снова.",
                        reply_markup=create_main_keyboard())
            return

        if 1 <= choice <= len(wishes):
            wish = wishes[choice-1]
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
            for status in STATUSES.values():
                markup.add(types.KeyboardButton(status))
            markup.add(types.KeyboardButton("Отмена"))

            msg = bot.reply_to(message,
                             f"Выберите новый статус для желания '{wish['text']}' друга {friend['name']}:",
                             reply_markup=markup)
            bot.register_next_step_handler(msg, process_friend_status_selection, friend, wish)
        else:
            bot.reply_to(message, "Некорректный номер", reply_markup=create_main_keyboard())
    except Exception as e:
        bot.reply_to(message, f"Ошибка: {e}", reply_markup=create_main_keyboard())

def process_friend_status_selection(message, friend, wish):
    try:
        if message.text == "Отмена":
            bot.reply_to(message, "Отменено", reply_markup=create_main_keyboard())
            return

        # Находим ключ статуса по значению
        status_key = next((k for k, v in STATUSES.items() if v == message.text), None)
        if status_key:
            update_wish_status(friend['id'], wish['text'], status_key)
            bot.reply_to(message,
                        f"Статус желания '{wish['text']}' друга {friend['name']} изменен на {message.text}",
                        reply_markup=create_main_keyboard())
        else:
            bot.reply_to(message, "Неизвестный статус", reply_markup=create_main_keyboard())
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

@bot.message_handler(func=lambda message: message.text == "Удалить желание")
def delete_wish_start(message):
    try:
        wishes = get_wishes(message.from_user.id)
        if not wishes:
            bot.reply_to(message, "У вас нет сохранённых желаний для удаления",
                        reply_markup=create_main_keyboard())
            return

        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        for i, wish in enumerate(wishes, 1):
            markup.add(types.KeyboardButton(f"{i}. {wish['text']}"))
        markup.add(types.KeyboardButton("Отмена"))

        msg = bot.reply_to(message,
                          "Выберите желание для удаления:",
                          reply_markup=markup)
        bot.register_next_step_handler(msg, process_delete_wish, wishes)
    except Exception as e:
        bot.reply_to(message, f"Ошибка: {e}", reply_markup=create_main_keyboard())

def process_delete_wish(message, wishes):
    try:
        if message.text == "Отмена":
            bot.reply_to(message, "Удаление отменено",
                        reply_markup=create_main_keyboard())
            return

        try:
            choice = int(message.text.split('.')[0])
        except (ValueError, IndexError):
            bot.reply_to(message, "Некорректный формат. Попробуйте снова.",
                        reply_markup=create_main_keyboard())
            return

        if 1 <= choice <= len(wishes):
            wish_to_delete = wishes[choice-1]['text']

            with db_lock:
                conn = sqlite3.connect(DB_FILE)
                cursor = conn.cursor()
                cursor.execute("DELETE FROM wishes WHERE user_id = ? AND wish = ?",
                             (message.from_user.id, wish_to_delete))
                conn.commit()
                conn.close()

            bot.reply_to(message,
                        f"Желание '{wish_to_delete}' успешно удалено!",
                        reply_markup=create_main_keyboard())
        else:
            bot.reply_to(message,
                        "Некорректный номер. Попробуйте снова.",
                        reply_markup=create_main_keyboard())
    except Exception as e:
        bot.reply_to(message, f"Ошибка при удалении: {e}",
                    reply_markup=create_main_keyboard())

@bot.message_handler(func=lambda message: message.text == "Мои друзья")
def manage_friends(message):
    bot.reply_to(message, "Управление друзьями:", reply_markup=create_friends_keyboard())

@bot.message_handler(func=lambda message: message.text == "Добавить друга")
def add_friend_start(message):
    msg = bot.reply_to(message,
                      "Введите ID друга, имя и дату рождения (ДД.ММ) через запятую:\nПример: 123456789, Иван, 15.05",
                      reply_markup=types.ReplyKeyboardRemove())
    bot.register_next_step_handler(msg, process_add_friend)

def process_add_friend(message):
    try:
        parts = [p.strip() for p in message.text.split(',')]
        if len(parts) != 3:
            raise ValueError("Неверный формат ввода")

        friend_id = int(parts[0])
        friend_name = parts[1]
        birthday = parts[2]

        # Проверка формата даты
        day, month = map(int, birthday.split('.'))
        if not (1 <= day <= 31 and 1 <= month <= 12):
            raise ValueError("Неверный формат даты")

        if add_friend(message.from_user.id, friend_id, friend_name, birthday):
            bot.reply_to(message,
                        f"Друг {friend_name} (ID: {friend_id}) добавлен с ДР {birthday}",
                        reply_markup=create_main_keyboard())
        else:
            bot.reply_to(message,
                        "Этот друг уже есть в вашем списке",
                        reply_markup=create_main_keyboard())
    except ValueError as e:
        bot.reply_to(message,
                    f"Ошибка: {e}\nПожалуйста, используйте формат: ID, Имя, ДД.ММ",
                    reply_markup=create_main_keyboard())
    except Exception as e:
        bot.reply_to(message,
                    f"Ошибка: {e}",
                    reply_markup=create_main_keyboard())

@bot.message_handler(func=lambda message: message.text == "Список друзей")
def show_friends(message):
    try:
        friends = get_friends(message.from_user.id)
        if friends:
            friends_list = "\n".join(
                [f"{i+1}. {f['name']} (ID: {f['id']}) - ДР: {f['birthday']}"
                 for i, f in enumerate(friends)]
            )
            reply = f"Ваши друзья:\n{friends_list}"
        else:
            reply = "У вас пока нет сохранённых друзей"
        bot.reply_to(message, reply, reply_markup=create_friends_keyboard())
    except Exception as e:
        bot.reply_to(message, f"Ошибка: {e}", reply_markup=create_main_keyboard())

@bot.message_handler(func=lambda message: message.text == "Удалить друга")
def delete_friend_start(message):
    try:
        friends = get_friends(message.from_user.id)
        if not friends:
            bot.reply_to(message,
                        "У вас нет сохранённых друзей для удаления",
                        reply_markup=create_main_keyboard())
            return

        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        for i, friend in enumerate(friends, 1):
            markup.add(types.KeyboardButton(f"{i}. {friend['name']}"))
        markup.add(types.KeyboardButton("Отмена"))

        msg = bot.reply_to(message,
                          "Выберите друга для удаления:",
                          reply_markup=markup)
        bot.register_next_step_handler(msg, process_delete_friend, friends)
    except Exception as e:
        bot.reply_to(message, f"Ошибка: {e}", reply_markup=create_main_keyboard())

def process_delete_friend(message, friends):
    try:
        if message.text == "Отмена":
            bot.reply_to(message, "Удаление отменено",
                        reply_markup=create_main_keyboard())
            return

        try:
            choice = int(message.text.split('.')[0])
        except (ValueError, IndexError):
            bot.reply_to(message, "Некорректный формат. Попробуйте снова.",
                        reply_markup=create_main_keyboard())
            return

        if 1 <= choice <= len(friends):
            friend_to_delete = friends[choice-1]
            delete_friend(message.from_user.id, friend_to_delete['id'])
            bot.reply_to(message,
                        f"Друг {friend_to_delete['name']} удалён",
                        reply_markup=create_main_keyboard())
        else:
            bot.reply_to(message,
                        "Некорректный номер. Попробуйте снова.",
                        reply_markup=create_main_keyboard())
    except Exception as e:
        bot.reply_to(message, f"Ошибка при удалении: {e}",
                    reply_markup=create_main_keyboard())


def check_birthdays_periodically():
    while True:
        check_birthdays()
        time.sleep(86400)

def check_birthdays():
    today = datetime.now()
    next_week = today + timedelta(days=7)

    with db_lock:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()

        cursor.execute("SELECT DISTINCT user_id FROM friends")
        user_ids = [row[0] for row in cursor.fetchall()]

        for user_id in user_ids:
            cursor.execute("""
                SELECT friend_name, birthday
                FROM friends
                WHERE user_id = ?
            """, (user_id,))

            for friend_name, birthday in cursor.fetchall():
                try:
                    day, month = map(int, birthday.split('.'))
                    friend_birthday = datetime(today.year, month, day)

                    if today <= friend_birthday <= next_week:
                        days_left = (friend_birthday - today).days
                        if days_left == 0:
                            message = f"🎉 Сегодня день рождения у {friend_name}! 🎂"
                        else:
                            message = f"⏳ До дня рождения {friend_name} осталось {days_left} дней"

                        try:
                            bot.send_message(user_id, message)
                        except:
                            continue
                except:
                    continue

        conn.close()

birthday_thread = threading.Thread(target=check_birthdays_periodically)
birthday_thread.daemon = True
birthday_thread.start()

bot.polling(none_stop=True)
