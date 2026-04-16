# =============================================================================
# Telemt bot
# Bot for managing Telemt proxies via Telegram
# =============================================================================
import asyncio
import logging
import json
import secrets
import os
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import aiohttp

load_dotenv()

# ================
# Settings
# ================


# Telemt API address. If the bot is in Docker on the same host, you may need
# http://host.docker.internal:9091/v1 or http://telemt:9091/v1
TELEMT_API_BASE = os.getenv("TELEMT_API_BASE", "http://127.0.0.1:9091/v1")

# API authorization token. Must match the auth_header in telemt.toml.
# If telemt.toml has auth_header = "", leave the line empty.
AUTH_HEADER = os.getenv("TELEMT_AUTH_HEADER", "")

#Bot token from @BotFather
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN не задан в переменных окружения!")


# Telegram IDs of administrators (numbers). The bot will only respond to them.
# You can find out your ID through the bot @userinfobot
ADMIN_IDS_RAW = os.getenv("BOT_ADMIN_IDS", "")
ADMIN_IDS = {int(x.strip()) for x in ADMIN_IDS_RAW.split(",") if x.strip()}

if not ADMIN_IDS:
    raise ValueError("❌ BOT_ADMIN_IDS не задан в переменных окружения!")

# Logging settings
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

# Initializing the bot and dispatcher
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# =============================================================================
# STATE MACHINE (FSM) for user creation
# =============================================================================

class CreateUser(StatesGroup):
    """
    Состояния для пошагового мастера создания пользователя:
    1. username — ожидание имени пользователя
    2. secret — ожидание секрета (или пропуска)
    """
    username = State()
    secret = State()

def is_admin(user_id: int) -> bool:
    """
    Проверяет, есть ли пользователь в списке администраторов.
    Возвращает True, если user_id есть в ADMIN_IDS.
    """
    return user_id in ADMIN_IDS

async def telemt_request(method: str, path: str, json_data: dict = None) -> dict:
    """
    Универсальная функция для HTTP-запросов к API Telemt.

    Args:
        method: HTTP метод (GET, POST, DELETE, PATCH)
        path: Путь эндпоинта (например, "/users" или "/health")
        json_data: Данные для тела запроса (для POST/PATCH)

    Returns:
        Словарь с ответом от API (распарсенный JSON)
    """
    # Forming headings
    headers = {"Content-Type": "application/json"}

    # Add an authorization token if it is specified in the settings
    if AUTH_HEADER:
        headers["Authorization"] = AUTH_HEADER

    # Collect the full URL
    url = f"{TELEMT_API_BASE}{path}"

    try:
        # Create an HTTP session and execute the request
        async with aiohttp.ClientSession() as session:
            async with session.request(method, url, json=json_data, headers=headers) as resp:
                # Trying to parse the JSON response
                try:
                    return await resp.json()
                except:
                    # If not JSON, return raw text and status
                    return {"raw": await resp.text(), "status": resp.status}
    except Exception as e:
        # Catching network errors (timeout, connection, etc.)
        logging.error(f"API request failed: {e}")
        return {"ok": False, "error": {"message": f"Network error: {e}"}}

# =============================================================================
# BOT COMMANDS
# =============================================================================

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    """
    Команда /start — показывает приветственное меню.
    """
    # Checking access rights
    if not is_admin(message.from_user.id):
        logging.warning(f"Unauthorized access attempt from user {message.from_user.id}")
        return await message.answer("🔒 Доступ запрещён. Вы не в списке администраторов.")

    # Generate a welcome message with HTML markup
    await message.answer(
        "👋 <b>Telemt Bot</b>\n\n"
        "Бот для управления прокси Telemt.\n\n"
        "<b>Команды:</b>\n"
        "/status — Статус прокси (аптайм, подключения)\n"
        "/users — Список пользователей (топ-10)\n"
        "/create — Создать нового пользователя\n"
        "/info @username — Информация о пользователе\n"
        "/delete @username — Удалить пользователя\n"
        "/help — Справка",
        parse_mode="HTML"
    )

@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    """
    Команда /help — подробная справка.
    """
    if not is_admin(message.from_user.id):
        return await message.answer("🔒 Доступ запрещён.")

    await message.answer(
        "📖 <b>Справка по боту</b>\n\n"
        "<b>Мониторинг:</b>\n"
        "• /status — Проверка здоровья и статистики\n\n"
        "<b>Пользователи:</b>\n"
        "• /users — Показать первых 10 пользователей\n"
        "• /info @name — Детали по конкретному юзеру\n"
        "• /create — Пошаговое создание юзера\n"
        "• /delete @name — Удаление юзера\n\n"
        "<b>Безопасность:</b>\n"
        "Бот отвечает только пользователям из ADMIN_IDS.",
        parse_mode="HTML"
    )

