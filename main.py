import asyncio
import json
import os
from telegram import (
    Update, InputMediaPhoto, InputMediaVideo, InputMediaDocument, Message,
    ReplyKeyboardMarkup, KeyboardButton
)
from telegram.error import RetryAfter, TelegramError
from telegram.ext import (
    ApplicationBuilder, MessageHandler, filters, ContextTypes,
    CommandHandler, ConversationHandler
)
from telegram.ext import TypeHandler
import re
from deep_translator import GoogleTranslator
from telegram.constants import ParseMode

# ---------------- MULTI-USER SETTINGS (NEW) ----------------
SETTINGS_FILE = "user_settings.json"

def load_user_settings():
    if not os.path.exists(SETTINGS_FILE):
        return {}
    with open(SETTINGS_FILE, "r") as f:
        return json.load(f)

def save_user_settings(settings):
    with open(SETTINGS_FILE, "w") as f:
        json.dump(settings, f, indent=2)

def get_settings(user_id):
    settings = load_user_settings()
    return settings.get(str(user_id), {
        "src": None,
        "dst": None,
        "lang": "en",
        "username": "",
        "active": True,
    })


def update_settings(user_id, **kwargs):
    settings = load_user_settings()
    user_id = str(user_id)
    if user_id not in settings:
        settings[user_id] = {
            "src": None, "dst": None, "lang": "en", "username": "", "active": True
        }
    settings[user_id].update(kwargs)
    save_user_settings(settings)
    print(f"Updated settings for user {user_id}: {settings[user_id]}")

# --------------- MENU AND COMMANDS (NEW) -------------------

MENU = [
    [KeyboardButton("Set Source Channel"), KeyboardButton("Set Destination Channel")],
    [KeyboardButton("Set Language"), KeyboardButton("Set Username")],
    [KeyboardButton("Start Forwarding"), KeyboardButton("Stop Forwarding")],
    [KeyboardButton("Help")],
]

def get_menu():
    return ReplyKeyboardMarkup(MENU, resize_keyboard=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Welcome to the Telegram Auto-Forwarder Bot!\n\n"
        "Use the menu below to configure your forwarding settings.\n"
        "Press 'Help' for instructions.",
        reply_markup=get_menu()
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "ℹ️ *How to use this bot:*\n\n"
        "1. *Set Source Channel*: Enter the channel/group ID you want to forward from (must be public or you must add the bot as admin).\n"
        "2. *Set Destination Channel*: Enter the channel/group ID you want to forward to (must be public or you must add the bot as admin).\n"
        "3. *Set Language*: Choose a language code for translation (e.g., 'en', 'ar', 'fr').\n"
        "4. *Set Username*: Enter your preferred username for replacements.\n"
        "5. After setting up, add this bot as admin in both channels/groups.\n\n"
        "*All your settings are private and used only for your messages!*",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=get_menu()
    )

# --- Conversation steps for setting options ---
AWAIT_SRC, AWAIT_DST, AWAIT_LANG, AWAIT_USER = range(4)

async def menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id

    if text.lower() == "stop forwarding":
        update_settings(user_id, active=False)
        await update.message.reply_text(
            "⛔️ Forwarding is now *DISABLED* for you. Use 'Start Forwarding' to resume.",
            parse_mode=ParseMode.MARKDOWN, reply_markup=get_menu()
        )
        print(f"User {user_id} set active to False")
        return ConversationHandler.END

    elif text.lower() == "start forwarding":
        update_settings(user_id, active=True)
        await update.message.reply_text(
            "✅ Forwarding is now *ENABLED* for you!",
            parse_mode=ParseMode.MARKDOWN, reply_markup=get_menu()
        )
        print(f"User {user_id} set active to True")
        return ConversationHandler.END
    if text == "Set Source Channel":
        await update.message.reply_text("Please send the source channel/group ID (must be numeric, e.g. -1001234567890):")
        return AWAIT_SRC
    elif text == "Set Destination Channel":
        await update.message.reply_text("Please send the destination channel/group ID (must be numeric, e.g. -1001234567890):")
        return AWAIT_DST
    elif text == "Set Language":
        await update.message.reply_text("Please send the target language code (e.g. 'en', 'ar', 'fr', 'ru'):")
        return AWAIT_LANG
    elif text == "Set Username":
        await update.message.reply_text("Please send the username you want to use for replacements (e.g. @yourusername):")
        return AWAIT_USER
    elif text == "Help":
        return await help_command(update, context)
    else:
        await update.message.reply_text("Unknown command. Use the menu.")
        return ConversationHandler.END

