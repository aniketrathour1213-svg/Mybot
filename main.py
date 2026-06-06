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
import uuid
from datetime import datetime

# --- Pyrogram ---
from pyrogram import Client, filters
from pyrogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
    Message
)
from pyrogram.errors import UserNotParticipant, FloodWait

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
# INITIALIZE BOT
# ============================================================

app = Client(
    name="video_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    in_memory=True,
    workdir="."
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
                video_msg_id=video_msg.id,
                note_msg_id=note_msg.id,
                video_id=video_id
            )
        )

        return video_msg, note_msg
    except Exception as e:
        logger.error(f"❌ Error sending video to {chat_id}: {e}")
        return None, None


async def auto_delete_messages(chat_id: int, video_msg_id: int, note_msg_id: int, video_id: str):
    """Auto-delete messages after timeout"""
    await asyncio.sleep(DELETE_AFTER_MINUTES * 60)
    try:
        await app.delete_messages(chat_id=chat_id, message_ids=[video_msg_id, note_msg_id])
        logger.info(f"🗑 Auto-deleted {video_id} for {chat_id}")
    except Exception as e:
        logger.warning(f"⚠️ Could not delete messages for {chat_id}: {e}")


# ============================================================
# RENDER HEALTH CHECK SERVER — FIXED PORT
# ============================================================

async def run_health_server():
    """Run health check server for Render"""
    # 🔥 FIX #3: Render expects PORT 10000 usually
    PORT = int(os.environ.get("PORT", 10000))

    async def health(request):
        return web.Response(text="OK", status=200)

    async def stats(request):
        return web.json_response({
            "status": "running",
            "users": len(bot_data.get("users", {})),
            "total_videos_sent": bot_data.get("stats", {}).get("total_videos_sent", 0),
            "total_verified": bot_data.get("stats", {}).get("total_verified", 0)
        })

    app_web = web.Application()
    app_web.router.add_get("/", health)
    app_web.router.add_get("/health", health)
    app_web.router.add_get("/stats", stats)

    runner = web.AppRunner(app_web)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    logger.info(f"🌐 Health server running on port {PORT}")


# ============================================================
# BOT HANDLERS
# ============================================================


@app.on_message(filters.command("start") & filters.private)
async def start_command(client: Client, message: Message):
    """Handle /start command"""
    user = message.from_user
    uid = str(user.id)

    # 🔥 FIX #4: Logging bug fixed — properly formatted f-string
    logger.info(f"🚀 /start from {user.id} ({user.first_name})")

    # Register user
    await register_user(user.id, user.username, user.first_name)

    # Check channel membership
    ok, ch1, ch2 = await check_both_channels(user.id)

    if ok:
        # User has joined both channels — show main menu
        welcome_text = (
            f"<b>Welcome {user.first_name}!</b>\n\n"
            "<b>🎬 Video Monetization Bot</b>\n\n"
            "<b>You have access to premium video content.</b>\n"
            "<b>Use the buttons below to get started.</b>"
        )

        await message.reply_text(
            text=welcome_text,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🎥 Watch Videos", callback_data="watch_videos")],
                [InlineKeyboardButton("👤 My Profile", callback_data="my_profile")],
                [InlineKeyboardButton("📢 Share & Earn", callback_data="share_earn")]
            ])
        )
    else:
        # Show join buttons
        join_message = format_join_message(ch1, ch2)
        await message.reply_text(
            text=join_message,
            reply_markup=get_join_buttons(),
            disable_web_page_preview=True
        )


