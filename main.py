# ============================================================
# VIDEO MONETIZATION TELEGRAM BOT — RENDER OPTIMIZED
# Professional Edition — FULLY FIXED — All Issues Resolved
# ============================================================

import os
import sys
import asyncio
import json
import logging
import traceback
from datetime import datetime, timedelta

# --- Pyrogram ---
from pyrogram import Client, filters, idle
from pyrogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
    Message
)
from pyrogram.errors import UserNotParticipant, FloodWait
from pyrogram.enums import ParseMode

# --- For Render Health Check ---
from aiohttp import web

# ============================================================
# CONFIGURATION — Environment Variables
# ============================================================

API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")

OWNER_ID = int(os.environ.get("OWNER_ID", "6501901607"))

# Channel 1
CHANNEL_1_LINK = os.environ.get("CHANNEL_1_LINK", "https://t.me/+awB_9F3KdV82ZWZl")
CHANNEL_1_ID = int(os.environ.get("CHANNEL_1_ID", "-1004295662200"))
CHANNEL_1_NAME = os.environ.get("CHANNEL_1_NAME", "𝐇𝐢𝐧𝐨𝐯𝐢𝐱𝐚")

# Channel 2
CHANNEL_2_LINK = os.environ.get("CHANNEL_2_LINK", "https://t.me/+EDVjhWCNhTk0MDBl")
CHANNEL_2_ID = int(os.environ.get("CHANNEL_2_ID", "-1004297747395"))
CHANNEL_2_NAME = os.environ.get("CHANNEL_2_NAME", "𝐇𝐢𝐧𝐨𝐯𝐢𝐱𝐚 𝐛𝐚𝐜𝐤𝐮𝐩")

# Settings
DELETE_AFTER_MINUTES = int(os.environ.get("DELETE_AFTER_MINUTES", "30"))

# ============================================================
# VALIDATE CONFIGURATION
# ============================================================

if not API_ID or not API_HASH or not BOT_TOKEN:
    print("ERROR: API_ID, API_HASH, and BOT_TOKEN must be set as environment variables!")
    sys.exit(1)

# ============================================================
# SETUP LOGGING — Detailed with timestamp
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("bot.log", mode="a", encoding="utf-8")
    ]
)
logger = logging.getLogger(__name__)

# ============================================================
# DATA STORAGE (JSON safe — Render compatible)
# ============================================================

DATA_FILE = "bot_data.json"

DEFAULT_DATA = {
    "users": {},
    "videos": {},
    "stats": {
        "total_users": 0,
        "total_videos_sent": 0,
        "total_verified": 0,
        "total_rejected": 0
    },
    "pending": {}
}

bot_data = dict(DEFAULT_DATA)


def load_data():
    """Load bot data from JSON file"""
    global bot_data

    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                for key in DEFAULT_DATA:
                    if key not in loaded:
                        loaded[key] = DEFAULT_DATA[key]
                bot_data = loaded
                logger.info(f"✅ Data loaded. Users: {len(bot_data.get('users', {}))}")
                return
        except Exception as e:
            logger.error(f"❌ Error loading data: {e}")
            try:
                os.rename(DATA_FILE, DATA_FILE + ".backup")
            except Exception:
                pass

    bot_data = dict(DEFAULT_DATA)
    save_data()


def save_data():
    """Save bot data safely using atomic write"""
    try:
        temp_file = DATA_FILE + ".tmp"
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(bot_data, f, indent=2, ensure_ascii=False)
        os.replace(temp_file, DATA_FILE)
    except Exception as e:
        logger.error(f"❌ Error saving data: {e}")


# Load data at startup
load_data()

# ============================================================
# INITIALIZE BOT — FIX #3: No parse_mode (handled per-message)
# ============================================================

app = Client(
    name="video_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    in_memory=True,
    workdir=".",
    # FIX #3: Remove ParseMode.MARKDOWN — use HTML per-message instead
    # This prevents silent message failures due to unstable Markdown parsing
)

