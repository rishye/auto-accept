import os
import logging
import json
import asyncio
from datetime import datetime
from pymongo import MongoClient
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    ChatJoinRequestHandler,
    CallbackQueryHandler,
    ContextTypes,
)

# ─── CONFIG ───────────────────────────────────────────
BOT_TOKEN = "8905275970:AAEo7yqdMpZ6g_yTJQ4comPVQZi_4VVcw54"
BOT_CREATOR_ID = 7763689060          # 🔴 YOUR Telegram User ID
BOT_USERNAME = "AutoReqAccept_2bot"    # Bot username without @
MONGO_URI = "mongodb+srv://saminsumesh02_db_user:<saminsumesh02_db_user@cluster0.ao0w9kz.mongodb.net/?appName=Cluster0"

# ─── LOGGING ──────────────────────────────────────────
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ─── MONGODB ──────────────────────────────────────────
client = MongoClient(MONGO_URI)
db = client["auto_acceptor_bot"]
users_collection = db["users"]
settings_collection = db["settings"]

def init_db():
    defaults = {
        "_id": "global",
        "welcome_message": "🎉 <b>Welcome {name}!</b>\n\nYour request has been approved! 🚀",
        "welcome_buttons": json.dumps([
            [{"text": "🎉 Get Started", "url": "https://t.me/yourchannel"}]
        ]),
        "broadcast_template": "📢 <b>Broadcast</b>\n\n{message}",
    }
    settings_collection.update_one(
        {"_id": "global"}, {"$setOnInsert": defaults}, upsert=True
    )

def get_setting(key, default=None):
    doc = settings_collection.find_one({"_id": "global"})
    return doc.get(key, default) if doc else default

def set_setting(key, value):
    settings_collection.update_one(
        {"_id": "global"}, {"$set": {key: value}}, upsert=True
    )

# ─── USER DB ──────────────────────────────────────────
def add_user(user_id, username, first_name, last_name, chat_id, channel_id=None, channel_name=None):
    users_collection.update_one(
        {"user_id": user_id},
        {"$set": {
            "user_id": user_id,
            "username": username or "",
            "first_name": first_name or "",
            "last_name": last_name or "",
            "chat_id": chat_id,
            "channel_id": channel_id,
            "channel_name": channel_name or "",
            "approved_at": datetime.now()
        }},
        upsert=True
    )

def get_all_users():
    return list(users_collection.find())

def get_user_count():
    return users_collection.count_documents({})

# ─── FORMATTER ────────────────────────────────────────
def format_message(template, user=None, chat=None, extra=None):
    text = template
    if user:
        name = user.first_name or "User"
        fullname = f"{user.first_name or ''} {user.last_name or ''}".strip()
        mention = f'<a href="tg://user?id={user.id}">{name}</a>'
        username = f"@{user.username}" if user.username else "No username"
        text = text.replace("{name}", name)
        text = text.replace("{fullname}", fullname)
        text = text.replace("{mention}", mention)
        text = text.replace("{username}", username)
        text = text.replace("{id}", str(user.id))
    if chat:
        text = text.replace("{chat}", chat.title or "Chat")
    if extra:
        text = text.replace("{message}", str(extra))
    text = text.replace("{count}", str(get_user_count()))
    return text

def build_keyboard(buttons_json, user=None):
    try:
        buttons_data = json.loads(buttons_json)
    except:
        return None
    keyboard = []
    for row in buttons_data:
        button_row = []
        for btn in row:
            text = btn.get("text", "Button")
            if user:
                text = text.replace("{name}", user.first_name or "User")
            if "url" in btn:
                button_row.append(InlineKeyboardButton(text, url=btn["url"]))
            elif "callback_data" in btn:
                button_row.append(InlineKeyboardButton(text, callback_data=btn["callback_data"]))
        keyboard.append(button_row)
    return InlineKeyboardMarkup(keyboard) if keyboard else None

def is_creator(user_id):
    return user_id == BOT_CREATOR_ID

