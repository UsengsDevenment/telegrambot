import asyncio
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ChatPermissions
)
from aiogram.filters import Command
from aiogram.enums import ParseMode

BOT_TOKEN = "1234567890"
ADMIN_ID = 234567890

bot = None
dp = Dispatcher()
router = Router()


class Database:
    def __init__(self):
        self.global_admins = {ADMIN_ID}
        self.warns = {}
        self.rules = {}
        self.welcome = {}

db = Database()


def parse_duration(text: str) -> timedelta | None:
    if not text:
        return None
    text = text.lower().strip()
    try:
        if text.endswith(("m", "м")):
            return timedelta(minutes=int(text[:-1]))
        elif text.endswith(("h", "ч")):
            return timedelta(hours=int(text[:-1]))
        elif text.endswith(("d", "д")):
            return timedelta(days=int(text[:-1]))
        elif text.endswith(("w", "н")):
            return timedelta(weeks=int(text[:-1]))
        elif text.isdigit():
            return timedelta(minutes=int(text))
    except ValueError:
        pass
    return None


def format_duration(td: timedelta) -> str:
    total_seconds = int(td.total_seconds())
    if total_seconds < 3600:
        return f"{total_seconds // 60} мин"
    elif total_seconds < 86400:
        return f"{total_seconds // 3600} ч"
    else:
        return f"{total_seconds // 86400} д"


def format_user(user) -> str:
    if user.username:
        return f"{user.first_name} (@{user.username})"
    return f"{user.first_name} [ID: {user.id}]"


def get_warns_key(chat_id: int, user_id: int) -> str:
    return f"{chat_id}:{user_id}"


def get_warns(chat_id: int, user_id: int) -> int:
    return db.warns.get(get_warns_key(chat_id, user_id), 0)


def add_warn(chat_id: int, user_id: int) -> int:
    key = get_warns_key(chat_id, user_id)
    db.warns[key] = db.warns.get(key, 0) + 1
    return db.warns[key]


def remove_warn(chat_id: int, user_id: int) -> int:
    key = get_warns_key(chat_id, user_id)
    if key in db.warns and db.warns[key] > 0:
        db.warns[key] -= 1
    return db.warns.get(key, 0)


def clear_warns(chat_id: int, user_id: int):
    db.warns[get_warns_key(chat_id, user_id)] = 0


async def is_admin(chat_id: int, user_id: int) -> bool:
    if user_id in db.global_admins:
        return True
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        return member.status in ["creator", "administrator"]
    except:
        return False