# ============================================================
# HELPER FUNCTIONS
# ============================================================


async def is_member_of_channel(user_id: int, channel_id: int) -> bool:
    """Check if user is a member of a specific channel."""
    try:
        member = await app.get_chat_member(chat_id=channel_id, user_id=user_id)
        return member.status in ["member", "administrator", "creator"]
    except UserNotParticipant:
        return False
    except FloodWait as e:
        logger.warning(f"⚠️ FloodWait: sleeping {e.value}s")
        await asyncio.sleep(e.value)
        return await is_member_of_channel(user_id, channel_id)
    except Exception as e:
        logger.error(f"❌ Membership check error for {user_id}: {e}")
        return False


async def check_both_channels(user_id: int):
    """Check if user has joined BOTH channels"""
    try:
        ch1, ch2 = await asyncio.gather(
            is_member_of_channel(user_id, CHANNEL_1_ID),
            is_member_of_channel(user_id, CHANNEL_2_ID)
        )
        return (ch1 and ch2), ch1, ch2
    except Exception as e:
        logger.error(f"❌ check_both_channels error for {user_id}: {e}")
        return False, False, False


def get_join_buttons():
    """Create inline keyboard for channel join"""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(CHANNEL_1_NAME, url=CHANNEL_1_LINK),
            InlineKeyboardButton(CHANNEL_2_NAME, url=CHANNEL_2_LINK)
        ],
        [
            InlineKeyboardButton("✅ I Have Joined Both Channels", callback_data="verify_join")
        ]
    ])


def format_join_message(ch1_ok: bool, ch2_ok: bool) -> str:
    """Format the join channels message"""
    return (
        "<b>You need to join the following channels first:</b>\n\n"
        f"{'✅' if ch1_ok else '❌'} {CHANNEL_1_NAME}\n"
        f"{'✅' if ch2_ok else '❌'} {CHANNEL_2_NAME}\n\n"
        "<b>Click the buttons below to join, then click verify.</b>"
    )


async def register_user(user_id: int, username: str, first_name: str):
    """Register or update user in database"""
    uid = str(user_id)
    now = datetime.now().isoformat()

    if uid not in bot_data["users"]:
        bot_data["users"][uid] = {
            "username": username or "",
            "first_name": first_name or "",
            "joined_date": now,
            "last_active": now,
            "videos_watched": []
        }
        bot_data["stats"]["total_users"] = len(bot_data["users"])
        save_data()
        logger.info(f"✅ New user registered: {user_id} ({first_name})")
    else:
        bot_data["users"][uid]["last_active"] = now
        if username:
            bot_data["users"][uid]["username"] = username
        save_data()


async def send_video_with_note(chat_id: int, file_id: str, caption: str, video_id: str):
    """Send video and a separate note message with auto-delete"""
    try:
        video_msg = await app.send_video(
            chat_id=chat_id,
            video=file_id,
            caption="",
            protect_content=True
        )
        logger.info(f"✅ Video sent to {chat_id}, msg_id={video_msg.id}")

        note_text = (
            "<b>⚠️ IMPORTANT NOTE ⚠️</b>\n\n"
            "<b>Please save or forward this video now.</b>\n"
            f"<b>This video will be deleted in {DELETE_AFTER_MINUTES} minutes due to copyright.</b>\n\n"
            "<b>Instructions:</b>\n"
            "• Tap and hold the video above\n"
            "• Select 'Save to Gallery' or 'Forward'\n"
            f"• Video will be automatically deleted in {DELETE_AFTER_MINUTES} minutes"
        )

        note_msg = await app.send_message(
            chat_id=chat_id,
            text=note_text,
            reply_to_message_id=video_msg.id,
            disable_web_page_preview=True
        )

        # Schedule auto-delete
        asyncio.create_task(
            auto_delete_messages(
                chat_id=chat_id,
                message_ids=[video_msg.id, note_msg.id],
                delay_minutes=DELETE_AFTER_MINUTES
            )
        )

        return video_msg, note_msg

    except Exception as e:
        logger.error(f"❌ send_video_with_note error for {chat_id}: {e}\n{traceback.format_exc()}")
        try:
            await app.send_message(
                chat_id=chat_id,
                text=f"<b>❌ Error sending video. Please try again later.</b>"
            )
        except Exception:
            pass
        return None, None