@app.on_callback_query()
async def handle_callbacks(client: Client, callback_query: CallbackQuery):
    """Handle all callback queries"""
    user = callback_query.from_user
    data = callback_query.data

    try:
        if data == "verify_join":
            ok, ch1, ch2 = await check_both_channels(user.id)

            if ok:
                await callback_query.answer("✅ Verification successful!", show_alert=True)
                await callback_query.message.edit_text(
                    text=f"<b>Welcome {user.first_name}!</b>\n\n"
                         "<b>🎬 Video Monetization Bot</b>\n\n"
                         "<b>You have access to premium video content.</b>\n"
                         "<b>Use the buttons below to get started.</b>",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🎥 Watch Videos", callback_data="watch_videos")],
                        [InlineKeyboardButton("👤 My Profile", callback_data="my_profile")],
                        [InlineKeyboardButton("📢 Share & Earn", callback_data="share_earn")]
                    ])
                )
            else:
                await callback_query.answer("❌ You haven't joined both channels yet!", show_alert=True)
                await callback_query.message.edit_text(
                    text=format_join_message(ch1, ch2),
                    reply_markup=get_join_buttons(),
                    disable_web_page_preview=True
                )

        elif data == "watch_videos":
            await callback_query.answer()
            await callback_query.message.edit_text(
                text="<b>🎥 Premium Videos</b>\n\n"
                     "<b>Select a category:</b>",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📁 Category 1", callback_data="cat_1")],
                    [InlineKeyboardButton("📁 Category 2", callback_data="cat_2")],
                    [InlineKeyboardButton("🔙 Back", callback_data="back_main")]
                ])
            )

        elif data == "my_profile":
            uid = str(user.id)
            user_data = bot_data["users"].get(uid, {})
            await callback_query.answer()
            await callback_query.message.edit_text(
                text=f"<b>👤 Your Profile</b>\n\n"
                     f"<b>ID:</b> <code>{user.id}</code>\n"
                     f"<b>Name:</b> {user.first_name}\n"
                     f"<b>Username:</b> @{user.username or 'N/A'}\n"
                     f"<b>Joined:</b> {user_data.get('joined_date', 'N/A')}\n"
                     f"<b>Videos Watched:</b> {len(user_data.get('videos_watched', []))}",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Back", callback_data="back_main")]
                ])
            )

        elif data == "share_earn":
            await callback_query.answer()
            bot_username = (await app.get_me()).username
            share_link = f"https://t.me/{bot_username}?start=ref_{user.id}"
            await callback_query.message.edit_text(
                text=f"<b>📢 Share & Earn</b>\n\n"
                     f"<b>Share this link with friends:</b>\n"
                     f"<code>{share_link}</code>\n\n"
                     f"<b>For each friend who joins, you earn rewards!</b>",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Back", callback_data="back_main")]
                ])
            )

        elif data == "back_main":
            await callback_query.answer()
            await callback_query.message.edit_text(
                text=f"<b>Welcome back {user.first_name}!</b>\n\n"
                     "<b>🎬 Video Monetization Bot</b>\n\n"
                     "<b>What would you like to do?</b>",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🎥 Watch Videos", callback_data="watch_videos")],
                    [InlineKeyboardButton("👤 My Profile", callback_data="my_profile")],
                    [InlineKeyboardButton("📢 Share & Earn", callback_data="share_earn")]
                ])
            )

        elif data.startswith("cat_"):
            await callback_query.answer("📂 Loading videos...")
            await callback_query.message.edit_text(
                text="<b>📂 No videos available in this category yet.</b>\n\n"
                     "<b>Check back later!</b>",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Back", callback_data="watch_videos")]
                ])
            )

        else:
            await callback_query.answer("❌ Unknown action")

    except Exception as e:
        logger.error(f"❌ Callback error: {e}")
        await callback_query.answer("❌ An error occurred", show_alert=True)


# ============================================================
# MAIN FUNCTION — 🔥 FIXED: No idle(), no start_bot(), no double loop
# ============================================================

async def main():
    """Main entry point — fully fixed for Render"""
    logger.info("=" * 50)
    logger.info("🚀 Starting Bot...")

    # Start Pyrogram client
    await app.start()
    logger.info(f"✅ Bot started: @{app.me.username}")

    # Run health server in background as a task
    asyncio.create_task(run_health_server())

    # Keep alive properly — this blocks but doesn't freeze like idle()
    # asyncio.Event().wait() keeps the loop running without blocking handlers
    await asyncio.Event().wait()


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Bot stopped by user")
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        traceback.print_exc()
