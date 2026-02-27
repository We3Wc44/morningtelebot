import os
import json
import asyncio
import logging
import random
from datetime import datetime, time
import pytz
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, KeyboardButton, WebAppInfo
)
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes, ConversationHandler
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import aiosqlite

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
WEBAPP_URL = os.getenv("WEBAPP_URL", "https://your-webapp.onrender.com")
DB_PATH = os.getenv("DB_PATH", "bot_data.db")

# Conversation states
LANG, NAME, TIME_SETUP, TONE_SETUP, DONE = range(5)

# ─── Messages ────────────────────────────────────────────────────────────────

MESSAGES = {
    "uk": {
        "morning_messages": [
            "🌸 Доброго ранку, {name}! Сьогодні буде неймовірний день — усміхнися світу!",
            "✨ {name}, ти просто сяєш! Сьогодні всі будуть в захваті від тебе 💫",
            "🌺 Привіт, {name}! Новий день — нові можливості. Ти впораєшся з усім!",
            "🦋 Доброго ранку! {name}, твоя краса та доброта роблять світ кращим 🌟",
            "🌷 {name}, встань і сяй! Цей день створений спеціально для тебе 💖",
            "🌈 Привіт, {name}! Ти сильна, красива і здатна на все. Вперед!",
            "🌻 Доброго ранку, {name}! Посміхнись — твоя усмішка освітлює кімнату ☀️",
            "💝 {name}, ти — диво! Сьогодні чудові речі чекають на тебе 🎀",
            "🌙➡️☀️ {name}, новий ранок — новий шанс бути ще кращою версією себе!",
            "🍀 Доброго ранку! {name}, сьогодні удача на твоєму боці 🌟",
            "🎀 {name}, ти неймовірна! Дозволь собі сяяти сьогодні 💎",
            "🌸 Привіт, {name}! Твоє серце повне любові — і це робить тебе прекрасною 💗",
            "⭐ {name}, ти зірка! Не забувай про це сьогодні та завжди ✨",
            "🌺 Доброго ранку, {name}! Обійми себе — ти це заслужила 🤗",
            "💫 {name}, сьогодні буде саме той день, коли все складеться ідеально!",
        ],
        "motivational": [
            "🏆 {name}, ти сильніша, ніж думаєш! Сьогодні покажи всім на що здатна!",
            "💪 Привіт, {name}! Кожен новий день — це твоя перемога. Вперед!",
            "🎯 {name}, ти маєш всі інструменти для успіху. Сьогодні твій день!",
        ],
        "gentle": [
            "🫂 {name}, піклуйся про себе сьогодні. Ти цього варта 💕",
            "🌿 Доброго ранку, {name}! Дихай глибше, рухайся повільніше, живи повніше 🍃",
            "☕ {name}, почни день з чашки кави та доброї думки про себе 💛",
        ],
        "start": "🌸 *Привіт! Я — твій ранковий помічник* 🌸\n\nЯ буду надсилати тобі теплі та надихаючі повідомлення кожного ранку!\n\nСпершу — кілька питань для налаштування 💫\n\n*Оберіть мову:*",
        "ask_name": "✨ Як тебе звати, красуне?",
        "ask_time": "⏰ *О котрій годині надсилати ранкове повідомлення?*\n\nНапиши у форматі `ГГ:ХХ` (наприклад `07:30`)\n\n_(Час за твоїм часовим поясом)_",
        "ask_timezone": "🌍 *Обери свій часовий пояс:*",
        "ask_tone": "💝 *Який стиль повідомлень тобі до душі?*",
        "tone_cheery": "🎉 Веселий та енергійний",
        "tone_gentle": "🌿 Ніжний та спокійний",
        "tone_motivational": "💪 Мотивуючий та надихаючий",
        "tone_mix": "🎲 Різноманітний (мікс)",
        "setup_done": "🎀 *Налаштування завершено!*\n\nЯ буду надсилати тобі повідомлення щоранку о *{time}* ⏰\n\nПам'ятай: ти неймовірна! 💖\n\n_Натисни /settings щоб змінити налаштування_",
        "settings_menu": "⚙️ *Налаштування*\n\nТут ти можеш змінити свої уподобання:",
        "btn_change_time": "⏰ Змінити час",
        "btn_change_tone": "💝 Змінити стиль",
        "btn_change_name": "✏️ Змінити ім'я",
        "btn_change_lang": "🌐 Змінити мову",
        "btn_test": "📨 Тестове повідомлення",
        "btn_webapp": "🌸 Відкрити додаток",
        "btn_pause": "⏸ Пауза",
        "btn_resume": "▶️ Продовжити",
        "paused": "⏸ Повідомлення призупинено. Напиши /settings щоб увімкнути знову.",
        "resumed": "▶️ Чудово! Я знову буду надсилати тобі ранкові повідомлення 🌸",
        "time_updated": "✅ Час оновлено! Тепер повідомлення о {time} ⏰",
        "invalid_time": "❌ Неправильний формат. Спробуй ще раз (наприклад: 07:30)",
        "name_updated": "✅ Оновлено! Буду звертатись до тебе: *{name}* 💖",
    },
    "ru": {
        "morning_messages": [
            "🌸 Доброе утро, {name}! Сегодня будет невероятный день — улыбнись миру!",
            "✨ {name}, ты просто сияешь! Сегодня все будут в восторге от тебя 💫",
            "🌺 Привет, {name}! Новый день — новые возможности. Ты справишься со всем!",
            "🦋 Доброе утро! {name}, твоя красота и доброта делают мир лучше 🌟",
            "🌷 {name}, вставай и сияй! Этот день создан специально для тебя 💖",
            "🌈 Привет, {name}! Ты сильная, красивая и способная на всё. Вперёд!",
            "🌻 Доброе утро, {name}! Улыбнись — твоя улыбка освещает комнату ☀️",
            "💝 {name}, ты — чудо! Сегодня замечательные вещи ждут тебя 🎀",
            "🌙➡️☀️ {name}, новое утро — новый шанс стать ещё лучшей версией себя!",
            "🍀 Доброе утро! {name}, сегодня удача на твоей стороне 🌟",
            "🎀 {name}, ты невероятная! Позволь себе сиять сегодня 💎",
            "🌸 Привет, {name}! Твоё сердце полно любви — и это делает тебя прекрасной 💗",
            "⭐ {name}, ты звезда! Не забывай об этом сегодня и всегда ✨",
            "🌺 Доброе утро, {name}! Обними себя — ты это заслужила 🤗",
            "💫 {name}, сегодня будет именно тот день, когда всё сложится идеально!",
        ],
        "motivational": [
            "🏆 {name}, ты сильнее, чем думаешь! Сегодня покажи всем на что способна!",
            "💪 Привет, {name}! Каждый новый день — это твоя победа. Вперёд!",
            "🎯 {name}, у тебя есть все инструменты для успеха. Сегодня твой день!",
        ],
        "gentle": [
            "🫂 {name}, заботься о себе сегодня. Ты этого достойна 💕",
            "🌿 Доброе утро, {name}! Дыши глубже, двигайся медленнее, живи полнее 🍃",
            "☕ {name}, начни день с чашки кофе и доброй мысли о себе 💛",
        ],
        "start": "🌸 *Привет! Я — твой утренний помощник* 🌸\n\nЯ буду присылать тебе тёплые и вдохновляющие сообщения каждое утро!\n\nСначала — несколько вопросов для настройки 💫\n\n*Выберите язык:*",
        "ask_name": "✨ Как тебя зовут, красавица?",
        "ask_time": "⏰ *В какое время присылать утреннее сообщение?*\n\nНапиши в формате `ЧЧ:ММ` (например `07:30`)\n\n_(Время по твоему часовому поясу)_",
        "ask_timezone": "🌍 *Выбери свой часовой пояс:*",
        "ask_tone": "💝 *Какой стиль сообщений тебе по душе?*",
        "tone_cheery": "🎉 Весёлый и энергичный",
        "tone_gentle": "🌿 Нежный и спокойный",
        "tone_motivational": "💪 Мотивирующий и вдохновляющий",
        "tone_mix": "🎲 Разнообразный (микс)",
        "setup_done": "🎀 *Настройка завершена!*\n\nЯ буду присылать тебе сообщения каждое утро в *{time}* ⏰\n\nПомни: ты невероятная! 💖\n\n_Нажми /settings чтобы изменить настройки_",
        "settings_menu": "⚙️ *Настройки*\n\nЗдесь ты можешь изменить свои предпочтения:",
        "btn_change_time": "⏰ Изменить время",
        "btn_change_tone": "💝 Изменить стиль",
        "btn_change_name": "✏️ Изменить имя",
        "btn_change_lang": "🌐 Изменить язык",
        "btn_test": "📨 Тестовое сообщение",
        "btn_webapp": "🌸 Открыть приложение",
        "btn_pause": "⏸ Пауза",
        "btn_resume": "▶️ Продолжить",
        "paused": "⏸ Сообщения приостановлены. Напиши /settings чтобы включить снова.",
        "resumed": "▶️ Отлично! Я снова буду присылать тебе утренние сообщения 🌸",
        "time_updated": "✅ Время обновлено! Теперь сообщения в {time} ⏰",
        "invalid_time": "❌ Неправильный формат. Попробуй ещё раз (например: 07:30)",
        "name_updated": "✅ Обновлено! Буду обращаться к тебе: *{name}* 💖",
    }
}