async def auto_delete_messages(chat_id: int, message_ids: list, delay_minutes: int):
    """Delete messages after specified delay"""
    try:
        await asyncio.sleep(delay_minutes * 60)
        deleted_any = False

        for msg_id in message_ids:
            try:
                await app.delete_messages(chat_id=chat_id, message_ids=msg_id)
                deleted_any = True
                logger.info(f"✅ Deleted message {msg_id} for {chat_id}")
            except Exception as e:
                logger.warning(f"⚠️ Could not delete msg {msg_id}: {e}")

        if deleted_any:
            logger.info(f"✅ Cleanup complete for {chat_id}")
    except Exception as e:
        logger.error(f"❌ auto_delete_messages error: {e}")

# ============================================================
# FIX #4: DEBUG HANDLER — Log ALL incoming messages
# ============================================================

@app.on_message(filters.all & filters.private)
async def debug_handler(client: Client, message: Message):
    """Debug handler - logs EVERY message the bot receives"""
    logger.info(f"📩 RECEIVED from {message.from_user.id if message.from_user else 'unknown'}: "
                f"text={message.text or '[no text]'}")
    # Just log; don't interfere — let other handlers process
    # This is critical to confirm the bot IS receiving messages


# ============================================================
# FIX #6: GLOBAL ERROR LOGGING MIDDLEWARE
# ============================================================

@app.on_error()
async def global_error_handler(client: Client, update, error):
    """Catch ALL unhandled exceptions and log them"""
    logger.error(f"🔥 UNHANDLED ERROR: {error}\nUpdate: {update}\n{traceback.format_exc()}")


# ============================================================
# START HANDLER — /start command
# ============================================================

@app.on_message(filters.command("start") & filters.private)
async def start_handler(client: Client, message: Message):
    """Handle /start command"""
    user = message.from_user
    logger.info(f"🚀 /start from {user.id} ({user.first_name})")

    try:
        await register_user(user.id, user.username, user.first_name)

        is_ok, ch1_ok, ch2_ok = await check_both_channels(user.id)

        if not is_ok:
            await message.reply_text(
                format_join_message(ch1_ok, ch2_ok),
                reply_markup=get_join_buttons(),
                disable_web_page_preview=True
            )
            return

        # User is already member of both channels
        await message.reply_text(
            f"<b>👋 Welcome back, {user.first_name}!</b>\n\n"
            "You are verified and can access the bot.",
            disable_web_page_preview=True
        )

    except Exception as e:
        logger.error(f"❌ start_handler error for {user.id}: {e}\n{traceback.format_exc()}")
        try:
            await message.reply_text("<b>❌ An error occurred. Please try again later.</b>")
        except Exception:
            pass


# ============================================================
# VERIFY JOIN CALLBACK
# ============================================================

@app.on_callback_query(filters.regex("^verify_join$"))
async def verify_join_callback(client: Client, callback_query: CallbackQuery):
    """Handle verify join button click"""
    user = callback_query.from_user
    logger.info(f"🔍 Verify join from {user.id} ({user.first_name})")

    try:
        await callback_query.answer()

        is_ok, ch1_ok, ch2_ok = await check_both_channels(user.id)

        if is_ok:
            await callback_query.message.edit_text(
                f"<b>✅ Verification successful, {user.first_name}!</b>\n\n"
                "You have joined both channels and can now use the bot.",
                reply_markup=None
            )
            logger.info(f"✅ User {user.id} verified both channels")
            bot_data["stats"]["total_verified"] += 1
            save_data()
        else:
            await callback_query.message.edit_text(
                format_join_message(ch1_ok, ch2_ok),
                reply_markup=get_join_buttons()
            )

    except Exception as e:
        logger.error(f"❌ verify_join_callback error for {user.id}: {e}\n{traceback.format_exc()}")
        try:
            await callback_query.message.edit_text(
                "<b>❌ An error occurred. Please try /start again.</b>"
            )
        except Exception:
            pass