# ─── HANDLERS ─────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    # 🔒 CREATOR gets admin panel
    if is_creator(user.id):
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📊 Stats", callback_data="admin_stats"),
             InlineKeyboardButton("👥 Users", callback_data="admin_users")],
            [InlineKeyboardButton("📝 Set Welcome", callback_data="admin_setwelcome"),
             InlineKeyboardButton("🔘 Set Buttons", callback_data="admin_setbuttons")],
            [InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast"),
             InlineKeyboardButton("👁 Preview", callback_data="admin_preview")]
        ])
        await update.message.reply_text(
            f"🔐 <b>Creator Admin Panel</b>\n\n"
            f"Welcome back, <b>{user.first_name}</b>!\n\n"
            f"👥 Total Users: <code>{get_user_count()}</code>\n\n"
            f"Available commands:\n"
            f"<code>/setwelcome /setbuttons /broadcast /stats /users /preview</code>",
            parse_mode="HTML",
            reply_markup=keyboard
        )
        return

    # 👤 REGULAR USERS — simple promo only
    promo_text = (
        f"👋 <b>Hello!</b>\n\n"
        f"Add <code>@{BOT_USERNAME}</code> to your channels or groups "
        f"to accept join requests automatically 😊\n\n"
        f"<i>Share And Support Us 😊</i>"
    )
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Add To Channel", url=f"https://t.me/{BOT_USERNAME}?startchannel=true")],
        [InlineKeyboardButton("📢 Updates Channel", url="https://t.me/+KvFO5_vTHnFjMzJl")]
    ])
    await update.message.reply_text(
        promo_text,
        parse_mode="HTML",
        reply_markup=keyboard,
        disable_web_page_preview=True
    )

async def chat_join_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    join_request = update.chat_join_request
    user = join_request.from_user
    chat = join_request.chat

    try:
        await context.bot.approve_chat_join_request(chat.id, user.id)
        logger.info(f"Approved {user.id} to {chat.title}")

        add_user(
            user_id=user.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
            chat_id=user.id,
            channel_id=chat.id,
            channel_name=chat.title
        )

        # Send welcome DM
        try:
            template = get_setting('welcome_message')
            buttons_json = get_setting('welcome_buttons')
            text = format_message(template, user=user, chat=chat)
            reply_markup = build_keyboard(buttons_json, user=user)

            await context.bot.send_message(
                chat_id=user.id,
                text=text,
                parse_mode="HTML",
                reply_markup=reply_markup,
                disable_web_page_preview=True
            )
        except Exception as e:
            logger.warning(f"Could not send DM to {user.id}: {e}")

    except Exception as e:
        logger.error(f"Error approving {user.id}: {e}")

# ─── CREATOR ONLY COMMANDS ────────────────────────────

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_creator(update.effective_user.id):
        return
    count = get_user_count()
    await update.message.reply_text(
        f"📊 <b>Statistics</b>\n\n"
        f"👥 Total Users: <code>{count}</code>",
        parse_mode="HTML"
    )

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_creator(update.effective_user.id):
        return

    if not context.args:
        await update.message.reply_text(
            "❌ Usage: <code>/broadcast Your message here</code>",
            parse_mode="HTML"
        )
        return

    raw_message = " ".join(context.args)
    users = get_all_users()

    if not users:
        await update.message.reply_text("📭 No users yet.")
        return

    sent = 0
    failed = 0
    status_msg = await update.message.reply_text(f"⏳ Broadcasting... 0/{len(users)}")

    for user_doc in users:
        try:
            class FakeUser:
                def __init__(self, id, first_name, username, last_name):
                    self.id = id
                    self.first_name = first_name
                    self.username = username
                    self.last_name = last_name

            fake_user = FakeUser(
                user_doc["user_id"],
                user_doc.get("first_name", ""),
                user_doc.get("username", ""),
                user_doc.get("last_name", "")
            )
            template = get_setting('broadcast_template')
            text = format_message(template, user=fake_user, extra=raw_message)

            await context.bot.send_message(
                chat_id=user_doc["chat_id"],
                text=text,
                parse_mode="HTML",
                disable_web_page_preview=False
            )
            sent += 1
        except Exception as e:
            failed += 1
            logger.warning(f"Failed to send to {user_doc['user_id']}: {e}")

        if (sent + failed) % 10 == 0:
            try:
                await status_msg.edit_text(
                    f"⏳ Broadcasting... {sent + failed}/{len(users)}\n"
                    f"✅ Sent: {sent} | ❌ Failed: {failed}"
                )
            except:
                pass
        await asyncio.sleep(0.05)

    await status_msg.edit_text(
        f"✅ <b>Broadcast Complete!</b>\n\n"
        f"📤 Sent: <code>{sent}</code>\n"
        f"❌ Failed: <code>{failed}</code>\n"
        f"👥 Total: <code>{len(users)}</code>",
        parse_mode="HTML"
    )

