import discord
from discord.ext import commands, tasks
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

# =========================
# НАСТРОЙКИ
# =========================

import os
TOKEN = os.getenv("TOKEN")

TIMEZONE = ZoneInfo("Europe/Moscow")
NOTIFY_CHANNEL_ID = None

EVENT_DESCRIPTIONS = {
    "Ги Пати": "Сбор на гильдейскую пати. Подтягиваемся!.",
    "Ги Арена": "Время выйти на гильдийскую арену.",
    "Breaking Army": "Активность Breaking Army начинается. Запасаемся открывашками и идём кошмарить боссов"
}

# Monday=0, Tuesday=1, Wednesday=2, Thursday=3, Friday=4, Saturday=5, Sunday=6
SCHEDULE = {
    0: [("Ги Пати", time(19, 0))],  # ПН
    1: [("Ги Пати", time(19, 0)), ("Breaking Army", time(19, 0))],  # ВТ
    2: [("Ги Пати", time(19, 0)), ("Ги Арена", time(19, 0))],  # СР
    3: [("Ги Пати", time(19, 0))],  # ЧТ
    4: [("Ги Пати", time(17, 0)), ("Breaking Army", time(19, 0))],  # ПТ
    5: [("Ги Пати", time(17, 0)), ("Ги Арена", time(17, 0))],  # СБ
    6: [("Ги Пати", time(17, 0))],  # ВС
}

sent_notifications = set()

# =========================
# ИНТЕНТЫ И БОТ
# =========================

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# =========================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# =========================

def get_now():
    return datetime.now(TIMEZONE)

def get_today_events(now: datetime):
    weekday = now.weekday()
    return SCHEDULE.get(weekday, [])

def format_event_message(event_name: str, event_time: time, mode: str) -> str:
    description = EVENT_DESCRIPTIONS.get(event_name, "Описание не указано.")
    event_time_str = event_time.strftime("%H:%M")

    if mode == "30min":
        title = f"@everyone ⏰ Через 30 минут начнётся **{event_name}**!"
    else:
        title = f"@everyone 🚨 Уже начинается **{event_name}**!"

    return (
        f"{title}\n"
        f"**Время:** {event_time_str}\n"
        f"**Описание:** {description}"
    )

async def send_notification(channel: discord.TextChannel, event_name: str, event_time: time, mode: str):
    message = format_event_message(event_name, event_time, mode)
    await channel.send(message, allowed_mentions=discord.AllowedMentions(everyone=True))

# =========================
# СОБЫТИЯ
# =========================

@bot.event
async def on_ready():
    print(f"Бот запущен как {bot.user}")
    if not check_schedule_loop.is_running():
        check_schedule_loop.start()

# =========================
# КОМАНДЫ
# =========================

@bot.command()
@commands.has_permissions(administrator=True)
async def setchannel(ctx):
    global NOTIFY_CHANNEL_ID
    NOTIFY_CHANNEL_ID = ctx.channel.id
    await ctx.send(f"✅ Канал для уведомлений установлен: {ctx.channel.mention}")

@bot.command()
async def schedule(ctx):
    text = (
        "**Текущее расписание:**\n"
        "• Ги Пати: ПН-ЧТ — 19:00; ПТ-ВС — 17:00\n"
        "• Ги Арена: СР — 19:00; СБ — 17:00\n"
        "• Breaking Army: ВТ — 19:00; ПТ — 19:00"
    )
    await ctx.send(text)

@bot.command()
@commands.has_permissions(administrator=True)
async def test30(ctx):
    await ctx.send(
        "@everyone ⏰ Через 30 минут начнётся **Тестовая активность**!\n"
        "**Время:** 19:00\n"
        "**Описание:** Это тестовое уведомление.",
        allowed_mentions=discord.AllowedMentions(everyone=True)
    )

@bot.command()
@commands.has_permissions(administrator=True)
async def testnow(ctx):
    await ctx.send(
        "@everyone 🚨 Уже начинается **Тестовая активность**!\n"
        "**Время:** 19:00\n"
        "**Описание:** Это тестовое уведомление.",
        allowed_mentions=discord.AllowedMentions(everyone=True)
    )

# =========================
# ФОНОВАЯ ПРОВЕРКА
# =========================

@tasks.loop(seconds=30)
async def check_schedule_loop():
    global NOTIFY_CHANNEL_ID

    if NOTIFY_CHANNEL_ID is None:
        return

    now = get_now()
    channel = bot.get_channel(NOTIFY_CHANNEL_ID)

    if channel is None:
        return

    today_events = get_today_events(now)

    for event_name, event_time in today_events:
        event_datetime = datetime.combine(now.date(), event_time, tzinfo=TIMEZONE)
        notify_30 = event_datetime - timedelta(minutes=30)

        key_30 = (now.date().isoformat(), event_name, "30min")
        key_now = (now.date().isoformat(), event_name, "start")

        if (
            now.year == notify_30.year and
            now.month == notify_30.month and
            now.day == notify_30.day and
            now.hour == notify_30.hour and
            now.minute == notify_30.minute and
            key_30 not in sent_notifications
        ):
            await send_notification(channel, event_name, event_time, "30min")
            sent_notifications.add(key_30)

        if (
            now.year == event_datetime.year and
            now.month == event_datetime.month and
            now.day == event_datetime.day and
            now.hour == event_datetime.hour and
            now.minute == event_datetime.minute and
            key_now not in sent_notifications
        ):
            await send_notification(channel, event_name, event_time, "start")
            sent_notifications.add(key_now)

    cleanup_old_notifications(now)

def cleanup_old_notifications(now: datetime):
    old_keys = set()

    for item in sent_notifications:
        date_str, event_name, mode = item
        item_date = datetime.fromisoformat(date_str).date()
        if item_date < now.date() - timedelta(days=2):
            old_keys.add(item)

    sent_notifications.difference_update(old_keys)

@check_schedule_loop.before_loop
async def before_check_schedule_loop():
    await bot.wait_until_ready()

bot.run(TOKEN)