async def set_src(update: Update, context: ContextTypes.DEFAULT_TYPE):
    val = update.message.text.strip()
    user_id = update.effective_user.id
    if not val.startswith("-100") or not val[1:].isdigit():
        await update.message.reply_text("❌ Invalid channel/group ID. Please try again.")
        return AWAIT_SRC
    update_settings(user_id, src=int(val))
    await update.message.reply_text(f"✅ Source channel set to `{val}`.", parse_mode=ParseMode.MARKDOWN, reply_markup=get_menu())
    return ConversationHandler.END

async def set_dst(update: Update, context: ContextTypes.DEFAULT_TYPE):
    val = update.message.text.strip()
    user_id = update.effective_user.id
    if not val.startswith("-100") or not val[1:].isdigit():
        await update.message.reply_text("❌ Invalid channel/group ID. Please try again.")
        return AWAIT_DST
    update_settings(user_id, dst=int(val))
    await update.message.reply_text(f"✅ Destination channel set to `{val}`.", parse_mode=ParseMode.MARKDOWN, reply_markup=get_menu())
    return ConversationHandler.END

async def set_lang(update: Update, context: ContextTypes.DEFAULT_TYPE):
    val = update.message.text.strip()
    user_id = update.effective_user.id
    if not re.match(r"^[a-z]{2,}$", val):
        await update.message.reply_text("❌ Invalid language code. Please use codes like 'en', 'ar', 'fr', etc.")
        return AWAIT_LANG
    update_settings(user_id, lang=val)
    await update.message.reply_text(f"✅ Language set to `{val}`.", parse_mode=ParseMode.MARKDOWN, reply_markup=get_menu())
    return ConversationHandler.END

async def set_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    val = update.message.text.strip()
    user_id = update.effective_user.id
    if not val.startswith("@") or len(val) < 5:
        await update.message.reply_text("❌ Invalid username. Must start with @ and be at least 5 characters.")
        return AWAIT_USER
    update_settings(user_id, username=val)
    await update.message.reply_text(f"✅ Username set to `{val}`.", parse_mode=ParseMode.MARKDOWN, reply_markup=get_menu())
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Operation cancelled.", reply_markup=get_menu())
    return ConversationHandler.END

# ------------------- FORWARDING LOGIC (YOUR CODE) -------------------

def translate_preserving_usernames(text: str, dest: str = "ar") -> str:
    if not text:
        return text
    parts = re.split(r'(@[a-zA-Z0-9_]{4,})', text)
    out = []
    for part in parts:
        if part.startswith('@') and len(part) > 4:
            out.append(part)
        else:
            try:
                out.append(GoogleTranslator(source='auto', target=dest).translate(part) if part.strip() else part)
            except Exception as e:
                print(f"Translation error: {e}")
                out.append(part)
    return ''.join(out)

# ------------- These will be dynamically fetched per user -----------

media_queues = {}  # (user_id, group_id): list
scheduled = set()  # set of (user_id, group_id)
msg_id_map = {}

def is_true_forward(msg):
    return msg.forward_origin is not None

async def safe_send(coro, *args, **kwargs):
    try:
        # Increase the timeout for large media
        return await asyncio.wait_for(coro(*args, **kwargs), timeout=60)
    except asyncio.TimeoutError:
        print("Telegram API timed out! Consider retrying or skipping this item.")
        return None
    except RetryAfter as e:
        await asyncio.sleep(e.retry_after + 1)
        return await coro(*args, **kwargs)
    except TelegramError as e:
        print(f"TelegramError: {e}")