@dp.message(Command("status"))
async def cmd_status(message: types.Message):
    """
    Команда /status — проверяет здоровье API и общую статистику.
    """
    if not is_admin(message.from_user.id):
        return await message.answer("🔒 Доступ запрещён.")

    # Request health and statistics summary
    health = await telemt_request("GET", "/health")
    summary = await telemt_request("GET", "/stats/summary")

    # Check that both requests are successful
    if health.get("ok") and summary.get("ok"):
        data = summary["data"]

        # Format uptime from seconds to hours
        uptime_hours = data.get('uptime_seconds', 0) / 3600

        text = (
            "✅ <b>Telemt Status</b>\n\n"
            f"🟢 Статус: {health['data'].get('status', 'unknown')}\n"
            f"⏱ Аптайм: {uptime_hours:.1f} ч\n"
            f"🔗 Всего подключений: {data.get('connections_total', 0)}\n"
            f"❌ Ошибок: {data.get('connections_bad_total', 0)}\n"
            f"👥 Пользователей: {data.get('configured_users', 0)}"
        )

        # Add the "Update" button
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Обновить", callback_data="refresh_status")]
        ])

        await message.answer(text, parse_mode="HTML", reply_markup=keyboard)
    else:
        # Showing an API error
        await message.answer(f"❌ Ошибка API:\n\n{health}\n\n{summary}")

@dp.callback_query(F.data == "refresh_status")
async def cb_refresh_status(callback: types.CallbackQuery):
    """
    Обработчик нажатия кнопки "Обновить" в статусе.
    """
    # Checking administrator rights
    if not is_admin(callback.from_user.id):
        await callback.answer("🔒 Доступ запрещён.", show_alert=True)
        return

    # Remove the loading indicator
    await callback.answer("Обновляю...")

    # Requesting data directly
    health = await telemt_request("GET", "/health")
    summary = await telemt_request("GET", "/stats/summary")

    if health.get("ok") and summary.get("ok"):
        data = summary["data"]
        uptime_hours = data.get('uptime_seconds', 0) / 3600

        text = (
            "✅ <b>Telemt Status</b>\n\n"
            f"🟢 Статус: {health['data'].get('status', 'unknown')}\n"
            f"⏱ Аптайм: {uptime_hours:.1f} ч\n"
            f"🔗 Всего подключений: {data.get('connections_total', 0)}\n"
            f"❌ Ошибок: {data.get('connections_bad_total', 0)}\n"
            f"👥 Пользователей: {data.get('configured_users', 0)}"
        )

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Обновить", callback_data="refresh_status")]
        ])

        # Editing an existing message instead of sending a new one
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
    else:
        await callback.message.edit_text(f"❌ Ошибка API:\n\n{health}\n\n{summary}")

@dp.message(Command("users"))
async def cmd_users(message: types.Message):
    """
    Команда /users — показывает список пользователей (первые 10).
    """
    if not is_admin(message.from_user.id):
        return await message.answer("🔒 Доступ запрещён.")

    # Request a list of all users
    resp = await telemt_request("GET", "/users")

    if resp.get("ok"):
        users = resp["data"]

        if not users:
            return await message.answer("📭 Пользователей нет.")

        text = "👥 <b>Пользователи</b>\n\n"

        # We show a maximum of 10 to avoid spam
        for u in users[:10]:
            username = u.get('username', 'unknown')
            links = u.get('links', {})
            tls_links = links.get('tls', [])
            connections = u.get('current_connections', 0)
            traffic_gb = u.get('total_octets', 0) / 1e9

            text += f"• <code>{username}</code>\n"
            text += f"  🔗 {tls_links[0] if tls_links else 'нет ссылок'}\n"
            text += f"  📊 {connections} подкл., {traffic_gb:.2f} GB\n\n"

        if len(users) > 10:
            text += f"... и ещё {len(users) - 10} пользователей"

        await message.answer(text, parse_mode="HTML")
    else:
        await message.answer(f"❌ Ошибка: {resp}")

@dp.message(Command("create"))
async def cmd_create_start(message: types.Message, state: FSMContext):
    """
    Команда /create — начинает мастер создания пользователя.
    """
    if not is_admin(message.from_user.id):
        return await message.answer("🔒 Доступ запрещён.")

    await message.answer(
        "📝 <b>Создание пользователя</b>\n\n"
        "Введите имя пользователя (латиница, цифры, _ . -):\n"
        "<i>Длина: 1-64 символа</i>",
        parse_mode="HTML"
    )
    await state.set_state(CreateUser.username)