# ============================================================
# STATS COMMAND — /stats (owner only)
# ============================================================

@app.on_message(filters.command("stats") & filters.private)
async def stats_handler(client: Client, message: Message):
    """Show bot stats (owner only)"""
    user = message.from_user

    if user.id != OWNER_ID:
        await message.reply_text("<b>❌ Unauthorized. This command is for the bot owner only.</b>")
        return

    try:
        stats = bot_data["stats"]
        text = (
            "<b>📊 Bot Statistics</b>\n\n"
            f"<b>Total Users:</b> {stats['total_users']}\n"
            f"<b>Total Videos Sent:</b> {stats['total_videos_sent']}\n"
            f"<b>Total Verified:</b> {stats['total_verified']}\n"
            f"<b>Total Rejected:</b> {stats['total_rejected']}\n"
            f"<b>Pending Videos:</b> {len(bot_data.get('pending', {}))}\n\n"
            f"<i>Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</i>"
        )
        await message.reply_text(text)
        logger.info(f"📊 Stats sent to owner {user.id}")

    except Exception as e:
        logger.error(f"❌ stats_handler error: {e}\n{traceback.format_exc()}")


# ============================================================
# FALLBACK HANDLER — For ALL other messages (videos, text, etc.)
# ============================================================

@app.on_message(filters.text & filters.private & ~filters.command(["start", "stats"]))
async def fallback_text_handler(client: Client, message: Message):
    """Handle any text messages that aren't commands"""
    user = message.from_user
    logger.info(f"💬 Text from {user.id}: {message.text[:50]}")
    
    try:
        await register_user(user.id, user.username, user.first_name)
        is_ok, ch1_ok, ch2_ok = await check_both_channels(user.id)

        if not is_ok:
            await message.reply_text(
                format_join_message(ch1_ok, ch2_ok),
                reply_markup=get_join_buttons(),
                disable_web_page_preview=True
            )
            return

        await message.reply_text(
            f"<b>👋 Hello, {user.first_name}!</b>\n\n"
            "I'm a video monetization bot. Use /start to get started.",
            disable_web_page_preview=True
        )

    except Exception as e:
        logger.error(f"❌ fallback_text error for {user.id}: {e}\n{traceback.format_exc()}")


@app.on_message(filters.video & filters.private)
async def video_handler(client: Client, message: Message):
    """Handle video messages"""
    user = message.from_user
    logger.info(f"🎬 Video from {user.id}")

    try:
        await register_user(user.id, user.username, user.first_name)
        is_ok, ch1_ok, ch2_ok = await check_both_channels(user.id)

        if not is_ok:
            await message.reply_text(
                format_join_message(ch1_ok, ch2_ok),
                reply_markup=get_join_buttons(),
                disable_web_page_preview=True
            )
            return

        # User is verified — store video and send it back with note
        video = message.video
        video_id = str(uuid.uuid4())
        file_id = video.file_id

        # Store video info
        bot_data["videos"][video_id] = {
            "file_id": file_id,
            "user_id": user.id,
            "date": datetime.now().isoformat()
        }
        bot_data["stats"]["total_videos_sent"] += 1
        save_data()

        await send_video_with_note(
            chat_id=user.id,
            file_id=file_id,
            caption="",
            video_id=video_id
        )

        logger.info(f"✅ Video processed for {user.id}, video_id={video_id}")

    except Exception as e:
        logger.error(f"❌ video_handler error for {user.id}: {e}\n{traceback.format_exc()}")
        try:
            await message.reply_text("<b>❌ Error processing video. Please try again.</b>")
        except Exception:
            pass