async def can_restrict(chat_id: int, user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        return member.status not in ["creator", "administrator"]
    except:
        return True


async def get_target_user(message: Message, args: list):
    if message.reply_to_message:
        return message.reply_to_message.from_user, 1
    if len(args) < 2:
        return None, 0
    identifier = args[1].strip()
    if identifier.startswith("@"):
        identifier = identifier[1:]
    try:
        user_id = int(identifier)
        try:
            member = await bot.get_chat_member(message.chat.id, user_id)
            return member.user, 2
        except:
            return None, 0
    except ValueError:
        pass
    return None, 0


@router.message(Command("start"))
async def cmd_start(message: Message):
    if message.chat.type == "private":
        await message.answer(
            "👨‍💼 <b>Бот модерации чатов</b>\n\n"
            "Добавьте меня в чат и дайте права администратора.\n\n"
            "<b>Команды:</b>\n"
            "/ban @user причина время\n"
            "/mute @user причина время\n"
            "/warn @user причина\n"
            "/kick @user\n\n"
            "<b>Время:</b> 10m, 2h, 1d, 1w\n\n"
            "Можно отвечать на сообщение вместо @user",
            parse_mode=ParseMode.HTML
        )


@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.reply(
        "📋 <b>Команды модерации</b>\n\n"
        "<b>Баны:</b>\n"
        "/ban причина время - ответом на сообщение\n"
        "/ban @user причина время\n"
        "/ban ID причина время\n"
        "/unban @user или ID\n\n"
        "<b>Муты:</b>\n"
        "/mute причина время - ответом\n"
        "/mute @user причина время\n"
        "/unmute @user\n\n"
        "<b>Варны:</b>\n"
        "/warn причина - ответом\n"
        "/warn @user причина\n"
        "/unwarn @user\n"
        "/clearwarns @user\n"
        "/warns @user\n\n"
        "<b>Другое:</b>\n"
        "/kick - ответом или @user\n"
        "/info - ответом или @user\n\n"
        "<b>Время:</b>\n"
        "30m = 30 минут\n"
        "2h = 2 часа\n"
        "1d = 1 день\n"
        "1w = 1 неделя",
        parse_mode=ParseMode.HTML
    )


@router.message(Command("ban"))
async def cmd_ban(message: Message):
    if message.chat.type == "private":
        return await message.reply("❌ Команда работает только в чатах")
    if not await is_admin(message.chat.id, message.from_user.id):
        return await message.reply("⛔ Нужны права администратора")
    args = message.text.split()
    target_user, arg_offset = await get_target_user(message, args)
    if not target_user:
        return await message.reply(
            "❌ <b>Пользователь не найден</b>\n\n"
            "Использование:\n"
            "• Ответьте на сообщение: /ban причина время\n"
            "• Или: /ban @username причина время\n"
            "• Или: /ban ID причина время",
            parse_mode=ParseMode.HTML
        )
    if not await can_restrict(message.chat.id, target_user.id):
        return await message.reply("❌ Нельзя забанить администратора")
    reason = "Не указана"
    duration = None
    if arg_offset == 1:
        if len(args) >= 2:
            reason = args[1]
        if len(args) >= 3:
            duration = parse_duration(args[2])
    else:
        if len(args) >= 3:
            reason = args[2]
        if len(args) >= 4:
            duration = parse_duration(args[3])
    try:
        until_date = datetime.now() + duration if duration else None
        await bot.ban_chat_member(message.chat.id, target_user.id, until_date=until_date)
        duration_text = format_duration(duration) if duration else "навсегда"
        await message.reply(
            f"🚫 <b>Пользователь забанен</b>\n\n"
            f"👤 {format_user(target_user)}\n"
            f"📝 Причина: {reason}\n"
            f"⏱ Срок: {duration_text}",
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        await message.reply(f"❌ Ошибка: {e}")


@router.message(Command("unban"))
async def cmd_unban(message: Message):
    if message.chat.type == "private":
        return await message.reply("❌ Команда работает только в чатах")
    if not await is_admin(message.chat.id, message.from_user.id):
        return await message.reply("⛔ Нужны права администратора")
    args = message.text.split()
    if len(args) < 2:
        return await message.reply("❌ Использование: /unban @user или /unban ID")
    identifier = args[1].replace("@", "")
    try:
        user_id = int(identifier)
    except ValueError:
        return await message.reply("❌ Укажите ID пользователя числом")
    try:
        await bot.unban_chat_member(message.chat.id, user_id, only_if_banned=True)
        await message.reply(f"✅ Пользователь {user_id} разбанен")
    except Exception as e:
        await message.reply(f"❌ Ошибка: {e}")


@router.message(Command("mute"))
async def cmd_mute(message: Message):
    if message.chat.type == "private":
        return await message.reply("❌ Команда работает только в чатах")
    if not await is_admin(message.chat.id, message.from_user.id):
        return await message.reply("⛔ Нужны права администратора")
    args = message.text.split()
    target_user, arg_offset = await get_target_user(message, args)
    if not target_user:
        return await message.reply(
            "❌ <b>Пользователь не найден</b>\n\n"
            "Использование:\n"
            "• Ответьте на сообщение: /mute причина время\n"
            "• Или: /mute @username причина время\n"
            "• Или: /mute ID причина время",
            parse_mode=ParseMode.HTML
        )
    if not await can_restrict(message.chat.id, target_user.id):
        return await message.reply("❌ Нельзя замутить администратора")
    reason = "Не указана"
    duration = timedelta(hours=1)
    if arg_offset == 1:
        if len(args) >= 2:
            reason = args[1]
        if len(args) >= 3:
            parsed = parse_duration(args[2])
            if parsed:
                duration = parsed
    else:
        if len(args) >= 3:
            reason = args[2]
        if len(args) >= 4:
            parsed = parse_duration(args[3])
            if parsed:
                duration = parsed
    try:
        until_date = datetime.now() + duration
        permissions = ChatPermissions(
            can_send_messages=False,
            can_send_media_messages=False,
            can_send_other_messages=False,
            can_add_web_page_previews=False
        )
        await bot.restrict_chat_member(message.chat.id, target_user.id, permissions=permissions, until_date=until_date)
        await message.reply(
            f"🔇 <b>Пользователь замучен</b>\n\n"
            f"👤 {format_user(target_user)}\n"
            f"📝 Причина: {reason}\n"
            f"⏱ Срок: {format_duration(duration)}",
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        await message.reply(f"❌ Ошибка: {e}")


@router.message(Command("unmute"))
async def cmd_unmute(message: Message):
    if message.chat.type == "private":
        return await message.reply("❌ Команда работает только в чатах")
    if not await is_admin(message.chat.id, message.from_user.id):
        return await message.reply("⛔ Нужны права администратора")
    args = message.text.split()
    target_user, _ = await get_target_user(message, args)
    if not target_user:
        return await message.reply("❌ Ответьте на сообщение или укажите @user/ID")
    try:
        permissions = ChatPermissions(
            can_send_messages=True,
            can_send_media_messages=True,
            can_send_other_messages=True,
            can_add_web_page_previews=True,
            can_send_polls=True,
            can_invite_users=True
        )
        await bot.restrict_chat_member(message.chat.id, target_user.id, permissions=permissions)
        await message.reply(f"🔊 {format_user(target_user)} размучен", parse_mode=ParseMode.HTML)
    except Exception as e:
        await message.reply(f"❌ Ошибка: {e}")


@router.message(Command("warn"))
async def cmd_warn(message: Message):
    if message.chat.type == "private":
        return await message.reply("❌ Команда работает только в чатах")
    if not await is_admin(message.chat.id, message.from_user.id):
        return await message.reply("⛔ Нужны права администратора")
    args = message.text.split()
    target_user, arg_offset = await get_target_user(message, args)
    if not target_user:
        return await message.reply(
            "❌ <b>Пользователь не найден</b>\n\n"
            "Использование:\n"
            "• Ответьте на сообщение: /warn причина\n"
            "• Или: /warn @username причина",
            parse_mode=ParseMode.HTML
        )
    if not await can_restrict(message.chat.id, target_user.id):
        return await message.reply("❌ Нельзя дать варн администратору")
    reason = "Не указана"
    if arg_offset == 1 and len(args) >= 2:
        reason = " ".join(args[1:])
    elif arg_offset == 2 and len(args) >= 3:
        reason = " ".join(args[2:])
    warns = add_warn(message.chat.id, target_user.id)
    if warns >= 3:
        try:
            await bot.ban_chat_member(message.chat.id, target_user.id)
            clear_warns(message.chat.id, target_user.id)
            await message.reply(
                f"🚫 <b>Пользователь забанен</b>\n\n"
                f"👤 {format_user(target_user)}\n"
                f"📝 Причина: 3/3 предупреждений",
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            await message.reply(f"❌ Ошибка бана: {e}")
    else:
        await message.reply(
            f"⚠️ <b>Предупреждение</b>\n\n"
            f"👤 {format_user(target_user)}\n"
            f"📝 Причина: {reason}\n"
            f"⚠️ Варнов: {warns}/3",
            parse_mode=ParseMode.HTML
        )


@router.message(Command("unwarn"))
async def cmd_unwarn(message: Message):
    if message.chat.type == "private":
        return await message.reply("❌ Команда работает только в чатах")
    if not await is_admin(message.chat.id, message.from_user.id):
        return await message.reply("⛔ Нужны права администратора")
    args = message.text.split()
    target_user, _ = await get_target_user(message, args)
    if not target_user:
        return await message.reply("❌ Ответьте на сообщение или укажите @user/ID")
    warns = remove_warn(message.chat.id, target_user.id)
    await message.reply(
        f"✅ Варн снят\n\n👤 {format_user(target_user)}\n⚠️ Осталось: {warns}/3",
        parse_mode=ParseMode.HTML
    )


@router.message(Command("clearwarns"))
async def cmd_clearwarns(message: Message):
    if message.chat.type == "private":
        return await message.reply("❌ Команда работает только в чатах")
    if not await is_admin(message.chat.id, message.from_user.id):
        return await message.reply("⛔ Нужны права администратора")
    args = message.text.split()
    target_user, _ = await get_target_user(message, args)
    if not target_user:
        return await message.reply("❌ Ответьте на сообщение или укажите @user/ID")
    clear_warns(message.chat.id, target_user.id)
    await message.reply(f"✅ Все варны сняты с {format_user(target_user)}", parse_mode=ParseMode.HTML)


@router.message(Command("warns"))
async def cmd_warns(message: Message):
    if message.chat.type == "private":
        return await message.reply("❌ Команда работает только в чатах")
    args = message.text.split()
    target_user, _ = await get_target_user(message, args)
    if not target_user:
        target_user = message.from_user
    warns = get_warns(message.chat.id, target_user.id)
    await message.reply(f"⚠️ У {format_user(target_user)} варнов: {warns}/3", parse_mode=ParseMode.HTML)


@router.message(Command("kick"))
async def cmd_kick(message: Message):
    if message.chat.type == "private":
        return await message.reply("❌ Команда работает только в чатах")
    if not await is_admin(message.chat.id, message.from_user.id):
        return await message.reply("⛔ Нужны права администратора")
    args = message.text.split()
    target_user, _ = await get_target_user(message, args)
    if not target_user:
        return await message.reply("❌ Ответьте на сообщение или укажите @user/ID")
    if not await can_restrict(message.chat.id, target_user.id):
        return await message.reply("❌ Нельзя кикнуть администратора")
    try:
        await bot.ban_chat_member(message.chat.id, target_user.id)
        await bot.unban_chat_member(message.chat.id, target_user.id, only_if_banned=True)
        await message.reply(f"👢 {format_user(target_user)} кикнут", parse_mode=ParseMode.HTML)
    except Exception as e:
        await message.reply(f"❌ Ошибка: {e}")


@router.message(Command("info"))
async def cmd_info(message: Message):
    if message.chat.type == "private":
        return await message.reply("❌ Команда работает только в чатах")
    args = message.text.split()
    target_user, _ = await get_target_user(message, args)
    if not target_user:
        target_user = message.from_user
    try:
        member = await bot.get_chat_member(message.chat.id, target_user.id)
        status_map = {
            "creator": "👑 Создатель",
            "administrator": "👨‍💼 Админ",
            "member": "👤 Участник",
            "restricted": "🔇 Ограничен",
            "left": "🚪 Покинул",
            "kicked": "🚫 Забанен"
        }
        status = status_map.get(member.status, member.status)
        warns = get_warns(message.chat.id, target_user.id)
        username_text = f"@{target_user.username}" if target_user.username else "нет"
        await message.reply(
            f"👤 <b>Информация</b>\n\n"
            f"🆔 ID: <code>{target_user.id}</code>\n"
            f"📛 Имя: {target_user.first_name}\n"
            f"👤 Username: {username_text}\n"
            f"📊 Статус: {status}\n"
            f"⚠️ Варнов: {warns}/3",
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        await message.reply(f"❌ Ошибка: {e}")


@router.message(Command("setrules"))
async def cmd_setrules(message: Message):
    if message.chat.type == "private":
        return await message.reply("❌ Команда работает только в чатах")
    if not await is_admin(message.chat.id, message.from_user.id):
        return await message.reply("⛔ Нужны права администратора")
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        return await message.reply("❌ Использование: /setrules текст правил")
    db.rules[message.chat.id] = args[1]
    await message.reply("✅ Правила установлены")


@router.message(Command("rules"))
async def cmd_rules(message: Message):
    if message.chat.type == "private":
        return await message.reply("❌ Команда работает только в чатах")
    rules = db.rules.get(message.chat.id, "Правила не установлены")
    await message.reply(f"📜 <b>Правила чата</b>\n\n{rules}", parse_mode=ParseMode.HTML)


@router.message(Command("setwelcome"))
async def cmd_setwelcome(message: Message):
    if message.chat.type == "private":
        return await message.reply("❌ Команда работает только в чатах")
    if not await is_admin(message.chat.id, message.from_user.id):
        return await message.reply("⛔ Нужны права администратора")
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        return await message.reply("❌ Использование: /setwelcome текст\n\n{user} - имя\n{chat} - название чата")
    db.welcome[message.chat.id] = args[1]
    await message.reply("✅ Приветствие установлено")


@router.message(Command("delwelcome"))
async def cmd_delwelcome(message: Message):
    if message.chat.type == "private":
        return await message.reply("❌ Команда работает только в чатах")
    if not await is_admin(message.chat.id, message.from_user.id):
        return await message.reply("⛔ Нужны права администратора")
    db.welcome.pop(message.chat.id, None)
    await message.reply("✅ Приветствие удалено")


@router.message(F.new_chat_members)
async def on_new_member(message: Message):
    for user in message.new_chat_members:
        if user.id == (await bot.get_me()).id:
            await message.reply(
                "👋 <b>Привет! Я бот модерации.</b>\n\n"
                "Дайте мне права администратора.\n"
                "Команды: /help",
                parse_mode=ParseMode.HTML
            )
        else:
            welcome = db.welcome.get(message.chat.id)
            if welcome:
                text = welcome.replace("{user}", user.first_name).replace("{chat}", message.chat.title or "чат")
                await message.reply(text, parse_mode=ParseMode.HTML)


async def main():
    global bot
    bot = Bot(token=BOT_TOKEN)
    dp.include_router(router)
    print("Бот запускается....")
    while True:
        try:
            await bot.delete_webhook(drop_pending_updates=True)
            me = await bot.get_me()
            print(f"Бот @{me.username} запущен!")
            await dp.start_polling(bot)
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Error: {e}")
            await asyncio.sleep(10)
    await bot.session.close()


if __name__ == "__main__":

    asyncio.run(main())