@dp.message(CreateUser.username)
async def create_username(message: types.Message, state: FSMContext):
    """
    Шаг 1: Получаем и валидируем имя пользователя.
    """
    username = message.text.strip()

    # Validation according to Telemt API rules
    if not (1 <= len(username) <= 64):
        return await message.answer("❌ Длина имени должна быть от 1 до 64 символов. Попробуйте ещё раз:")

    if not all(c.isalnum() or c in "_.-" for c in username):
        return await message.answer("❌ Разрешены только латиница, цифры и символы _ . -\nПопробуйте ещё раз:")

    # Save the name to the state and go to step 2
    await state.update_data(username=username)
    await message.answer(
        "🔑 Введите секрет (32 hex-символа) или нажмите /skip для автогенерации:\n"
        "<i>Пример: a1b2c3d4e5f6789012345678abcdef90</i>",
        parse_mode="HTML"
    )
    await state.set_state(CreateUser.secret)

@dp.message(CreateUser.secret, F.text == "/skip")
async def create_secret_skip(message: types.Message, state: FSMContext):
    """
    Шаг 2 (вариант А): Пропуск ввода секрета → автогенерация.
    """
    data = await state.get_data()
    await create_user(message, data["username"], None, state)

@dp.message(CreateUser.secret)
async def create_secret(message: types.Message, state: FSMContext):
    """
    Шаг 2 (вариант Б): Пользователь ввёл свой секрет.
    """
    secret = message.text.strip()

    # Validation: exactly 32 hex characters
    if len(secret) != 32 or not all(c in "0123456789abcdefABCDEF" for c in secret):
        return await message.answer(
            "❌ Секрет должен быть ровно 32 hex-символа (0-9, a-f).\n"
            "Попробуйте ещё раз или нажмите /skip:"
        )

    data = await state.get_data()
    await create_user(message, data["username"], secret, state)

async def create_user(message: types.Message, username: str, secret: str, state: FSMContext):
    """
    Внутренняя функция: отправляет запрос на создание пользователя в API.
    """
    # Forming the request body
    payload = {"username": username}
    if secret:
        payload["secret"] = secret

    # Sending a POST request
    resp = await telemt_request("POST", "/users", json_data=payload)

    if resp.get("ok"):
        user = resp["data"]["user"]
        links = user.get("links", {}).get("tls", [])

        text = (
            f"✅ Пользователь <code>{username}</code> создан!\n\n"
            f"🔑 Секрет: <code>{resp['data']['secret']}</code>\n\n"
            f"🔗 Ссылка для подключения:\n"
            f"<code>{links[0] if links else 'нет ссылок'}</code>",
        )
        await message.answer(text, parse_mode="HTML")
    else:
        error = resp.get("error", {})
        await message.answer(f"❌ Ошибка создания: {error.get('message', resp)}")

    # Reset the FSM state
    await state.clear()

@dp.message(Command("info"))
async def cmd_info(message: types.Message):
    """
    Команда /info @username — показывает детальную информацию о пользователе.
    """
    if not is_admin(message.from_user.id):
        return await message.answer("🔒 Доступ запрещён.")

    # Parse @username from the command text
    parts = message.text.split()
    if len(parts) < 2:
        return await message.answer("📋 Использование: /info @username")

    username = parts[1].lstrip("@")
    resp = await telemt_request("GET", f"/users/{username}")

    if resp.get("ok"):
        u = resp["data"]

        text = f"👤 <b>{u['username']}</b>\n\n"
        text += f"🔗 Подключений: {u.get('current_connections', 0)}\n"
        text += f"🌐 Уникальных IP: {u.get('active_unique_ips', 0)}\n"
        text += f"📦 Трафик: {u.get('total_octets', 0) / 1e9:.2f} GB\n"

        # Optional fields (may be absent)
        if u.get("expiration_rfc3339"):
            text += f"⏰ Истекает: {u['expiration_rfc3339']}\n"
        if u.get("data_quota_bytes"):
            text += f"💾 Квота: {u['data_quota_bytes'] / 1e9:.2f} GB"

        await message.answer(text, parse_mode="HTML")
    else:
        await message.answer(f"❌ Пользователь не найден или ошибка API: {resp}")

@dp.message(Command("delete"))
async def cmd_delete(message: types.Message):
    """
    Команда /delete @username — удаляет пользователя.
    """
    if not is_admin(message.from_user.id):
        return await message.answer("🔒 Доступ запрещён.")

    parts = message.text.split()
    if len(parts) < 2:
        return await message.answer("📋 Использование: /delete @username")

    username = parts[1].lstrip("@")

    # Request confirmation (optional, can be removed for speed)
    resp = await telemt_request("DELETE", f"/users/{username}")

    if resp.get("ok"):
        await message.answer(f"✅ Пользователь <code>{username}</code> удалён", parse_mode="HTML")
    else:
        error = resp.get("error", {})
        await message.answer(f"❌ Ошибка удаления: {error.get('message', resp)}")

# =============================================================================
# LAUNCH THE BOT
# =============================================================================

async def main():
    """
    Основная функция запуска. Запускает polling (опрос) сервера Telegram.
    """
    logging.info("Bot starting...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Bot stopped by user")
    finally:
        # Correct closing of sessions when stopped
        #await bot.session.close()
        pass