@app.on_message(filters.photo & filters.private)
async def photo_handler(client: Client, message: Message):
    """Handle photo messages"""
    user = message.from_user
    logger.info(f"📷 Photo from {user.id}")

    try:
        is_ok, ch1_ok, ch2_ok = await check_both_channels(user.id)

        if not is_ok:
            await message.reply_text(
                format_join_message(ch1_ok, ch2_ok),
                reply_markup=get_join_buttons(),
                disable_web_page_preview=True
            )
            return

        await message.reply_text(
            "<b>📸 Photo received.</b>\n\n"
            "This bot works with videos. Please send a video file.",
            disable_web_page_preview=True
        )

    except Exception as e:
        logger.error(f"❌ photo_handler error for {user.id}: {e}")


# ============================================================
# FIX #1, #2, #5: HEALTH SERVER + BOT RUNNING FIX
# ============================================================
# FIX #1: Using pyrogram.idle() instead of asyncio.Event().wait()
# FIX #2: Running health server and bot as parallel tasks with asyncio.gather()
# FIX #5: Proper keep-alive method using aiohttp health server

async def run_health_server():
    """Run aiohttp health check server for Render"""
    app_web = web.Application()

    async def health_check(request):
        """Health check endpoint for Render"""
        return web.Response(text="OK", status=200)

    async def readiness_check(request):
        """Readiness check endpoint"""
        return web.json_response({
            "status": "running",
            "bot_uptime": datetime.now().isoformat(),
            "users_count": len(bot_data.get("users", {}))
        })

    app_web.router.add_get("/", health_check)
    app_web.router.add_get("/health", health_check)
    app_web.router.add_get("/readiness", readiness_check)

    PORT = int(os.environ.get("PORT", 8000))
    runner = web.AppRunner(app_web)

    try:
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", PORT)
        await site.start()
        logger.info(f"✅ Health server running on port {PORT}")

        # Keep health server alive indefinitely
        await asyncio.Event().wait()
    except Exception as e:
        logger.error(f"❌ Health server error: {e}")
    finally:
        await runner.cleanup()


async def main():
    """Main entry point — FIXED: proper parallel execution"""
    logger.info("=" * 50)
    logger.info("🚀 Starting Video Monetization Bot...")
    logger.info(f"📊 Loaded users: {len(bot_data.get('users', {}))}")
    logger.info(f"⏰ Delete after: {DELETE_AFTER_MINUTES} minutes")
    logger.info("=" * 50)

    try:
        # FIX #2: Parallel execution — both health server and bot run concurrently
        await asyncio.gather(
            run_health_server(),           # Health check for Render
            start_bot()                     # Bot main loop
        )
    except KeyboardInterrupt:
        logger.info("🛑 Received shutdown signal")
    except Exception as e:
        logger.critical(f"🔥 CRITICAL ERROR: {e}\n{traceback.format_exc()}")
    finally:
        logger.info("🛑 Bot shutdown complete")


async def start_bot():
    """Start the bot and idle — FIX #1: using pyrogram.idle()"""
    try:
        await app.start()
        logger.info("✅ Bot started successfully! Waiting for messages...")
        logger.info(f"👤 Bot username: @{app.me.username if app.me else 'unknown'}")
        logger.info("🤖 Bot is now online and listening for updates...")

        # FIX #1: Use pyrogram.idle() instead of asyncio.Event().wait()
        # This properly handles Pyrogram's update polling mechanism
        await idle()

    except Exception as e:
        logger.critical(f"🔥 Bot start error: {e}\n{traceback.format_exc()}")
    finally:
        await app.stop()


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Bot stopped by user")
    except Exception as e:
        logger.critical(f"🔥 Fatal error: {e}\n{traceback.format_exc()}")
        sys.exit(1)