TIMEZONES = {
    "🇺🇦 Київ (UTC+2/+3)": "Europe/Kiev",
    "🇷🇺 Москва (UTC+3)": "Europe/Moscow",
    "🌍 Берлін (UTC+1/+2)": "Europe/Berlin",
    "🌍 Лондон (UTC+0/+1)": "Europe/London",
    "🌍 Нью-Йорк (UTC-5/-4)": "America/New_York",
    "🌏 Дубай (UTC+4)": "Asia/Dubai",
    "🌏 Варшава (UTC+1/+2)": "Europe/Warsaw",
}

# ─── Database ─────────────────────────────────────────────────────────────────

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                name TEXT,
                lang TEXT DEFAULT 'uk',
                send_hour INTEGER DEFAULT 8,
                send_minute INTEGER DEFAULT 0,
                timezone TEXT DEFAULT 'Europe/Kiev',
                tone TEXT DEFAULT 'mix',
                paused INTEGER DEFAULT 0,
                created_at TEXT
            )
        """)
        await db.commit()

async def get_user(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE user_id=?", (user_id,)) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None

async def save_user(user_id: int, **kwargs):
    user = await get_user(user_id)
    if user:
        sets = ", ".join(f"{k}=?" for k in kwargs)
        vals = list(kwargs.values()) + [user_id]
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(f"UPDATE users SET {sets} WHERE user_id=?", vals)
            await db.commit()
    else:
        kwargs["user_id"] = user_id
        kwargs.setdefault("created_at", datetime.utcnow().isoformat())
        cols = ", ".join(kwargs.keys())
        placeholders = ", ".join("?" * len(kwargs))
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(f"INSERT INTO users ({cols}) VALUES ({placeholders})", list(kwargs.values()))
            await db.commit()

async def get_all_active_users():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE paused=0 AND name IS NOT NULL") as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]

# ─── Message Generation ───────────────────────────────────────────────────────

def get_morning_message(user: dict) -> str:
    lang = user.get("lang", "uk")
    tone = user.get("tone", "mix")
    name = user.get("name", "")
    msgs = MESSAGES[lang]

    if tone == "mix":
        pool = msgs["morning_messages"] + msgs["motivational"] + msgs["gentle"]
    elif tone == "motivational":
        pool = msgs["motivational"] + msgs["morning_messages"]
    elif tone == "gentle":
        pool = msgs["gentle"] + msgs["morning_messages"]
    else:
        pool = msgs["morning_messages"]

    return random.choice(pool).format(name=name)

# ─── Scheduler ───────────────────────────────────────────────────────────────

scheduler = AsyncIOScheduler()
_app = None

async def send_morning_messages():
    users = await get_all_active_users()
    now_utc = datetime.utcnow()
    for user in users:
        try:
            tz = pytz.timezone(user.get("timezone", "Europe/Kiev"))
            now_local = datetime.now(tz)
            if now_local.hour == user["send_hour"] and now_local.minute == user["send_minute"]:
                msg = get_morning_message(user)
                await _app.bot.send_message(
                    chat_id=user["user_id"],
                    text=msg,
                    parse_mode="Markdown"
                )
        except Exception as e:
            logger.error(f"Failed to send to {user['user_id']}: {e}")

# ─── Handlers ─────────────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    existing = await get_user(user_id)

    if existing and existing.get("name"):
        lang = existing.get("lang", "uk")
        msgs = MESSAGES[lang]
        kb = [
            [InlineKeyboardButton(msgs["btn_change_time"], callback_data="set_time"),
             InlineKeyboardButton(msgs["btn_change_tone"], callback_data="set_tone")],
            [InlineKeyboardButton(msgs["btn_change_name"], callback_data="set_name"),
             InlineKeyboardButton(msgs["btn_change_lang"], callback_data="set_lang")],
            [InlineKeyboardButton(msgs["btn_test"], callback_data="test_msg")],
            [InlineKeyboardButton(msgs["btn_webapp"], web_app=WebAppInfo(url=WEBAPP_URL))],
        ]
        paused = existing.get("paused", 0)
        pause_btn = msgs["btn_resume"] if paused else msgs["btn_pause"]
        kb.append([InlineKeyboardButton(pause_btn, callback_data="toggle_pause")])

        await update.message.reply_text(
            msgs["settings_menu"],
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(kb)
        )
        return ConversationHandler.END

    # New user — start onboarding
    await save_user(user_id, lang="uk")
    kb = [
        [InlineKeyboardButton("🇺🇦 Українська", callback_data="lang_uk"),
         InlineKeyboardButton("🇷🇺 Русский", callback_data="lang_ru")]
    ]
    await update.message.reply_text(
        MESSAGES["uk"]["start"],
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(kb)
    )
    return LANG

async def lang_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = "uk" if query.data == "lang_uk" else "ru"
    user_id = query.from_user.id
    await save_user(user_id, lang=lang)
    context.user_data["lang"] = lang
    msgs = MESSAGES[lang]
    await query.edit_message_text(msgs["ask_name"], parse_mode="Markdown")
    return NAME

async def name_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    user_id = update.effective_user.id
    await save_user(user_id, name=name)
    context.user_data["name"] = name
    lang = context.user_data.get("lang", "uk")
    msgs = MESSAGES[lang]

    # Ask timezone
    kb = [[InlineKeyboardButton(label, callback_data=f"tz_{tz}")]
          for label, tz in TIMEZONES.items()]
    await update.message.reply_text(
        msgs["ask_timezone"],
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(kb)
    )
    return TIME_SETUP

async def timezone_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    tz = query.data.replace("tz_", "")
    user_id = query.from_user.id
    await save_user(user_id, timezone=tz)
    context.user_data["timezone"] = tz
    lang = context.user_data.get("lang", "uk")
    msgs = MESSAGES[lang]
    await query.edit_message_text(msgs["ask_time"], parse_mode="Markdown")
    return TIME_SETUP

async def time_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    lang = context.user_data.get("lang", "uk")
    msgs = MESSAGES[lang]
    try:
        t = datetime.strptime(text, "%H:%M")
    except ValueError:
        await update.message.reply_text(msgs["invalid_time"])
        return TIME_SETUP

    user_id = update.effective_user.id
    await save_user(user_id, send_hour=t.hour, send_minute=t.minute)
    context.user_data["time"] = text

    # Ask tone
    kb = [
        [InlineKeyboardButton(msgs["tone_cheery"], callback_data="tone_cheery")],
        [InlineKeyboardButton(msgs["tone_gentle"], callback_data="tone_gentle")],
        [InlineKeyboardButton(msgs["tone_motivational"], callback_data="tone_motivational")],
        [InlineKeyboardButton(msgs["tone_mix"], callback_data="tone_mix")],
    ]
    await update.message.reply_text(msgs["ask_tone"], parse_mode="Markdown",
                                    reply_markup=InlineKeyboardMarkup(kb))
    return TONE_SETUP

async def tone_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    tone = query.data.replace("tone_", "")
    user_id = query.from_user.id
    await save_user(user_id, tone=tone)
    lang = context.user_data.get("lang", "uk")
    msgs = MESSAGES[lang]
    send_time = context.user_data.get("time", "08:00")
    await query.edit_message_text(
        msgs["setup_done"].format(time=send_time),
        parse_mode="Markdown"
    )
    return ConversationHandler.END

async def settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = await get_user(user_id)
    if not user:
        await start(update, context)
        return
    lang = user.get("lang", "uk")
    msgs = MESSAGES[lang]
    paused = user.get("paused", 0)
    pause_btn = msgs["btn_resume"] if paused else msgs["btn_pause"]
    kb = [
        [InlineKeyboardButton(msgs["btn_change_time"], callback_data="set_time"),
         InlineKeyboardButton(msgs["btn_change_tone"], callback_data="set_tone")],
        [InlineKeyboardButton(msgs["btn_change_name"], callback_data="set_name"),
         InlineKeyboardButton(msgs["btn_change_lang"], callback_data="set_lang")],
        [InlineKeyboardButton(msgs["btn_test"], callback_data="test_msg")],
        [InlineKeyboardButton(msgs["btn_webapp"], web_app=WebAppInfo(url=WEBAPP_URL))],
        [InlineKeyboardButton(pause_btn, callback_data="toggle_pause")],
    ]
    time_str = f"{user['send_hour']:02d}:{user['send_minute']:02d}"
    status = "⏸ ПАУЗА" if paused else "✅ Активний"
    text = (
        f"{msgs['settings_menu']}\n\n"
        f"👤 Ім'я: *{user.get('name', '?')}*\n"
        f"⏰ Час: *{time_str}*\n"
        f"🌍 Timezone: *{user.get('timezone', '?')}*\n"
        f"💝 Стиль: *{user.get('tone', 'mix')}*\n"
        f"📊 Статус: {status}"
    )
    await update.message.reply_text(text, parse_mode="Markdown",
                                    reply_markup=InlineKeyboardMarkup(kb))

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user = await get_user(user_id)
    if not user:
        return
    lang = user.get("lang", "uk")
    msgs = MESSAGES[lang]
    data = query.data

    if data == "test_msg":
        msg = get_morning_message(user)
        await query.message.reply_text(msg, parse_mode="Markdown")

    elif data == "toggle_pause":
        new_val = 0 if user.get("paused") else 1
        await save_user(user_id, paused=new_val)
        text = msgs["paused"] if new_val else msgs["resumed"]
        await query.message.reply_text(text, parse_mode="Markdown")

    elif data == "set_time":
        await query.message.reply_text(msgs["ask_time"], parse_mode="Markdown")
        context.user_data["awaiting"] = "time"

    elif data == "set_name":
        await query.message.reply_text(msgs["ask_name"], parse_mode="Markdown")
        context.user_data["awaiting"] = "name"

    elif data == "set_lang":
        kb = [
            [InlineKeyboardButton("🇺🇦 Українська", callback_data="lang_uk"),
             InlineKeyboardButton("🇷🇺 Русский", callback_data="lang_ru")]
        ]
        await query.message.reply_text("🌐", reply_markup=InlineKeyboardMarkup(kb))

    elif data == "set_tone":
        kb = [
            [InlineKeyboardButton(msgs["tone_cheery"], callback_data="tone_update_cheery")],
            [InlineKeyboardButton(msgs["tone_gentle"], callback_data="tone_update_gentle")],
            [InlineKeyboardButton(msgs["tone_motivational"], callback_data="tone_update_motivational")],
            [InlineKeyboardButton(msgs["tone_mix"], callback_data="tone_update_mix")],
        ]
        await query.message.reply_text(msgs["ask_tone"], parse_mode="Markdown",
                                       reply_markup=InlineKeyboardMarkup(kb))

    elif data.startswith("tone_update_"):
        tone = data.replace("tone_update_", "")
        await save_user(user_id, tone=tone)
        await query.message.reply_text("✅ Стиль оновлено! 💝", parse_mode="Markdown")

    elif data.startswith("lang_"):
        lang_new = data.replace("lang_", "")
        await save_user(user_id, lang=lang_new)
        await query.message.reply_text("✅ Мову змінено! 🌐")

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    awaiting = context.user_data.get("awaiting")
    if not awaiting:
        return
    user_id = update.effective_user.id
    user = await get_user(user_id)
    lang = user.get("lang", "uk") if user else "uk"
    msgs = MESSAGES[lang]
    text = update.message.text.strip()

    if awaiting == "time":
        try:
            t = datetime.strptime(text, "%H:%M")
            await save_user(user_id, send_hour=t.hour, send_minute=t.minute)
            await update.message.reply_text(msgs["time_updated"].format(time=text), parse_mode="Markdown")
            context.user_data.pop("awaiting")
        except ValueError:
            await update.message.reply_text(msgs["invalid_time"])

    elif awaiting == "name":
        await save_user(user_id, name=text)
        await update.message.reply_text(msgs["name_updated"].format(name=text), parse_mode="Markdown")
        context.user_data.pop("awaiting")

# ─── Main ─────────────────────────────────────────────────────────────────────

async def post_init(application):
    global _app
    _app = application
    await init_db()
    scheduler.add_job(send_morning_messages, CronTrigger(minute="*"))
    scheduler.start()
    logger.info("Bot started, scheduler running")

def main():
    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            LANG: [CallbackQueryHandler(lang_chosen, pattern="^lang_")],
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, name_received)],
            TIME_SETUP: [
                CallbackQueryHandler(timezone_chosen, pattern="^tz_"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, time_received),
            ],
            TONE_SETUP: [CallbackQueryHandler(tone_chosen, pattern="^tone_")],
        },
        fallbacks=[CommandHandler("start", start)],
        allow_reentry=True,
    )

    app.add_handler(conv)
    app.add_handler(CommandHandler("settings", settings))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