async def setwelcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_creator(update.effective_user.id):
        return

    if not context.args:
        current = get_setting('welcome_message')
        await update.message.reply_text(
            f"📝 <b>Current Welcome Message:</b>\n\n"
            f"<code>{current}</code>\n\n"
            f"Set new: <code>/setwelcome Your message</code>\n\n"
            f"<b>Placeholders:</b> <code>{{name}}</code> <code>{{mention}}</code> <code>{{username}}</code> <code>{{id}}</code> <code>{{chat}}</code>",
            parse_mode="HTML"
        )
        return

    new_msg = " ".join(context.args)
    set_setting('welcome_message', new_msg)
    await update.message.reply_text("✅ Welcome message updated!")

async def setbuttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_creator(update.effective_user.id):
        return

    if not context.args:
        current = get_setting('welcome_buttons')
        await update.message.reply_text(
            f"🔘 <b>Current Buttons JSON:</b>\n\n"
            f"<pre>{current}</pre>\n\n"
            f"Set new: <code>/setbuttons [JSON]</code>\n\n"
            f"<b>Example:</b>\n"
            f'<code>/setbuttons [[{{"text":"Channel","url":"https://t.me/xxx"}}]]</code>',
            parse_mode="HTML"
        )
        return

    try:
        new_buttons = " ".join(context.args)
        json.loads(new_buttons)
        set_setting('welcome_buttons', new_buttons)
        await update.message.reply_text("✅ Welcome buttons updated!")
    except json.JSONDecodeError:
        await update.message.reply_text("❌ Invalid JSON!")

async def preview(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_creator(update.effective_user.id):
        return

    user = update.effective_user
    welcome_template = get_setting('welcome_message')
    welcome_text = format_message(welcome_template, user=user, chat=update.effective_chat)
    welcome_buttons = build_keyboard(get_setting('welcome_buttons'), user=user)

    await update.message.reply_text("👇 <b>Preview:</b>", parse_mode="HTML")
    await update.message.reply_text(
        welcome_text,
        parse_mode="HTML",
        reply_markup=welcome_buttons
    )

async def users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_creator(update.effective_user.id):
        return

    users_list = list(users_collection.find().sort("approved_at", -1).limit(15))

    if not users_list:
        await update.message.reply_text("📭 No users yet.")
        return

    text = "👥 <b>Recent Users</b>\n\n"
    for doc in users_list:
        name = doc.get("first_name") or doc.get("username") or "Unknown"
        text += f"• <code>{doc['user_id']}</code> - {name}\n"

    await update.message.reply_text(text, parse_mode="HTML")

# ─── CALLBACKS ────────────────────────────────────────

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user = query.from_user

    if not is_creator(user.id):
        return

    if data == "admin_stats":
        await query.edit_message_text(
            f"📊 <b>Statistics</b>\n\n"
            f"👥 Total Users: <code>{get_user_count()}</code>",
            parse_mode="HTML"
        )
    elif data == "admin_users":
        users_list = list(users_collection.find().sort("approved_at", -1).limit(10))
        text = "👥 <b>Recent Users:</b>\n\n"
        for doc in users_list:
            name = doc.get("first_name") or doc.get("username") or "Unknown"
            text += f"• <code>{doc['user_id']}</code> - {name}\n"
        await query.edit_message_text(text, parse_mode="HTML")
    elif data == "admin_setwelcome":
        await query.edit_message_text(
            "📝 Use <code>/setwelcome Your message here</code>",
            parse_mode="HTML"
        )
    elif data == "admin_setbuttons":
        await query.edit_message_text(
            "🔘 Use <code>/setbuttons [JSON]</code>",
            parse_mode="HTML"
        )
    elif data == "admin_broadcast":
        await query.edit_message_text(
            "📢 Use <code>/broadcast Your message here</code>",
            parse_mode="HTML"
        )
    elif data == "admin_preview":
        welcome_template = get_setting('welcome_message')
        welcome_text = format_message(welcome_template, user=user, chat=query.message.chat)
        welcome_buttons = build_keyboard(get_setting('welcome_buttons'), user=user)
        await query.edit_message_text(
            "👇 <b>Preview:</b>\n\n" + welcome_text,
            parse_mode="HTML",
            reply_markup=welcome_buttons
        )

# ─── MAIN ─────────────────────────────────────────────

def main():
    init_db()
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("stats", stats))
    application.add_handler(CommandHandler("broadcast", broadcast))
    application.add_handler(CommandHandler("setwelcome", setwelcome))
    application.add_handler(CommandHandler("setbuttons", setbuttons))
    application.add_handler(CommandHandler("preview", preview))
    application.add_handler(CommandHandler("users", users))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(ChatJoinRequestHandler(chat_join_request))

    logger.info("🤖 Bot started!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
