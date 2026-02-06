"""
Telegram бот для расписания студентов университета.
Поддержка ролей: админ и обычный пользователь.
Экспорт в CSV доступен для всех пользователей.
"""

import logging
import json
import os
import csv
import io
from datetime import datetime, timedelta
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

# ========== КОНФИГУРАЦИЯ ==========
TOKEN = "8452219341:AAF_bQh-paa0NeYOcpNSQJwNk7peRZPct20"

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Файлы для хранения данных
CHANGES_FILE = "schedule_changes.json"
ADMINS_FILE = "admins.json"

# ID администратора (ваш Telegram ID)
ADMIN_IDS = [1165068171]  # Ваш ID

# Базы данных в памяти
users_db = {}
notifications_db = {}
schedule_changes = {}
admins_db = set(ADMIN_IDS)  # Инициализируем с дефолтными админами

# Расписание по группам
schedule_by_group = {
    "ИТ-101": {
        "Понедельник": [
            "09:00 - 10:30 Математика (ауд. 101) - Иванов И.И.",
            "11:00 - 12:30 Физика (ауд. 202) - Петров П.П.",
            "14:00 - 15:30 Программирование (ауд. 305) - Сидоров С.С."
        ],
        "Вторник": [
            "10:00 - 11:30 Иностранный язык (ауд. 105) - Кузнецова Е.В.",
            "12:00 - 13:30 Алгоритмы (ауд. 303) - Сидоров С.С."
        ],
        "Среда": [
            "09:30 - 11:00 Базы данных (ауд. 401) - Васильев В.В.",
            "11:30 - 13:00 Веб-разработка (ауд. 402) - Николаев Н.Н."
        ],
        "Четверг": [
            "10:00 - 11:30 Математика (ауд. 101) - Иванов И.И.",
            "12:00 - 13:30 Физкультура (спортзал) - Смирнов А.А."
        ],
        "Пятница": [
            "09:00 - 10:30 Проектная деятельность (ауд. 505) - Сидоров С.С.",
            "11:00 - 12:30 Семинар (ауд. 201) - Васильев В.В."
        ],
        "Суббота": [],
        "Воскресенье": []
    },
    "ИТ-102": {
        "Понедельник": [
            "09:00 - 10:30 Физика (ауд. 203) - Петров П.П.",
            "11:00 - 12:30 Математика (ауд. 102) - Иванов И.И."
        ],
        "Вторник": [
            "10:00 - 11:30 Программирование (ауд. 306) - Сидоров С.С."
        ],
        "Среда": [
            "09:30 - 11:00 Иностранный язык (ауд. 106) - Кузнецова Е.В."
        ],
        "Четверг": [
            "10:00 - 11:30 Веб-разработка (ауд. 403) - Николаев Н.Н."
        ],
        "Пятница": [
            "09:00 - 10:30 Базы данных (ауд. 402) - Васильев В.В."
        ],
        "Суббота": [],
        "Воскресенье": []
    },
    "ЭК-201": {
        "Понедельник": [
            "09:00 - 10:30 Экономика (ауд. 301) - Орлова О.П.",
            "11:00 - 12:30 Менеджмент (ауд. 302) - Киселев К.Д."
        ],
        "Вторник": [
            "10:00 - 11:30 Маркетинг (ауд. 303) - Захарова З.М."
        ],
        "Среда": [
            "09:30 - 11:00 Финансы (ауд. 304) - Орлова О.П."
        ],
        "Четверг": [
            "10:00 - 11:30 Бухгалтерия (ауд. 305) - Соколов С.В."
        ],
        "Пятница": [
            "09:00 - 10:30 Статистика (ауд. 306) - Захарова З.М."
        ],
        "Суббота": [],
        "Воскресенье": []
    }
}

# Преподаватели и их расписание
teachers = {
    "Иванов И.И.": {
        "Понедельник": [
            "09:00 - 10:30 Математика (ИТ-101, ауд. 101)",
            "11:00 - 12:30 Математика (ИТ-102, ауд. 102)"
        ],
        "Вторник": ["10:00 - 11:30 Математика (ИТ-101, ауд. 101)"],
        "Среда": ["14:00 - 15:30 Консультация (каб. 205)"],
        "Четверг": ["10:00 - 11:30 Математика (ИТ-101, ауд. 101)"],
        "Пятница": ["13:00 - 14:30 Семинар (ауд. 103)"],
        "Суббота": [],
        "Воскресенье": []
    },
    "Сидоров С.С.": {
        "Понедельник": ["14:00 - 15:30 Программирование (ИТ-101, ауд. 305)"],
        "Вторник": ["12:00 - 13:30 Алгоритмы (ИТ-101, ауд. 303)"],
        "Среда": ["10:00 - 11:30 Программирование (ИТ-102, ауд. 306)"],
        "Четверг": [],
        "Пятница": ["09:00 - 10:30 Проектная деятельность (ИТ-101, ауд. 505)"],
        "Суббота": ["10:00 - 12:00 Консультация (каб. 305)"],
        "Воскресенье": []
    },
    "Орлова О.П.": {
        "Понедельник": ["09:00 - 10:30 Экономика (ЭК-201, ауд. 301)"],
        "Вторник": ["14:00 - 15:30 Консультация (каб. 401)"],
        "Среда": ["09:30 - 11:00 Финансы (ЭК-201, ауд. 304)"],
        "Четверг": ["11:00 - 12:30 Экономика (ЭК-202, ауд. 302)"],
        "Пятница": [],
        "Суббота": [],
        "Воскресенье": []
    }
}

# Список всех групп
all_groups = list(schedule_by_group.keys())

# Список всех преподавателей
all_teachers = list(teachers.keys())

# Перевод дней недели
day_translation = {
    "Monday": "Понедельник",
    "Tuesday": "Вторник",
    "Wednesday": "Среда",
    "Thursday": "Четверг",
    "Friday": "Пятница",
    "Saturday": "Суббота",
    "Sunday": "Воскресенье"
}

# Обратный перевод дней недели
reverse_day_translation = {v: k for k, v in day_translation.items()}

# ========== ФУНКЦИИ ДЛЯ РАБОТЫ С РОЛЯМИ ==========
def is_admin(user_id):
    """Проверяет, является ли пользователь администратором."""
    # Гарантируем, что владелец (1165068171) всегда админ
    if user_id == 1165068171:
        return True
    return user_id in admins_db

def save_admins():
    """Сохраняет список администраторов в файл."""
    try:
        # Гарантируем, что владелец всегда в списке
        admins_to_save = set(admins_db)
        admins_to_save.add(1165068171)
        
        with open(ADMINS_FILE, 'w', encoding='utf-8') as f:
            json.dump(list(admins_to_save), f, ensure_ascii=False, indent=2)
        logger.info(f"Сохранено {len(admins_to_save)} администраторов (включая владельца)")
    except Exception as e:
        logger.error(f"Ошибка сохранения администраторов: {e}")

def load_admins():
    """Загружает список администраторов из файла."""
    global admins_db
    try:
        if os.path.exists(ADMINS_FILE):
            with open(ADMINS_FILE, 'r', encoding='utf-8') as f:
                admins_list = json.load(f)
                admins_db = set(admins_list)
            logger.info(f"Загружено {len(admins_db)} администраторов из файла")
        else:
            admins_db = set()
            logger.info("Файл администраторов не найден, создан новый список")
    except Exception as e:
        logger.error(f"Ошибка загрузки администраторов: {e}")
        admins_db = set()
    
    # Гарантируем, что владелец всегда администратор
    admins_db.add(1165068171)
    logger.info(f"Владелец (ID: 1165068171) добавлен как администратор")