def break_telegram_mention(match):
    at_name = match.group(0)
    return "@\u200b" + at_name[1:]

def link_replacer(match, username="@username"):
    url = match.group(0)
    # Do NOT replace blockchain/tronscan URLs
    if (
        re.match(r'https?://(www\.)?tronscan', url) or
        re.match(r'https?://(www\.)?blockchain', url) or
        re.match(r'www\.blockchain', url) or
        re.match(r'blockchain', url)
    ):
        return url
    return username



def clean_text(text, username="@destinationusername"):
    if not text:
        return text

    dest_no_at = username.lstrip("@")
    html_link = f'<a href="https://t.me/{dest_no_at}">{username}</a>'

    # Remove t.me/@1234xxxx links (where username starts with 4 digits)
    text = re.sub(
        r'(https?://)?(www\.)?t\.me/@?(\d{4}[a-zA-Z0-9_]+)',
        lambda m: f"@{m.group(3)}",
        text,
        flags=re.IGNORECASE
    )

    # Replace t.me/username (where username does NOT start with 4 digits) with HTML link
    text = re.sub(
        r'(https?://)?(www\.)?t\.me/@?([a-zA-Z_][a-zA-Z0-9_]+)',
        html_link,
        text,
        flags=re.IGNORECASE
    )

    # Now for @-mentions
    # Keep @1234xxxx as plain text (not linkified, not replaced)
    text = re.sub(
        r'@(\d{4}[a-zA-Z0-9_]+)',
        lambda m: m.group(0),  # just leave as is
        text
    )

    # Replace all other @usernames with HTML link
    text = re.sub(
        r'@([a-zA-Z_][a-zA-Z0-9_]+)',
        html_link,
        text
    )

    # Replace emails with HTML link
    text = re.sub(r'\b\S+@\S+\.\S+\b', html_link, text)

    return text



def force_link_usernames(text):
    def make_link(match):
        username = match.group(1)
        return f'<a href="https://t.me/{username}">@{username}</a>'
    return re.sub(r'@([a-zA-Z_][a-zA-Z0-9_]{4,})', make_link, text)


# def strip_hashtag_links(text, entities):
#     """
#     If a text_link entity's text starts with #, remove the link but keep the hashtag as plain text.
#     Returns the new text and new entities.
#     """
#     if not entities:
#         return text, entities
#     new_entities = []
#     for ent in entities:
#         try:
#             # Telegram v20: ent.offset/length are always correct for original text
#             if ent.type == 'text_link' and text[ent.offset:ent.offset + ent.length].startswith("#"):
#                 # Do not add this entity (removes the link, keeps the hashtag)
#                 continue
#         except Exception as e:
#             # Defensive: skip errors, but don't crash
#             pass
#         new_entities.append(ent)
#     return text, new_entities




# ----------------- MULTI-USER FORWARDING (NEW) ---------------------