# ========== ФУНКЦИИ РАБОТЫ С ИЗМЕНЕНИЯМИ ==========
def load_changes():
    """Загрузить изменения расписания из файла."""
    global schedule_changes
    if os.path.exists(CHANGES_FILE):
        try:
            with open(CHANGES_FILE, 'r', encoding='utf-8') as f:
                schedule_changes = json.load(f)
            logger.info(f"Загружено {len(schedule_changes)} изменений расписания")
        except Exception as e:
            logger.error(f"Ошибка загрузки изменений: {e}")
            schedule_changes = {}
    else:
        schedule_changes = {}

def save_changes():
    """Сохранить изменения расписания в файл."""
    try:
        with open(CHANGES_FILE, 'w', encoding='utf-8') as f:
            json.dump(schedule_changes, f, ensure_ascii=False, indent=2)
        logger.info("Изменения расписания сохранены")
    except Exception as e:
        logger.error(f"Ошибка сохранения изменений: {e}")

def apply_changes_to_schedule(group_name, day_name, original_lessons):
    """Применить изменения к расписанию на определенный день."""
    if not schedule_changes:
        return original_lessons
    
    key = f"{group_name}:{day_name}"
    if key in schedule_changes:
        changes = schedule_changes[key]
        result_lessons = []
        
        for lesson in original_lessons:
            lesson_key = lesson[:50]
            
            # Проверяем, была ли пара отменена
            is_cancelled = any(
                change.get("type") == "cancelled" and lesson_key in change.get("original", "")
                for change in changes
            )
            
            if not is_cancelled:
                # Проверяем, есть ли замена для этой пары
                replacement = None
                for change in changes:
                    if change.get("type") == "replacement" and lesson_key in change.get("original", ""):
                        replacement = change.get("replacement")
                        break
                
                if replacement:
                    result_lessons.append(f"🔄 {replacement}")
                else:
                    result_lessons.append(lesson)
        
        # Добавляем дополнительные пары
        for change in changes:
            if change.get("type") == "additional":
                result_lessons.append(f"➕ {change.get('lesson')}")
        
        return result_lessons
    
    return original_lessons

def get_changes_for_day(group_name, day_name):
    """Получить изменения для определенной группы и дня."""
    key = f"{group_name}:{day_name}"
    return schedule_changes.get(key, [])

# ========== ФУНКЦИИ ЭКСПОРТА В CSV ==========
def parse_lesson_details(lesson_str):
    """Парсинг деталей занятия из строки."""
    try:
        # Убираем эмодзи если есть
        clean_lesson = lesson_str
        if lesson_str.startswith('🔄 ') or lesson_str.startswith('➕ '):
            clean_lesson = lesson_str[2:]
        
        parts = clean_lesson.split(' ')
        
        if len(parts) < 3:
            return {
                "time": "00:00 - 00:00",
                "subject": clean_lesson,
                "auditorium": "",
                "teacher": ""
            }
        
        # Время
        time_part = f"{parts[0]} {parts[1]} {parts[2]}"
        start_time = parts[0]
        end_time = parts[2]
        
        # Предмет, аудитория, преподаватель
        subject_parts = []
        auditorium = ""
        teacher = ""
        
        # Находим аудиторию (в скобках)
        for i in range(3, len(parts)):
            if '(' in parts[i] and ')' in parts[i]:
                # Убираем скобки
                auditorium = parts[i].replace('(', '').replace(')', '')
            elif parts[i] == '-' and i + 1 < len(parts):
                # Все что после дефиса - преподаватель
                teacher = ' '.join(parts[i+1:])
                break
            else:
                subject_parts.append(parts[i])
        
        subject = ' '.join(subject_parts).strip()
        
        return {
            "time": time_part,
            "start_time": start_time,
            "end_time": end_time,
            "subject": subject,
            "auditorium": auditorium,
            "teacher": teacher
        }
    except Exception as e:
        logger.error(f"Ошибка парсинга занятия: {e} - {lesson_str}")
        return {
            "time": "00:00 - 00:00",
            "start_time": "00:00",
            "end_time": "00:00",
            "subject": lesson_str,
            "auditorium": "",
            "teacher": ""
        }

def create_csv_for_group(group_name, weeks=4):
    """Создать CSV файл для группы на несколько недель."""
    output = io.StringIO()
    writer = csv.writer(output, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
    
    # Заголовки CSV с правильной кодировкой
    writer.writerow(["Дата", "День недели", "Начало", "Конец", "Предмет", "Аудитория", "Преподаватель", "Статус"])
    
    today = datetime.now().date()
    
    for week_offset in range(weeks):
        for day_name_ru, lessons in schedule_by_group[group_name].items():
            if not lessons:
                continue
                
            day_name_en = reverse_day_translation.get(day_name_ru)
            if not day_name_en:
                continue
            
            # Находим дату для этого дня недели
            current_week_date = today + timedelta(days=week_offset * 7)
            target_weekday = list(day_translation.keys()).index(day_name_en)
            current_weekday = current_week_date.weekday()
            day_date = current_week_date + timedelta(days=target_weekday - current_weekday)
            
            # Применяем изменения
            lessons_with_changes = apply_changes_to_schedule(group_name, day_name_ru, lessons)
            
            for lesson in lessons_with_changes:
                details = parse_lesson_details(lesson)
                
                # Определяем статус
                status = "По расписанию"
                if lesson.startswith('🔄 '):
                    status = "Замена"
                elif lesson.startswith('➕ '):
                    status = "Дополнительно"
                elif "Отменена" in lesson:
                    status = "Отменена"
                
                # Записываем строку в CSV
                writer.writerow([
                    day_date.strftime("%d.%m.%Y"),
                    day_name_ru,
                    details["start_time"],
                    details["end_time"],
                    details["subject"],
                    details["auditorium"],
                    details["teacher"],
                    status
                ])
    
    return output.getvalue()

def create_csv_for_teacher(teacher_name, weeks=4):
    """Создать CSV файл для преподавателя на несколько недель."""
    output = io.StringIO()
    writer = csv.writer(output, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
    
    # Заголовки CSV
    writer.writerow(["Дата", "День недели", "Начало", "Конец", "Занятие", "Группа", "Аудитория", "Статус"])
    
    today = datetime.now().date()
    
    if teacher_name not in teachers:
        return output.getvalue()
    
    for week_offset in range(weeks):
        for day_name_ru, lessons in teachers[teacher_name].items():
            if not lessons:
                continue
                
            day_name_en = reverse_day_translation.get(day_name_ru)
            if not day_name_en:
                continue
            
            # Находим дату для этого дня недели
            current_week_date = today + timedelta(days=week_offset * 7)
            target_weekday = list(day_translation.keys()).index(day_name_en)
            current_weekday = current_week_date.weekday()
            day_date = current_week_date + timedelta(days=target_weekday - current_weekday)
            
            for lesson in lessons:
                # Парсим занятие преподавателя
                parts = lesson.split(' ')
                if len(parts) >= 3:
                    time_part = f"{parts[0]} {parts[1]} {parts[2]}"
                    start_time = parts[0]
                    end_time = parts[2]
                    
                    # Извлекаем информацию о группе и аудитории
                    lesson_info = ' '.join(parts[3:])
                    group = ""
                    auditorium = ""
                    
                    # Ищем группу в формате (ИТ-101)
                    for part in parts:
                        if any(group_name in part for group_name in all_groups):
                            group = part.strip(',')
                        if '(' in part and ')' in part:
                            auditorium = part.replace('(', '').replace(')', '')
                    
                    writer.writerow([
                        day_date.strftime("%d.%m.%Y"),
                        day_name_ru,
                        start_time,
                        end_time,
                        lesson_info,
                        group,
                        auditorium,
                        "По расписанию"
                    ])
    
    return output.getvalue()

# ========== КЛАВИАТУРЫ ==========
def get_main_keyboard(user_id):
    """Создает основную клавиатуру меню в зависимости от роли."""
    if is_admin(user_id):
        keyboard = [
            [KeyboardButton("📅 Сегодня"), KeyboardButton("📆 Завтра")],
            [KeyboardButton("📋 Полное расписание"), KeyboardButton("📤 Экспорт в CSV")],
            [KeyboardButton("👥 Выбор группы"), KeyboardButton("👨‍🏫 Выбор преподавателя")],
            [KeyboardButton("🔄 Изменения расписания"), KeyboardButton("⚙️ Админ панель")],
            [KeyboardButton("🔔 Оповещения"), KeyboardButton("❓ Помощь")]
        ]
    else:
        keyboard = [
            [KeyboardButton("📅 Сегодня"), KeyboardButton("📆 Завтра")],
            [KeyboardButton("📋 Полное расписание"), KeyboardButton("📤 Экспорт в CSV")],
            [KeyboardButton("👥 Выбор группы"), KeyboardButton("👨‍🏫 Выбор преподавателя")],
            [KeyboardButton("🔔 Оповещения"), KeyboardButton("❓ Помощь")]
        ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_admin_keyboard():
    """Создает клавиатуру для админ панели."""
    keyboard = [
        [KeyboardButton("👤 Управление пользователями"), KeyboardButton("📊 Статистика")],
        [KeyboardButton("📢 Рассылка"), KeyboardButton("🔄 Управление изменениями")],
        [KeyboardButton("➕ Добавить админа"), KeyboardButton("➖ Удалить админа")],
        [KeyboardButton("🔙 В главное меню")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_group_selection_keyboard():
    """Создает инлайн-клавиатуру для выбора группы."""
    keyboard = []
    for i in range(0, len(all_groups), 2):
        row = []
        for j in range(2):
            if i + j < len(all_groups):
                group = all_groups[i + j]
                row.append(InlineKeyboardButton(group, callback_data=f"select_group:{group}"))
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")])
    return InlineKeyboardMarkup(keyboard)

def get_teacher_selection_keyboard():
    """Создает инлайн-клавиатуру для выбора преподавателя."""
    keyboard = []
    for i in range(0, len(all_teachers), 2):
        row = []
        for j in range(2):
            if i + j < len(all_teachers):
                teacher = all_teachers[i + j]
                row.append(InlineKeyboardButton(teacher, callback_data=f"select_teacher:{teacher}"))
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")])
    return InlineKeyboardMarkup(keyboard)

def get_notify_keyboard():
    """Создает клавиатуру для настройки оповещений."""
    keyboard = [
        [KeyboardButton("🕘 За 30 минут"), KeyboardButton("🕗 За 1 час")],
        [KeyboardButton("🕖 За 2 часа")],
        [KeyboardButton("⏰ Тестовое уведомление")],
        [KeyboardButton("🔕 Выключить"), KeyboardButton("🔙 Назад")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_changes_keyboard():
    """Создает клавиатуру для управления изменениями расписания."""
    keyboard = [
        [KeyboardButton("📝 Добавить изменение")],
        [KeyboardButton("📋 Посмотреть изменения")],
        [KeyboardButton("🗑️ Удалить изменение"), KeyboardButton("🔙 Назад")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_export_keyboard():
    """Создает клавиатуру для выбора типа экспорта."""
    keyboard = [
        [KeyboardButton("📅 Экспорт на месяц"), KeyboardButton("📆 Экспорт на семестр")],
        [KeyboardButton("📋 Экспорт полного расписания")],
        [KeyboardButton("🔙 Назад")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# ========== ОСНОВНЫЕ КОМАНДЫ (ДЛЯ ВСЕХ) ==========
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start."""
    user_id = update.effective_user.id
    username = update.effective_user.username or "пользователь"
    
    # Гарантируем, что владелец всегда админ
    if user_id == 1165068171:
        admins_db.add(1165068171)
        save_admins()
    
    # Инициализируем пользователя
    users_db[user_id] = {
        "notifications": False,
        "selected_group": None,
        "selected_teacher": None,
        "view_mode": "group",
        "awaiting_change": False,
        "change_data": {},
        "username": username,
        "join_date": datetime.now().isoformat(),
        "role": "admin" if is_admin(user_id) else "user"
    }
    
    # Приветствие в зависимости от роли
    if is_admin(user_id):
        welcome_text = (
            f"👑 *Добро пожаловать, администратор {username}!*\n\n"
            "*Ваши привилегии:*\n"
            "• Полный доступ к расписанию\n"
            "• Управление изменениями расписания\n"
            "• Управление пользователями\n"
            "• Рассылка сообщений\n"
            "• Просмотр статистики\n\n"
            "*Основные функции:*\n"
            "• Просмотр расписания на сегодня/завтра\n"
            "• Полное расписание\n"
            "• Выбор группы/преподавателя\n"
            "• Экспорт в CSV (для всех)\n"
            "• Настройка оповещений\n\n"
            "Используйте кнопки ниже или команды:\n"
            "/admin - админ панель\n"
            "/export - экспорт в CSV\n"
            "/help - помощь"
        )
    else:
        welcome_text = (
            f"👋 *Добро пожаловать, {username}!*\n\n"
            "*Что я умею:*\n"
            "• Показывать расписание на сегодня/завтра\n"
            "• Показывать полное расписание\n"
            "• Выбор группы для просмотра расписания\n"
            "• Просмотр расписания преподавателей\n"
            "• Экспорт расписания в CSV формат\n"
            "• Отправлять уведомления о парах\n\n"
            "Используйте кнопки ниже или команды:\n"
            "/today - расписание на сегодня\n"
            "/tomorrow - расписание на завтра\n"
            "/full - полное расписание\n"
            "/group - выбрать группу\n"
            "/teacher - выбрать преподавателя\n"
            "/export - экспорт в CSV\n"
            "/notify - настройка оповещений\n"
            "/help - помощь"
        )
    
    await update.message.reply_text(
        welcome_text,
        parse_mode='Markdown',
        reply_markup=get_main_keyboard(user_id)
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /help."""
    user_id = update.effective_user.id
    
    if is_admin(user_id):
        help_text = (
            "*👑 Администраторские команды:*\n\n"
            "/admin - открыть админ панель\n"
            "/users - список пользователей\n"
            "/stats - статистика бота\n"
            "/broadcast - рассылка сообщений\n"
            "/addadmin - добавить администратора\n"
            "/removeadmin - удалить администратора\n\n"
            "*📚 Основные команды (для всех):*\n\n"
            "/start - начать работу\n"
            "/today - расписание на сегодня\n"
            "/tomorrow - расписание на завтра\n"
            "/full - полное расписание\n"
            "/group - выбрать группу\n"
            "/teacher - выбрать преподавателя\n"
            "/export - экспорт в CSV формат\n"
            "/notify - настройка оповещений\n"
            "/myinfo - мои настройки\n"
            "/help - помощь"
        )
    else:
        help_text = (
            "*📚 Доступные команды:*\n\n"
            "/start - начать работу\n"
            "/today - расписание на сегодня\n"
            "/tomorrow - расписание на завтра\n"
            "/full - полное расписание\n"
            "/group - выбрать группу для просмотра расписания\n"
            "/teacher - выбрать преподавателя для просмотра расписания\n"
            "/export - экспорт расписания в CSV формат\n"
            "/notify - настройка оповещений\n"
            "/test_notify - тестовое уведомление\n"
            "/stop_notify - отключить оповещения\n"
            "/myinfo - мои текущие настройки\n"
            "/help - помощь\n\n"
            "*Или используйте кнопки меню!*"
        )
    
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def group_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /group для выбора группы."""
    await update.message.reply_text(
        "*👥 Выберите группу:*\n\n"
        "Доступные группы: " + ", ".join(all_groups),
        parse_mode='Markdown',
        reply_markup=get_group_selection_keyboard()
    )

async def teacher_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /teacher для выбора преподавателя."""
    await update.message.reply_text(
        "*👨‍🏫 Выберите преподавателя:*\n\n"
        "Доступные преподаватели: " + ", ".join(all_teachers),
        parse_mode='Markdown',
        reply_markup=get_teacher_selection_keyboard()
    )

async def myinfo_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /myinfo для показа текущих настроек."""
    user_id = update.effective_user.id
    if user_id in users_db:
        user_data = users_db[user_id]
        group_info = user_data.get("selected_group", "не выбрана")
        teacher_info = user_data.get("selected_teacher", "не выбран")
        view_mode = "группа" if user_data.get("view_mode") == "group" else "преподаватель"
        notify_status = "включены" if user_data.get("notifications") else "выключены"
        role = "👑 Администратор" if is_admin(user_id) else "👤 Пользователь"
        
        info_text = (
            "*📊 Ваши текущие настройки:*\n\n"
            f"• Роль: *{role}*\n"
            f"• Выбранная группа: *{group_info}*\n"
            f"• Выбранный преподаватель: *{teacher_info}*\n"
            f"• Режим просмотра: *{view_mode}*\n"
            f"• Оповещения: *{notify_status}*\n\n"
            f"Используйте команды:\n"
            f"/group - изменить группу\n"
            f"/teacher - изменить преподавателя\n"
            f"/export - экспортировать расписание"
        )
    else:
        info_text = "Вы еще не начали работу с ботом. Используйте /start"
    await update.message.reply_text(info_text, parse_mode='Markdown')

# ========== ФУНКЦИИ РАСПИСАНИЯ ==========
def get_day_schedule_for_group(group_name, day_offset=0):
    """Получить расписание для группы на заданный день с учетом изменений."""
    if group_name not in schedule_by_group:
        return None, []
    
    target_date = datetime.now() + timedelta(days=day_offset)
    english_day = target_date.strftime("%A")
    russian_day = day_translation.get(english_day, english_day)
    
    schedule = schedule_by_group[group_name]
    original_lessons = schedule.get(russian_day, [])
    
    # Применяем изменения
    lessons_with_changes = apply_changes_to_schedule(group_name, russian_day, original_lessons)
    
    return russian_day, lessons_with_changes

def get_day_schedule_for_teacher(teacher_name, day_offset=0):
    """Получить расписание для преподавателя на заданный день."""
    if teacher_name not in teachers:
        return None, []
    
    target_date = datetime.now() + timedelta(days=day_offset)
    english_day = target_date.strftime("%A")
    russian_day = day_translation.get(english_day, english_day)
    
    schedule = teachers[teacher_name]
    lessons = schedule.get(russian_day, [])
    
    return russian_day, lessons

async def today_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /today для расписания на сегодня."""
    user_id = update.effective_user.id
    if user_id not in users_db:
        await update.message.reply_text("Сначала выберите группу или преподавателя! Используйте /start")
        return
    
    user_data = users_db[user_id]
    
    if user_data["view_mode"] == "group":
        group_name = user_data.get("selected_group")
        if not group_name:
            await update.message.reply_text(
                "Сначала выберите группу! Используйте кнопку '👥 Выбор группы' или команду /group",
                reply_markup=get_main_keyboard(user_id)
            )
            return
        
        russian_day, lessons = get_day_schedule_for_group(group_name, 0)
        
        if not russian_day:
            await update.message.reply_text("Ошибка определения дня недели")
            return
        
        # Проверяем, есть ли изменения для этого дня
        changes = get_changes_for_day(group_name, russian_day)
        has_changes = len(changes) > 0
        
        if lessons:
            response = f"*📅 Расписание на сегодня для группы {group_name} ({russian_day})*"
            if has_changes:
                response += " ⚠️ *Есть изменения*\n\n"
            else:
                response += ":\n\n"
            
            for i, lesson in enumerate(lessons, 1):
                response += f"{i}. {lesson}\n"
            
            response += f"\n_Всего пар: {len(lessons)}_"
            
            if has_changes:
                response += "\n\n*Изменения:*"
                for change in changes:
                    if change["type"] == "replacement":
                        response += f"\n🔄 Замена: {change.get('replacement', '')}"
                    elif change["type"] == "cancelled":
                        response += f"\n❌ Отмена"
                    elif change["type"] == "additional":
                        response += f"\n➕ Дополнительная пара"
        else:
            response = f"*🎉 Сегодня ({russian_day}) у группы {group_name} пар нет!*"
    else:
        teacher_name = user_data.get("selected_teacher")
        if not teacher_name:
            await update.message.reply_text(
                "Сначала выберите преподавателя! Используйте кнопку '👨‍🏫 Выбор преподавателя' или команду /teacher",
                reply_markup=get_main_keyboard(user_id)
            )
            return
        
        russian_day, lessons = get_day_schedule_for_teacher(teacher_name, 0)
        
        if lessons:
            response = f"*📅 Расписание на сегодня для преподавателя {teacher_name} ({russian_day}):*\n\n"
            for i, lesson in enumerate(lessons, 1):
                response += f"{i}. {lesson}\n"
            response += f"\n_Всего занятий: {len(lessons)}_"
        else:
            response = f"*🎉 Сегодня ({russian_day}) у преподавателя {teacher_name} занятий нет!*"
    
    await update.message.reply_text(response, parse_mode='Markdown')

async def tomorrow_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /tomorrow для расписания на завтра."""
    user_id = update.effective_user.id
    if user_id not in users_db:
        await update.message.reply_text("Сначала выберите группу или преподавателя! Используйте /start")
        return
    
    user_data = users_db[user_id]
    
    if user_data["view_mode"] == "group":
        group_name = user_data.get("selected_group")
        if not group_name:
            await update.message.reply_text(
                "Сначала выберите группу! Используйте кнопку '👥 Выбор группы' или команду /group",
                reply_markup=get_main_keyboard(user_id)
            )
            return
        
        russian_day, lessons = get_day_schedule_for_group(group_name, 1)
        
        if not russian_day:
            await update.message.reply_text("Ошибка определения дня недели")
            return
        
        # Проверяем, есть ли изменения для этого дня
        changes = get_changes_for_day(group_name, russian_day)
        has_changes = len(changes) > 0
        
        if lessons:
            response = f"*📆 Расписание на завтра для группы {group_name} ({russian_day})*"
            if has_changes:
                response += " ⚠️ *Есть изменения*\n\n"
            else:
                response += ":\n\n"
            
            for i, lesson in enumerate(lessons, 1):
                response += f"{i}. {lesson}\n"
            
            response += f"\n_Всего пар: {len(lessons)}_"
            
            if has_changes:
                response += "\n\n*Изменения:*"
                for change in changes:
                    if change["type"] == "replacement":
                        response += f"\n🔄 Замена: {change.get('replacement', '')}"
                    elif change["type"] == "cancelled":
                        response += f"\n❌ Отмена"
                    elif change["type"] == "additional":
                        response += f"\n➕ Дополнительная пара"
        else:
            response = f"*🎉 Завтра ({russian_day}) у группы {group_name} пар нет!*"
    else:
        teacher_name = user_data.get("selected_teacher")
        if not teacher_name:
            await update.message.reply_text(
                "Сначала выберите преподавателя! Используйте кнопку '👨‍🏫 Выбор преподавателя' или команду /teacher",
                reply_markup=get_main_keyboard(user_id)
            )
            return
        
        russian_day, lessons = get_day_schedule_for_teacher(teacher_name, 1)
        
        if lessons:
            response = f"*📆 Расписание на завтра для преподавателя {teacher_name} ({russian_day}):*\n\n"
            for i, lesson in enumerate(lessons, 1):
                response += f"{i}. {lesson}\n"
            response += f"\n_Всего занятий: {len(lessons)}_"
        else:
            response = f"*🎉 Завтра ({russian_day}) у преподавателя {teacher_name} занятий нет!*"
    
    await update.message.reply_text(response, parse_mode='Markdown')

async def full_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /full для полного расписания."""
    user_id = update.effective_user.id
    if user_id not in users_db:
        await update.message.reply_text("Сначала выберите группу или преподавателя! Используйте /start")
        return
    
    user_data = users_db[user_id]
    
    if user_data["view_mode"] == "group":
        group_name = user_data.get("selected_group")
        if not group_name:
            await update.message.reply_text(
                "Сначала выберите группу! Используйте кнопку '👥 Выбор группы' или команду /group",
                reply_markup=get_main_keyboard(user_id)
            )
            return
        
        response = f"*📋 Полное расписание на неделю для группы {group_name}:*\n\n"
        for day_name in ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]:
            lessons = apply_changes_to_schedule(group_name, day_name, schedule_by_group[group_name].get(day_name, []))
            changes = get_changes_for_day(group_name, day_name)
            has_changes = len(changes) > 0
            
            response += f"*{day_name}*"
            if has_changes:
                response += " ⚠️\n"
            else:
                response += ":\n"
            
            if lessons:
                for i, lesson in enumerate(lessons, 1):
                    response += f"  {i}. {lesson}\n"
            else:
                response += "  🎉 Выходной\n"
            
            response += "\n"
    else:
        teacher_name = user_data.get("selected_teacher")
        if not teacher_name:
            await update.message.reply_text(
                "Сначала выберите преподавателя! Используйте кнопку '👨‍🏫 Выбор преподавателя' или команду /teacher",
                reply_markup=get_main_keyboard(user_id)
            )
            return
        
        schedule = teachers.get(teacher_name, {})
        response = f"*📋 Полное расписание на неделю для преподавателя {teacher_name}:*\n\n"
        for day, lessons in schedule.items():
            response += f"*{day}:*\n"
            if lessons:
                for i, lesson in enumerate(lessons, 1):
                    response += f"  {i}. {lesson}\n"
            else:
                response += "  🎉 Выходной\n"
            response += "\n"
    
    await update.message.reply_text(response, parse_mode='Markdown')

# ========== ЭКСПОРТ В CSV (ДЛЯ ВСЕХ) ==========
async def export_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /export для экспорта в CSV."""
    user_id = update.effective_user.id
    
    if user_id not in users_db:
        await update.message.reply_text("Сначала выберите группу или преподавателя с помощью /start")
        return
    
    user_data = users_db[user_id]
    
    if user_data["view_mode"] == "group":
        group_name = user_data.get("selected_group")
        if not group_name:
            await update.message.reply_text(
                "Сначала выберите группу для экспорта!\n"
                "Используйте кнопку '👥 Выбор группы' или команду /group",
                parse_mode='Markdown',
                reply_markup=get_main_keyboard(user_id)
            )
            return
        
        await update.message.reply_text(
            f"*📤 Экспорт расписания группы {group_name}*\n\n"
            f"Выберите период для экспорта:",
            parse_mode='Markdown',
            reply_markup=get_export_keyboard()
        )
        context.user_data["export_type"] = "group"
        context.user_data["export_name"] = group_name
        
    else:
        teacher_name = user_data.get("selected_teacher")
        if not teacher_name:
            await update.message.reply_text(
                "Сначала выберите преподавателя для экспорта!\n"
                "Используйте кнопку '👨‍🏫 Выбор преподавателя' или команду /teacher",
                parse_mode='Markdown',
                reply_markup=get_main_keyboard(user_id)
            )
            return
        
        await update.message.reply_text(
            f"*📤 Экспорт расписания преподавателя {teacher_name}*\n\n"
            f"Выберите период для экспорта:",
            parse_mode='Markdown',
            reply_markup=get_export_keyboard()
        )
        context.user_data["export_type"] = "teacher"
        context.user_data["export_name"] = teacher_name

async def process_export(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка выбора типа экспорта."""
    text = update.message.text
    user_id = update.effective_user.id
    
    export_type = context.user_data.get("export_type")
    export_name = context.user_data.get("export_name")
    
    if not export_type or not export_name:
        await update.message.reply_text("Ошибка экспорта. Попробуйте снова.")
        return
    
    if text == "📅 Экспорт на месяц":
        weeks = 4
        period = "месяц"
    elif text == "📆 Экспорт на семестр":
        weeks = 16
        period = "семестр"
    elif text == "📋 Экспорт полного расписания":
        weeks = 1  # Только текущая неделя для полного расписания
        period = "неделю"
    elif text == "🔙 Назад":
        await update.message.reply_text(
            "*Главное меню:*",
            parse_mode='Markdown',
            reply_markup=get_main_keyboard(user_id)
        )
        return
    else:
        await update.message.reply_text(
            "Пожалуйста, используйте кнопки для выбора типа экспорта",
            reply_markup=get_export_keyboard()
        )
        return
    
    await update.message.reply_text(f"⏳ Создаю CSV файл на {period}...")
    
    try:
        if export_type == "group":
            csv_data = create_csv_for_group(export_name, weeks)
            filename = f"расписание_{export_name}_{period}.csv"
            caption = f"📅 Расписание группы *{export_name}* на {period}\n\nФайл в формате CSV."
        else:
            csv_data = create_csv_for_teacher(export_name, weeks)
            filename = f"расписание_{export_name}_{period}.csv"
            caption = f"📅 Расписание преподавателя *{export_name}* на {period}\n\nФайл в формате CSV."
        
        # Отправляем файл пользователю
        await update.message.reply_document(
            document=io.BytesIO(csv_data.encode('utf-8-sig')),
            filename=filename,
            caption=caption,
            parse_mode='Markdown'
        )
        
        logger.info(f"Пользователь {user_id} экспортировал {export_type} {export_name} на {period}")
        
    except Exception as e:
        logger.error(f"Ошибка экспорта: {e}")
        await update.message.reply_text(
            "❌ *Произошла ошибка при создании файла!*\n\n"
            "Попробуйте еще раз или обратитесь к администратору.",
            parse_mode='Markdown'
        )

# ========== АДМИН КОМАНДЫ ==========
async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /admin для админ панели."""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text(
            "❌ *У вас нет прав администратора!*\n\n"
            "Эта команда доступна только администраторам бота.",
            parse_mode='Markdown'
        )
        return
    
    await update.message.reply_text(
        "👑 *Административная панель*\n\n"
        "*Доступные функции:*\n"
        "• Управление пользователями\n"
        "• Просмотр статистики\n"
        "• Рассылка сообщений\n"
        "• Управление изменениями расписания\n"
        "• Управление администраторами\n\n"
        "Выберите действие:",
        parse_mode='Markdown',
        reply_markup=get_admin_keyboard()
    )

async def admin_panel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик кнопок админ панели."""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("❌ У вас нет прав администратора!")
        return
    
    text = update.message.text
    
    if text == "👤 Управление пользователями":
        await manage_users_command(update, context)
    elif text == "📊 Статистика":
        await stats_command(update, context)
    elif text == "📢 Рассылка":
        await broadcast_command(update, context)
    elif text == "🔄 Управление изменениями":
        await admin_changes_command(update, context)
    elif text == "➕ Добавить админа":
        context.user_data["awaiting_admin_id"] = True
        await update.message.reply_text(
            "✍️ *Добавление администратора*\n\n"
            "Отправьте ID пользователя, которого хотите сделать администратором.\n"
            "Чтобы отменить, отправьте /cancel",
            parse_mode='Markdown'
        )
    elif text == "➖ Удалить админа":
        await remove_admin_command(update, context)
    elif text == "🔙 В главное меню":
        await update.message.reply_text(
            "*Главное меню:*",
            parse_mode='Markdown',
            reply_markup=get_main_keyboard(user_id)
        )
    else:
        await update.message.reply_text(
            "Пожалуйста, используйте кнопки админ-панели",
            reply_markup=get_admin_keyboard()
        )

async def manage_users_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать список пользователей."""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("❌ У вас нет прав администратора!")
        return
    
    if not users_db:
        await update.message.reply_text("📭 *Пользователей пока нет*", parse_mode='Markdown')
        return
    
    response = "*👥 Список пользователей:*\n\n"
    
    for uid, user_data in list(users_db.items())[:50]:  # Показываем первых 50 пользователей
        username = user_data.get("username", "без username")
        role = "👑 Админ" if is_admin(uid) else "👤 Пользователь"
        group = user_data.get("selected_group", "не выбрана")
        join_date = user_data.get("join_date", "неизвестно")
        
        # Парсим дату
        try:
            join_dt = datetime.fromisoformat(join_date)
            formatted_date = join_dt.strftime("%d.%m.%Y")
        except:
            formatted_date = join_date
        
        response += f"*ID:* {uid}\n"
        response += f"*Username:* @{username}\n"
        response += f"*Роль:* {role}\n"
        response += f"*Группа:* {group}\n"
        response += f"*Дата регистрации:* {formatted_date}\n"
        response += "─" * 20 + "\n\n"
    
    response += f"\n*Всего пользователей:* {len(users_db)}"
    
    await update.message.reply_text(response, parse_mode='Markdown')

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать статистику бота."""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("❌ У вас нет прав администратора!")
        return
    
    total_users = len(users_db)
    active_users = sum(1 for u in users_db.values() if u.get("selected_group"))
    admin_count = len(admins_db)
    changes_count = len(schedule_changes)
    
    # Считаем пользователей по группам
    groups_stats = {}
    for user_data in users_db.values():
        group = user_data.get("selected_group")
        if group:
            groups_stats[group] = groups_stats.get(group, 0) + 1
    
    groups_text = "\n".join([f"  • {group}: {count}" for group, count in groups_stats.items()])
    
    response = (
        "*📊 Статистика бота*\n\n"
        f"*Общее количество пользователей:* {total_users}\n"
        f"*Активных пользователей (с выбранной группой):* {active_users}\n"
        f"*Количество администраторов:* {admin_count}\n"
        f"*Изменений в расписании:* {changes_count}\n\n"
        f"*Пользователи по группам:*\n{groups_text if groups_text else '  • Данные отсутствуют'}"
    )
    
    await update.message.reply_text(response, parse_mode='Markdown')

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начать процесс рассылки."""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("❌ У вас нет прав администратора!")
        return
    
    context.user_data["awaiting_broadcast"] = True
    await update.message.reply_text(
        "📢 *Рассылка сообщений*\n\n"
        "Отправьте сообщение, которое хотите разослать всем пользователям.\n"
        "Можно использовать Markdown разметку.\n"
        "Чтобы отменить, отправьте /cancel",
        parse_mode='Markdown'
    )

async def process_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка рассылки сообщений."""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        return
    
    message = update.message.text
    total_users = len(users_db)
    successful = 0
    failed = 0
    
    await update.message.reply_text(f"⏳ Начинаю рассылку для {total_users} пользователей...")
    
    for uid in users_db.keys():
        try:
            await context.bot.send_message(
                chat_id=uid,
                text=f"*📢 Объявление от администрации:*\n\n{message}",
                parse_mode='Markdown'
            )
            successful += 1
        except Exception as e:
            logger.error(f"Ошибка отправки сообщения пользователю {uid}: {e}")
            failed += 1
    
    await update.message.reply_text(
        f"✅ *Рассылка завершена!*\n\n"
        f"*Успешно:* {successful} пользователей\n"
        f"*Не удалось:* {failed} пользователей",
        parse_mode='Markdown'
    )
    
    context.user_data["awaiting_broadcast"] = False

async def add_admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Добавить администратора по команде."""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("❌ У вас нет прав администратора!")
        return
    
    if len(context.args) != 1:
        await update.message.reply_text(
            "❌ *Использование:* /addadmin <user_id>\n"
            "Пример: /addadmin 123456789",
            parse_mode='Markdown'
        )
        return
    
    try:
        new_admin_id = int(context.args[0])
        # Нельзя добавлять себя повторно
        if new_admin_id == 1165068171:
            await update.message.reply_text("❌ *Вы уже владелец бота!*", parse_mode='Markdown')
            return
            
        admins_db.add(new_admin_id)
        save_admins()
        
        await update.message.reply_text(
            f"✅ *Пользователь {new_admin_id} добавлен в администраторы!*",
            parse_mode='Markdown'
        )
    except ValueError:
        await update.message.reply_text("❌ ID должен быть числом!")

async def remove_admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Удалить администратора."""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("❌ У вас нет прав администратора!")
        return
    
    # Не показываем владельца в списке для удаления
    admins_to_show = [aid for aid in admins_db if aid != 1165068171]
    
    if not admins_to_show:
        await update.message.reply_text("❌ Нет администраторов для удаления (кроме владельца)!")
        return
    
    response = "*🗑️ Выберите администратора для удаления:*\n\n"
    
    for i, admin_id in enumerate(admins_to_show, 1):
        username = users_db.get(admin_id, {}).get("username", "неизвестно")
        response += f"{i}. ID: {admin_id} (@{username})\n"
    
    response += "\nОтправьте номер администратора для удаления:"
    
    context.user_data["admin_list"] = admins_to_show
    context.user_data["awaiting_remove_admin"] = True
    
    await update.message.reply_text(response, parse_mode='Markdown')

async def process_remove_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка удаления администратора."""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        return
    
    try:
        index = int(update.message.text) - 1
        admin_list = context.user_data.get("admin_list", [])
        
        if 0 <= index < len(admin_list):
            removed_id = admin_list[index]
            
            # Нельзя удалить самого себя если вы владелец
            if removed_id == 1165068171:
                await update.message.reply_text(
                    "❌ *Вы не можете удалить владельца бота!*",
                    parse_mode='Markdown'
                )
                return
            
            admins_db.remove(removed_id)
            save_admins()
            
            username = users_db.get(removed_id, {}).get("username", "неизвестно")
            await update.message.reply_text(
                f"✅ *Администратор @{username} (ID: {removed_id}) удален!*",
                parse_mode='Markdown',
                reply_markup=get_admin_keyboard()
            )
        else:
            await update.message.reply_text("❌ Неверный номер администратора.")
    
    except ValueError:
        await update.message.reply_text("❌ Пожалуйста, отправьте номер цифрами.")
    
    context.user_data["awaiting_remove_admin"] = False

# ========== МОДУЛЬ ИЗМЕНЕНИЙ РАСПИСАНИЯ (ТОЛЬКО ДЛЯ АДМИНОВ) ==========
async def changes_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /changes для управления изменениями расписания."""
    user_id = update.effective_user.id
    
    # Только администраторы могут управлять изменениями
    if not is_admin(user_id):
        await update.message.reply_text(
            "❌ *У вас нет прав для управления изменениями!*\n\n"
            "Эта функция доступна только администраторам.",
            parse_mode='Markdown'
        )
        return
    
    await update.message.reply_text(
        "*🔄 Управление изменениями расписания*\n\n"
        "Вы можете:\n"
        "• Добавить замену пары\n"
        "• Отменить пару\n"
        "• Добавить дополнительную пару\n"
        "• Просмотреть все изменения\n"
        "• Удалить изменение\n\n"
        "Выберите действие:",
        parse_mode='Markdown',
        reply_markup=get_changes_keyboard()
    )

async def admin_changes_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Алиас для команды изменений из админ панели."""
    await changes_command(update, context)

# ========== ОПОВЕЩЕНИЯ ==========
async def notify_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /notify для настройки оповещений."""
    user_id = update.effective_user.id
    if user_id not in users_db:
        users_db[user_id] = {
            "notifications": False,
            "selected_group": None,
            "selected_teacher": None,
            "view_mode": "group",
            "awaiting_change": False,
            "change_data": {},
            "username": update.effective_user.username or "пользователь",
            "join_date": datetime.now().isoformat(),
            "role": "admin" if is_admin(user_id) else "user"
        }
    await update.message.reply_text(
        f"*⏰ Настройка оповещений*\n\n"
        f"Текущий статус: {'✅ Включены' if users_db[user_id]['notifications'] else '❌ Выключены'}\n\n"
        f"Выберите время уведомления:",
        parse_mode='Markdown',
        reply_markup=get_notify_keyboard()
    )

async def set_notification_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Установка времени уведомлений."""
    user_id = update.effective_user.id
    text = update.message.text
    time_mapping = {
        "🕘 За 30 минут": 30,
        "🕗 За 1 час": 60,
        "🕖 За 2 часа": 120
    }
    if text in time_mapping:
        minutes = time_mapping[text]
        if user_id not in users_db:
            users_db[user_id] = {
                "notifications": True,
                "time_before": minutes,
                "selected_group": None,
                "selected_teacher": None,
                "view_mode": "group",
                "awaiting_change": False,
                "change_data": {},
                "username": update.effective_user.username or "пользователь",
                "join_date": datetime.now().isoformat(),
                "role": "admin" if is_admin(user_id) else "user"
            }
        else:
            users_db[user_id]["notifications"] = True
            users_db[user_id]["time_before"] = minutes
        await update.message.reply_text(
            f"*✅ Оповещения настроены!*\n\n"
            f"Я буду напоминать за *{minutes} минут* до начала пары.\n"
            f"Теперь вы будете получать уведомления.",
            parse_mode='Markdown',
            reply_markup=get_main_keyboard(user_id)
        )
    elif text == "⏰ Тестовое уведомление":
        await test_notify_command(update, context)
    elif text == "🔕 Выключить":
        await stop_notify_command(update, context)
    elif text == "🔙 Назад":
        await update.message.reply_text(
            "*Главное меню:*",
            parse_mode='Markdown',
            reply_markup=get_main_keyboard(user_id)
        )
    else:
        await update.message.reply_text(
            "Пожалуйста, выберите время из предложенных вариантов.",
            reply_markup=get_notify_keyboard()
        )

async def test_notify_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /test_notify для тестового уведомления."""
    await update.message.reply_text(
        "🔔 *Тестовое уведомление!*\n\n"
        "Если вы настроили оповещения, вы будете получать такие уведомления перед парами.",
        parse_mode='Markdown'
    )

async def stop_notify_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /stop_notify для отключения оповещений."""
    user_id = update.effective_user.id
    if user_id in users_db:
        users_db[user_id]["notifications"] = False
    await update.message.reply_text(
        "*🔕 Оповещения отключены!*\n\n"
        "Вы больше не будете получать уведомления о парах.\n"
        "Чтобы включить снова, используйте меню 'Оповещения'.",
        parse_mode='Markdown',
        reply_markup=get_main_keyboard(user_id)
    )

# ========== ОБРАБОТКА ИНЛАЙН-КНОПОК ==========
async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нажатий на инлайн-кнопки."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data
    
    if user_id not in users_db:
        users_db[user_id] = {
            "notifications": False,
            "selected_group": None,
            "selected_teacher": None,
            "view_mode": "group",
            "awaiting_change": False,
            "change_data": {},
            "username": query.from_user.username or "пользователь",
            "join_date": datetime.now().isoformat(),
            "role": "admin" if is_admin(user_id) else "user"
        }
    
    if data.startswith("select_group:"):
        group_name = data.split(":")[1]
        users_db[user_id]["selected_group"] = group_name
        users_db[user_id]["view_mode"] = "group"
        await query.edit_message_text(
            f"✅ *Группа {group_name} выбрана!*\n\n"
            f"Теперь вы будете видеть расписание для этой группы.\n"
            f"Используйте кнопки 'Сегодня', 'Завтра' или 'Полное расписание'.",
            parse_mode='Markdown'
        )
        # Показываем расписание на сегодня
        await today_command_from_callback(query, group_name)
    
    elif data.startswith("select_teacher:"):
        teacher_name = data.split(":")[1]
        users_db[user_id]["selected_teacher"] = teacher_name
        users_db[user_id]["view_mode"] = "teacher"
        await query.edit_message_text(
            f"✅ *Преподаватель {teacher_name} выбран!*\n\n"
            f"Теперь вы будете видеть расписание для этого преподавателя.\n"
            f"Используйте кнопки 'Сегодня', 'Завтра' или 'Полное расписание'.",
            parse_mode='Markdown'
        )
        await send_teacher_schedule(query, teacher_name)
    
    elif data == "back_to_main":
        await query.edit_message_text("Возвращаемся в главное меню...", parse_mode='Markdown')
        await query.message.reply_text(
            "*Главное меню:*",
            parse_mode='Markdown',
            reply_markup=get_main_keyboard(user_id)
        )

async def today_command_from_callback(query, group_name):
    """Упрощенная версия today_command для использования из callback."""
    russian_day, lessons = get_day_schedule_for_group(group_name, 0)
    
    if not russian_day:
        await query.message.reply_text("Ошибка определения дня недели")
        return
    
    # Проверяем, есть ли изменения для этого дня
    changes = get_changes_for_day(group_name, russian_day)
    has_changes = len(changes) > 0
    
    if lessons:
        response = f"*📅 Расписание на сегодня для группы {group_name} ({russian_day})*"
        if has_changes:
            response += " ⚠️ *Есть изменения*\n\n"
        else:
            response += ":\n\n"
        
        for i, lesson in enumerate(lessons, 1):
            response += f"{i}. {lesson}\n"
        
        response += f"\n_Всего пар: {len(lessons)}_"
        
        if has_changes:
            response += "\n\n*Изменения:*"
            for change in changes:
                if change["type"] == "replacement":
                    response += f"\n🔄 Замена: {change.get('replacement', '')}"
                elif change["type"] == "cancelled":
                    response += f"\n❌ Отмена"
                elif change["type"] == "additional":
                    response += f"\n➕ Дополнительная пара"
    else:
        response = f"*🎉 Сегодня ({russian_day}) у группы {group_name} пар нет!*"
    
    await query.message.reply_text(response, parse_mode='Markdown')

async def send_teacher_schedule(query, teacher_name):
    """Отправить расписание на сегодня для преподавателя."""
    russian_day, lessons = get_day_schedule_for_teacher(teacher_name, 0)
    if lessons:
        response = f"*📅 Расписание на сегодня для преподавателя {teacher_name} ({russian_day}):*\n\n"
        for i, lesson in enumerate(lessons, 1):
            response += f"{i}. {lesson}\n"
        response += f"\n_Всего занятий: {len(lessons)}_"
    else:
        response = f"*🎉 Сегодня ({russian_day}) у преподавателя {teacher_name} занятий нет!*"
    await query.message.reply_text(response, parse_mode='Markdown')

# ========== ОБРАБОТКА ТЕКСТОВЫХ СООБЩЕНИЙ ==========
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка текстовых сообщений."""
    user_id = update.effective_user.id
    text = update.message.text
    
    # Проверяем, ожидается ли ввод для добавления администратора
    if context.user_data.get("awaiting_admin_id"):
        try:
            new_admin_id = int(text)
            # Нельзя добавлять себя повторно
            if new_admin_id == 1165068171:
                await update.message.reply_text("❌ *Вы уже владелец бота!*", parse_mode='Markdown')
            else:
                admins_db.add(new_admin_id)
                save_admins()
                await update.message.reply_text(
                    f"✅ *Пользователь {new_admin_id} добавлен в администраторы!*",
                    parse_mode='Markdown',
                    reply_markup=get_admin_keyboard()
                )
        except ValueError:
            await update.message.reply_text("❌ ID должен быть числом!")
        context.user_data["awaiting_admin_id"] = False
        return
    
    # Проверяем, ожидается ли ввод для удаления администратора
    if context.user_data.get("awaiting_remove_admin"):
        await process_remove_admin(update, context)
        return
    
    # Проверяем, ожидается ли рассылка
    if context.user_data.get("awaiting_broadcast"):
        await process_broadcast(update, context)
        return
    
    # Проверяем, является ли это выбором типа экспорта
    if context.user_data.get("export_type"):
        await process_export(update, context)
        context.user_data.pop("export_type", None)
        context.user_data.pop("export_name", None)
        return
    
    # Обработка основных команд
    if text == "📅 Сегодня":
        await today_command(update, context)
    elif text == "📆 Завтра":
        await tomorrow_command(update, context)
    elif text == "📋 Полное расписание":
        await full_command(update, context)
    elif text == "👥 Выбор группы":
        await group_command(update, context)
    elif text == "👨‍🏫 Выбор преподавателя":
        await teacher_command(update, context)
    elif text == "🔄 Изменения расписания":
        await changes_command(update, context)
    elif text == "📤 Экспорт в CSV":
        await export_command(update, context)
    elif text == "🔔 Оповещения":
        await notify_command(update, context)
    elif text == "❓ Помощь":
        await help_command(update, context)
    elif text == "⚙️ Админ панель":
        await admin_command(update, context)
    elif text in ["🕘 За 30 минут", "🕗 За 1 час", "🕖 За 2 часа", "⏰ Тестовое уведомление", "🔕 Выключить", "🔙 Назад"]:
        await set_notification_time(update, context)
    elif text == "👤 Управление пользователями":
        await manage_users_command(update, context)
    elif text == "📊 Статистика":
        await stats_command(update, context)
    elif text == "📢 Рассылка":
        await broadcast_command(update, context)
    elif text == "🔄 Управление изменениями":
        await admin_changes_command(update, context)
    elif text == "➕ Добавить админа":
        context.user_data["awaiting_admin_id"] = True
        await update.message.reply_text(
            "✍️ *Добавление администратора*\n\n"
            "Отправьте ID пользователя, которого хотите сделать администратором.\n"
            "Чтобы отменить, отправьте /cancel",
            parse_mode='Markdown'
        )
    elif text == "➖ Удалить админа":
        await remove_admin_command(update, context)
    elif text in ["📅 Экспорт на месяц", "📆 Экспорт на семестр", "📋 Экспорт полного расписания"]:
        # Это обрабатывается в process_export
        pass
    elif text == "🔙 Назад" or text == "🔙 В главное меню":
        await update.message.reply_text(
            "*Главное меню:*",
            parse_mode='Markdown',
            reply_markup=get_main_keyboard(user_id)
        )
    else:
        # Если это админ команда из админ панели
        if is_admin(user_id) and text in ["📝 Добавить изменение", "📋 Посмотреть изменения", "🗑️ Удалить изменение"]:
            await update.message.reply_text(
                "Эта функция находится в разработке. Скоро будет доступна!",
                reply_markup=get_changes_keyboard()
            )
        else:
            await update.message.reply_text(
                "🤔 *Я не понял ваш запрос.*\n\n"
                "Пожалуйста, используйте кнопки меню или команду /help",
                parse_mode='Markdown',
                reply_markup=get_main_keyboard(user_id)
            )

# ========== ДОПОЛНИТЕЛЬНЫЕ КОМАНДЫ ==========
async def force_owner_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда для принудительной проверки прав владельца."""
    user_id = update.effective_user.id
    
    if user_id == 1165068171:
        # Гарантируем права владельца
        admins_db.add(1165068171)
        save_admins()
        
        await update.message.reply_text(
            "👑 *Права владельца подтверждены!*\n\n"
            f"Ваш ID: {user_id}\n"
            f"Статус: Владелец бота\n"
            f"Права администратора: ✅ АКТИВНЫ\n\n"
            "Используйте /admin для доступа к админ-панели.",
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text(
            "❌ *Эта команда доступна только владельцу бота!*",
            parse_mode='Markdown'
        )

# ========== ОСНОВНАЯ ФУНКЦИЯ ==========
def main():
    """Запуск бота."""
    # Загружаем данные
    load_changes()
    load_admins()
    
    application = Application.builder().token(TOKEN).build()
    
    # Основные команды для всех пользователей
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("today", today_command))
    application.add_handler(CommandHandler("tomorrow", tomorrow_command))
    application.add_handler(CommandHandler("full", full_command))
    application.add_handler(CommandHandler("group", group_command))
    application.add_handler(CommandHandler("teacher", teacher_command))
    application.add_handler(CommandHandler("myinfo", myinfo_command))
    application.add_handler(CommandHandler("notify", notify_command))
    application.add_handler(CommandHandler("test_notify", test_notify_command))
    application.add_handler(CommandHandler("stop_notify", stop_notify_command))
    application.add_handler(CommandHandler("export", export_command))
    
    # Админ команды
    application.add_handler(CommandHandler("admin", admin_command))
    application.add_handler(CommandHandler("addadmin", add_admin_command))
    application.add_handler(CommandHandler("forceowner", force_owner_command))
    
    # Команды для изменений (только для админов)
    application.add_handler(CommandHandler("changes", changes_command))
    
    # Обработчики
    application.add_handler(CallbackQueryHandler(handle_callback_query))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    print("=" * 60)
    print("БОТ ДЛЯ РАСПИСАНИЯ УНИВЕРСИТЕТА")
    print("=" * 60)
    print(f"🤖 Токен бота: {TOKEN[:10]}...")
    print(f"👑 Владелец (админ): ID 1165068171")
    print(f"👥 Группы: {', '.join(all_groups)}")
    print(f"👨‍🏫 Преподаватели: {', '.join(all_teachers[:3])}...")
    print("=" * 60)
    print("\n📤 Экспорт в CSV доступен для ВСЕХ пользователей!")
    print("👑 Администратор - полный доступ ко всем функциям")
    print("👤 Обычный пользователь - просмотр расписания + экспорт в CSV")
    print("\n🚀 Бот запущен и готов к работе!")
    print("💡 Используйте /start для начала работы")
    print("👑 Используйте /forceowner для подтверждения прав владельца")
    print("⏰ Нажмите Ctrl+C для остановки бота")
    print("=" * 60)
    
    # Запуск бота
    try:
        application.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)
    except Exception as e:
        logger.error(f"Ошибка запуска бота: {e}")
        

if __name__ == '__main__':
    main()
    import traceback

def run_bot():
    """Функция с обработкой ошибок для автоматического перезапуска"""
    attempts = 0
    max_attempts = 5
    
    while attempts < max_attempts:
        try:
            print(f"Запуск бота... Попытка {attempts + 1}/{max_attempts}")
            main()  # Ваша основная функция
        except KeyboardInterrupt:
            print("\nБот остановлен пользователем")
            break
        except Exception as e:
            attempts += 1
            print(f"Ошибка: {e}")
            print(traceback.format_exc())
            
            if attempts < max_attempts:
                print(f"Перезапуск через 10 секунд...")
                import time
                time.sleep(10)
            else:
                print("Достигнут лимит попыток перезапуска")
                # Можно отправить уведомление администратору
                break

if __name__ == '__main__':
    run_bot()