# Handler for channel posts only (multi-user)
async def manual_forward(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("manual_forward called!")
    if update.channel_post:
        print("Received channel post:", update.channel_post)
        channel_id = update.channel_post.chat_id
    else:
        print("No channel_post in this update.")
        return

    settings = load_user_settings()
    print("Loaded user_settings:", settings)
    found = False
    # This will collect all matched users
    for user_id, user_conf in settings.items():
        print(f"Checking user {user_id} src={user_conf.get('src')} dst={user_conf.get('dst')}")
        print(f"User {user_id} active state: {user_conf.get('active', True)}")
        if user_conf.get("src") == channel_id and user_conf.get("active", True):
            found = True
            print(f"Matched user {user_id}, will forward!")
            dst = user_conf.get("dst")
            lang = user_conf.get("lang", "en")
            username = user_conf.get("username", "@username")
            print(f"Passing username to forward_message_recursive: {username}")
            # Schedule a forward for EACH user that matches
            await forward_message_recursive(context.bot, update.channel_post, dst, lang, username, user_id=int(user_id))
    if not found:
        print("No matching src in user_settings for this channel post!")



async def flush_group(bot, user_id, group_id, DST, LANG, USERNAME, reply_to_message_id=None):
    print(f"Flushing media group for user {user_id}, group {group_id}")
    await asyncio.sleep(0.8)  # allow batching
    queue_items = media_queues.pop((user_id, group_id), [])
    scheduled.discard((user_id, group_id))

    if queue_items:
        media_group = []
        for idx, (item, src_msg_id) in enumerate(queue_items):
            if idx == 0:
                raw_caption = getattr(item, "caption", None)
                print(f"Using USERNAME in clean_text: {USERNAME}")
                cleaned = clean_text(raw_caption, username=USERNAME) if raw_caption else None
                translated = translate_preserving_usernames(cleaned, dest=LANG) if cleaned else None
                # Also support force_link_usernames in captions
                final_caption = force_link_usernames(translated) if translated else None
                if isinstance(item, InputMediaPhoto):
                    new_item = InputMediaPhoto(media=item.media, caption=final_caption, caption_entities=None, parse_mode="HTML")
                elif isinstance(item, InputMediaVideo):
                    new_item = InputMediaVideo(media=item.media, caption=final_caption, caption_entities=None, parse_mode="HTML")
                elif isinstance(item, InputMediaDocument):
                    new_item = InputMediaDocument(media=item.media, caption=final_caption, caption_entities=None, parse_mode="HTML")
                else:
                    new_item = item
            else:
                # Only first item gets caption
                if isinstance(item, InputMediaPhoto):
                    new_item = InputMediaPhoto(media=item.media, caption=None, caption_entities=None)
                elif isinstance(item, InputMediaVideo):
                    new_item = InputMediaVideo(media=item.media, caption=None, caption_entities=None)
                elif isinstance(item, InputMediaDocument):
                    new_item = InputMediaDocument(media=item.media, caption=None, caption_entities=None)
                else:
                    new_item = item
            media_group.append(new_item)

        src_message_ids = [item[1] for item in queue_items]
        send_kwargs = {"chat_id": DST, "media": media_group}
        if reply_to_message_id:
            send_kwargs["reply_to_message_id"] = reply_to_message_id

        msgs = await safe_send(bot.send_media_group, **send_kwargs)

        if msgs:
            for src_msg_id, dst_msg in zip(src_message_ids, msgs):
                msg_id_map[(user_id, src_msg_id)] = dst_msg.message_id



async def forward_message_recursive(bot, msg: Message, DST, LANG, USERNAME, user_id=None):
    if user_id is None:
        raise ValueError("user_id must always be provided to forward_message_recursive")
    if not msg:
        return None
    # Use per-user+src_msg mapping
    key = (user_id, msg.message_id)
    if key in msg_id_map:
        return msg_id_map[key]

    # Find reply destination for this user, if applicable
    reply_to_msg_id = None
    if msg.reply_to_message:
        reply_to_msg_id = await forward_message_recursive(
            bot, msg.reply_to_message, DST, LANG, USERNAME, user_id=user_id
        )

    if is_true_forward(msg):
        sent_msg = await safe_send(
            bot.forward_message,
            chat_id=DST,
            from_chat_id=msg.chat_id,
            message_id=msg.message_id
        )
        if sent_msg:
            msg_id_map[key] = sent_msg.message_id
        return sent_msg.message_id if sent_msg else None

    # MEDIA GROUPS / ALBUMS
    if msg.media_group_id:
        gid = msg.media_group_id
        group_key = (user_id, gid)
        queue = media_queues.setdefault(group_key, [])

        media_item = None
        if msg.photo:
            media_item = InputMediaPhoto(msg.photo[-1].file_id, caption=msg.caption or "", caption_entities=msg.caption_entities)
        elif msg.video:
            media_item = InputMediaVideo(msg.video.file_id, caption=msg.caption or "", caption_entities=msg.caption_entities)
        elif msg.document:
            media_item = InputMediaDocument(msg.document.file_id, caption=msg.caption or "", caption_entities=msg.caption_entities)

        if media_item:
            queue.append((media_item, msg.message_id))
        else:
            return None  # unsupported in groups

        if group_key not in scheduled:
            scheduled.add(group_key)
            asyncio.create_task(flush_group(
                bot, user_id, gid, DST, LANG, USERNAME, reply_to_message_id=reply_to_msg_id
            ))
        return None

    # Non-media-group single message
    await forward_single_message(bot, msg, DST, LANG, USERNAME, user_id, reply_to_message_id=reply_to_msg_id)
    return msg_id_map.get(key)


async def forward_single_message(bot, msg: Message, DST, LANG, USERNAME, user_id, reply_to_message_id=None):
    raw_caption = msg.caption if msg.caption else None
    print(f"Using USERNAME in clean_text: {USERNAME}")
    cleaned_caption = clean_text(raw_caption, username=USERNAME) if raw_caption else None
    translated_caption = translate_preserving_usernames(cleaned_caption, dest=LANG) if cleaned_caption else None
    cleaned_text = clean_text(msg.text, username=USERNAME) if msg.text else None
    translated_text = translate_preserving_usernames(cleaned_text, dest=LANG) if cleaned_text else None

    common = dict(
        chat_id=DST,
        caption=translated_caption,
        caption_entities=None,
        disable_notification=False,
    )
    if reply_to_message_id:
        common["reply_to_message_id"] = reply_to_message_id

    sent_msg = None

    if msg.photo:
        final_caption = force_link_usernames(translated_caption) if translated_caption else None
        sent_msg = await safe_send(
            bot.send_photo, chat_id=DST, photo=msg.photo[-1].file_id, caption=final_caption,
            caption_entities=None, parse_mode=ParseMode.HTML, disable_notification=False,
            **({"reply_to_message_id": reply_to_message_id} if reply_to_message_id else {})
        )
    elif msg.video:
        final_caption = force_link_usernames(translated_caption) if translated_caption else None
        sent_msg = await safe_send(
            bot.send_video, chat_id=DST, video=msg.video.file_id, caption=final_caption,
            caption_entities=None, parse_mode=ParseMode.HTML, disable_notification=False,
            **({"reply_to_message_id": reply_to_message_id} if reply_to_message_id else {})
        )
    elif msg.document:
        final_caption = force_link_usernames(translated_caption) if translated_caption else None
        sent_msg = await safe_send(
            bot.send_document, document=msg.document.file_id, caption=final_caption,
            caption_entities=None, parse_mode=ParseMode.HTML, disable_notification=False,
            **({"reply_to_message_id": reply_to_message_id} if reply_to_message_id else {})
        )
    elif msg.text:
        final_text = force_link_usernames(translated_text) if translated_text else None
        sent_msg = await safe_send(
            bot.send_message,
            chat_id=DST,
            text=final_text,
            entities=None,
            parse_mode=ParseMode.HTML,
            **({"reply_to_message_id": reply_to_message_id} if reply_to_message_id else {})
        )
    elif msg.sticker:
        sent_msg = await safe_send(
            bot.send_sticker,
            chat_id=DST,
            sticker=msg.sticker.file_id,
            **({"reply_to_message_id": reply_to_message_id} if reply_to_message_id else {})
        )
    elif msg.voice:
        sent_msg = await safe_send(bot.send_voice, chat_id=DST, voice=msg.voice.file_id, **common)
    elif msg.audio:
        sent_msg = await safe_send(bot.send_audio, chat_id=DST, audio=msg.audio.file_id, **common)
    elif msg.animation:
        sent_msg = await safe_send(bot.send_animation, chat_id=DST, animation=msg.animation.file_id, **common)
    else:
        print("Unsupported message type.")

    if sent_msg:
        msg_id_map[(user_id, msg.message_id)] = sent_msg.message_id
        print(f"Map: SRC {msg.message_id} → DST {sent_msg.message_id}")


async def edit_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("Edit handler triggered!", update)
    msg = getattr(update, "edited_channel_post", None)
    if not msg:
        print("No edited_channel_post in update.")
        return

    settings = load_user_settings()
    channel_id = msg.chat_id
    found_any = False
    for user_id, user_conf in settings.items():
        print(f"User {user_id} active state: {user_conf.get('active', True)}")
        if user_conf.get("src") == channel_id and user_conf.get("active", True):
            dst = user_conf.get("dst")
            lang = user_conf.get("lang", "en")
            username = user_conf.get("username", "@username")
            dst_msg_id = msg_id_map.get((int(user_id), msg.message_id))
            if not dst_msg_id:
                print(f"No destination message found for (user {user_id}) SRC {msg.message_id}")
                continue
            try:
                if msg.text:
                    cleaned_text = clean_text(msg.text, username=username)
                    translated = translate_preserving_usernames(cleaned_text, dest=lang)
                    final_text = force_link_usernames(translated)
                    await context.bot.edit_message_text(
                        chat_id=dst,
                        message_id=dst_msg_id,
                        text=final_text,
                        entities=None,
                        parse_mode=ParseMode.HTML,
                    )
                elif msg.caption:
                    cleaned_caption = clean_text(msg.caption, username=username)
                    translated = translate_preserving_usernames(cleaned_caption, dest=lang)
                    final_caption = force_link_usernames(translated)
                    await context.bot.edit_message_caption(
                        chat_id=dst,
                        message_id=dst_msg_id,
                        caption=final_caption,
                        caption_entities=None,
                        parse_mode=ParseMode.HTML,
                    )
                print(f"Edited DST {dst_msg_id} for user {user_id}")
                found_any = True
            except TelegramError as e:
                print(f"Edit failed for user {user_id}: {e}")
    if not found_any:
        print(f"No destination message found for SRC {msg.message_id} for any user.")


async def quick_forward_control(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private":
        return  # only allow in private chat
    text = (update.message.text or "").strip().lower()
    user_id = update.effective_user.id

    if text == "stop forwarding":
        update_settings(user_id, active=False)
        await update.message.reply_text("⛔️ Forwarding is now *DISABLED* for you. Use 'Start Forwarding' to resume.",
                                       parse_mode=ParseMode.MARKDOWN, reply_markup=get_menu())
        print(f"[QUICK CONTROL] User {user_id} set active to False")
    elif text == "start forwarding":
        update_settings(user_id, active=True)
        await update.message.reply_text("✅ Forwarding is now *ENABLED* for you!",
                                       parse_mode=ParseMode.MARKDOWN, reply_markup=get_menu())
        print(f"[QUICK CONTROL] User {user_id} set active to True")

# -------------------------------------------------------------

if __name__ == "__main__":
    # TOKEN = "8191615350:AAGHn0E93wSjrf4LC4C6A4Z3ihcXk3SCRcQ"
    TOKEN = "8191615350:AAGHn0E93wSjrf4LC4C6A4Z3ihcXk3SCRcQ"
    app = ApplicationBuilder().token(TOKEN).build()

    # ---- MENU/COMMANDS ----
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            MessageHandler(filters.Regex("^(Set Source Channel|Set Destination Channel|Set Language|Set Username|Help)$"), menu_handler),
        ],
        states={
            AWAIT_SRC: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_src)],
            AWAIT_DST: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_dst)],
            AWAIT_LANG: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_lang)],
            AWAIT_USER: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_username)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
    )
    app.add_handler(conv_handler)
    app.add_handler(MessageHandler(
        filters.TEXT & filters.ChatType.PRIVATE & (
                    filters.Regex("^Stop Forwarding$") | filters.Regex("^Start Forwarding$")),
        quick_forward_control
    ))

    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(TypeHandler(Update, edit_handler), group=0)

    # --------- MULTI-USER FORWARDING ---------
    app.add_handler(MessageHandler(filters.ALL, manual_forward), group=1)

    print("✅ Bot running—multi-user forwarding enabled!")
    app.run_polling()
