# ============================================================
# VIDEO MONETIZATION TELEGRAM BOT
# RENDER OPTIMIZED — ALL COMMANDS WORKING — STABLE
# ============================================================

import os
import sys
import asyncio
import json
import logging
import uuid
import traceback
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
# SETUP LOGGING  
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ]
)
logger = logging.getLogger(__name__)

# ============================================================
# DATA STORAGE (JSON)
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
    global bot_data

    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                loaded = json.load(f)

            for key in DEFAULT_DATA:
                if key not in loaded:
                    loaded[key] = DEFAULT_DATA[key]

            bot_data = loaded
            logger.info(f"Data loaded. Users: {len(bot_data.get('users', {}))}")
            return

        except Exception as e:
            logger.error(f"Error loading data: {e}")

            try:
                os.rename(DATA_FILE, DATA_FILE + ".backup")
            except:
                pass

    bot_data = dict(DEFAULT_DATA)
    save_data()


def save_data():
    try:
        temp_file = DATA_FILE + ".tmp"
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(bot_data, f, indent=2, ensure_ascii=False)
        os.replace(temp_file, DATA_FILE)
    except Exception as e:
        logger.error(f"Error saving data: {e}")


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
    try:
        member = await app.get_chat_member(chat_id=channel_id, user_id=user_id)
        return member.status in ["member", "administrator", "creator"]
    except UserNotParticipant:
        return False
    except FloodWait as e:
        logger.warning(f"FloodWait: sleeping {e.value}s")
        await asyncio.sleep(e.value)
        return await is_member_of_channel(user_id, channel_id)
    except Exception as e:
        logger.error(f"Membership error for {user_id}: {e}")
        return False


async def check_both_channels(user_id: int):
    try:
        ch1, ch2 = await asyncio.gather(
            is_member_of_channel(user_id, CHANNEL_1_ID),
            is_member_of_channel(user_id, CHANNEL_2_ID)
        )
        return (ch1 and ch2), ch1, ch2
    except Exception as e:
        logger.error(f"Check channels error: {e}")
        return False, False, False


def get_join_buttons():
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
    return (
        "**You need to join the following channels first:**\n\n"
        f"{'✅' if ch1_ok else '❌'} {CHANNEL_1_NAME}\n"
        f"{'✅' if ch2_ok else '❌'} {CHANNEL_2_NAME}\n\n"
        "**Click the buttons below to join, then click verify.**"
    )


async def register_user(user_id: int, username: str, first_name: str):
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
        logger.info(f"New user registered: {user_id} ({first_name})")
    else:
        bot_data["users"][uid]["last_active"] = now
        if username:
            bot_data["users"][uid]["username"] = username
        save_data()


async def send_video_with_note(chat_id: int, file_id: str, caption: str, video_id: str):
    try:
        video_msg = await app.send_video(
            chat_id=chat_id,
            video=file_id,
            caption="",
            protect_content=True
        )
        logger.info(f"Video sent to {chat_id}, msg_id={video_msg.id}")

        note_text = (
            "**⚠️ IMPORTANT NOTE ⚠️**\n\n"
            "**Please save or forward this video now.**\n"
            f"**This video will be deleted in {DELETE_AFTER_MINUTES} minutes due to copyright.**\n\n"
            "**Instructions:**\n"
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
        logger.error(f"Error sending video to {chat_id}: {e}")
        return None, None


async def send_video_to_user(user_id: int, video_id: str):
    video_data = bot_data["videos"].get(video_id)
    if not video_data:
        await app.send_message(
            chat_id=user_id,
            text="**❌ This video is no longer available or has expired.**"
        )
        return False

    await send_video_with_note(
        chat_id=user_id,
        file_id=video_data["file_id"],
        caption=video_data.get("caption", ""),
        video_id=video_id
    )

    uid = str(user_id)
    if uid in bot_data["users"]:
        if video_id not in bot_data["users"][uid]["videos_watched"]:
            bot_data["users"][uid]["videos_watched"].append(video_id)
            bot_data["stats"]["total_videos_sent"] += 1
            save_data()

    return True


async def auto_delete_messages(chat_id: int, video_msg_id: int, note_msg_id: int, video_id: str):
    await asyncio.sleep(DELETE_AFTER_MINUTES * 60)
    try:
        await app.delete_messages(chat_id=chat_id, message_ids=[video_msg_id, note_msg_id])
        logger.info(f"Auto-deleted {video_id} for {chat_id}")
    except Exception as e:
        logger.warning(f"Could not delete messages: {e}")

# ============================================================
# RENDER HEALTH CHECK SERVER
# ============================================================

async def run_health_server():
    PORT = int(os.environ.get("PORT", 10000))

    async def health(request):
        return web.Response(text="OK", status=200)

    async def stats_endpoint(request):
        return web.json_response({
            "status": "running",
            "users": len(bot_data.get("users", {})),
            "total_videos_sent": bot_data.get("stats", {}).get("total_videos_sent", 0),
            "total_verified": bot_data.get("stats", {}).get("total_verified", 0)
        })

    app_web = web.Application()
    app_web.router.add_get("/", health)
    app_web.router.add_get("/health", health)
    app_web.router.add_get("/stats", stats_endpoint)

    runner = web.AppRunner(app_web)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    logger.info(f"Health server running on port {PORT}")


# ============================================================
# BOT HANDLERS — ALL ORIGINAL COMMANDS PRESERVED
# ============================================================
@app.on_message(filters.private)
async def debug_all(client, message):
    logger.info(f"MESSAGE RECEIVED: {message.text}")
# ----- /start -----
@app.on_message(filters.command("start") & filters.private)
async def start_command(client: Client, message: Message):
    user = message.from_user
    user_id = user.id
    username = user.username or ""
    first_name = user.first_name or ""

    await register_user(user_id, username, first_name)

    command_parts = message.text.split()

    # Case: Video link (/start VIDEO_ID)
    if len(command_parts) > 1:
        video_id = command_parts[1]
        is_ok, ch1, ch2 = await check_both_channels(user_id)

        if not is_ok:
            join_msg = format_join_message(ch1, ch2)
            await message.reply_text(
                text=join_msg,
                reply_markup=get_join_buttons(),
                disable_web_page_preview=True
            )
            bot_data["pending"][str(user_id)] = video_id
            save_data()
            return

        success = await send_video_to_user(user_id, video_id)
        if not success:
            await message.reply_text("**❌ Video not found. Please try again with a valid link.**")
        return

    # Case: Just /start
    is_ok, ch1, ch2 = await check_both_channels(user_id)

    if not is_ok:
        join_msg = format_join_message(ch1, ch2)
        await message.reply_text(
            text=join_msg,
            reply_markup=get_join_buttons(),
            disable_web_page_preview=True
        )
        return

    welcome_msg = (
        "**🎬 Welcome to the Premium Video System!**\n\n"
        "**How it works:**\n"
        "• Click on a video link shared in our channel\n"
        "• Join both required channels\n"
        "• Get your video instantly\n\n"
        f"**⚠️ Note:** All videos are automatically deleted after {DELETE_AFTER_MINUTES} minutes due to copyright protection.\n\n"
        "**Please save or forward videos immediately after receiving them.**"
    )

    await message.reply_text(welcome_msg)


# ----- Verify Join Callback -----
@app.on_callback_query(filters.regex("^verify_join$"))
async def verify_join_callback(client: Client, callback_query: CallbackQuery):
    user = callback_query.from_user
    user_id = user.id

    await callback_query.answer()

    is_ok, ch1, ch2 = await check_both_channels(user_id)

    if not is_ok:
        bot_data["stats"]["total_rejected"] += 1
        save_data()

        reject_msg = (
            "**❌ ACCESS DENIED ❌**\n\n"
            "**You have not joined both channels yet!**\n\n"
            f"{'✅' if ch1 else '❌'} {CHANNEL_1_NAME}\n"
            f"{'✅' if ch2 else '❌'} {CHANNEL_2_NAME}\n\n"
            "**Please join BOTH channels first, then click the verify button again.**"
        )

        try:
            await callback_query.edit_message_text(
                text=reject_msg,
                reply_markup=get_join_buttons(),
                disable_web_page_preview=True
            )
        except Exception as e:
            logger.error(f"Edit message error: {e}")
        return

    # VERIFIED
    bot_data["stats"]["total_verified"] += 1
    save_data()

    success_msg = (
        "**✅ VERIFICATION SUCCESSFUL ✅**\n\n"
        "**You have successfully joined both channels!**\n\n"
        f"✅ {CHANNEL_1_NAME}\n"
        f"✅ {CHANNEL_2_NAME}\n\n"
        "**Access granted! Please wait for your video...**"
    )

    try:
        await callback_query.edit_message_text(
            text=success_msg,
            disable_web_page_preview=True
        )
    except Exception as e:
        logger.error(f"Edit message error: {e}")

    # Send pending video if any
    uid = str(user_id)
    video_id = bot_data.get("pending", {}).pop(uid, None)
    if video_id:
        save_data()
        await send_video_to_user(user_id, video_id)
    else:
        await app.send_message(
            chat_id=user_id,
            text="**✅ You now have full access!**\n\n"
                 "Click any video link from our channel to receive content."
        )


# ----- /video — Owner command to add video -----
@app.on_message(filters.command("video") & filters.private)
async def video_command(client: Client, message: Message):
    user_id = message.from_user.id

    if user_id != OWNER_ID:
        await message.reply_text("**❌ You are not authorized to use this command.**")
        return

    if not message.reply_to_message or not message.reply_to_message.video:
        await message.reply_text(
            "**📤 How to add a video:**\n\n"
            "1. Send me the video file\n"
            "2. Reply to that video with:\n"
            "   `/video Your Caption Here`\n\n"
            "The bot will generate a shareable link.\n"
            "Users must join both channels to access it."
        )
        return

    video = message.reply_to_message.video
    caption = message.text.replace("/video", "", 1).strip()
    if not caption:
        caption = "🎬 Premium Video Content"

    video_id = str(uuid.uuid4())[:8]

    bot_data["videos"][video_id] = {
        "file_id": video.file_id,
        "caption": caption,
        "duration": video.duration,
        "file_size": video.file_size,
        "file_name": video.file_name or "video.mp4",
        "added_date": datetime.now().isoformat()
    }
    save_data()

    bot_username = (await app.get_me()).username
    video_link = f"https://t.me/{bot_username}?start={video_id}"

    await message.reply_text(
        f"**✅ VIDEO ADDED SUCCESSFULLY ✅**\n\n"
        f"**Video ID:** `{video_id}`\n"
        f"**Caption:** {caption}\n"
        f"**Duration:** {video.duration} seconds\n"
        f"**Size:** {video.file_size / (1024 * 1024):.1f} MB\n\n"
        f"**🔗 Share this link with users:**\n"
        f"`{video_link}`\n\n"
        f"**⏰ Auto-delete:** {DELETE_AFTER_MINUTES} minutes\n"
        f"**🔒 Protection:** Channel join required\n\n"
        f"**📊 Use /stats to see analytics**"
    )


# ----- /stats — Owner analytics -----
@app.on_message(filters.command("stats") & filters.private)
async def stats_command(client: Client, message: Message):
    user_id = message.from_user.id

    if user_id != OWNER_ID:
        await message.reply_text("**❌ Unauthorized. This command is for the bot owner only.**")
        return

    users = bot_data.get("users", {})
    videos = bot_data.get("videos", {})
    stats = bot_data.get("stats", {})

    now = datetime.now()
    active_24h = 0
    today_users = 0
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    for uid, uinfo in users.items():
        last_active = uinfo.get("last_active", "")
        try:
            last_dt = datetime.fromisoformat(last_active)
            if (now - last_dt).total_seconds() < 86400:
                active_24h += 1
            if last_dt >= today_start:
                today_users += 1
        except:
            pass

    video_watch_count = {}
    for uid, uinfo in users.items():
        for vid in uinfo.get("videos_watched", []):
            video_watch_count[vid] = video_watch_count.get(vid, 0) + 1

    most_watched_id = max(video_watch_count, key=video_watch_count.get) if video_watch_count else None
    most_watched_count = video_watch_count.get(most_watched_id, 0) if most_watched_id else 0

    most_watched_caption = "N/A"
    if most_watched_id and most_watched_id in videos:
        most_watched_caption = videos[most_watched_id].get("caption", "N/A")[:30]

    stats_msg = (
        "**📊 BOT ANALYTICS DASHBOARD 📊**\n\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "**👥 USER STATISTICS**\n"
        f"• **Total Users:** `{len(users)}`\n"
        f"• **Active (24h):** `{active_24h}`\n"
        f"• **New Today:** `{today_users}`\n\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "**🎬 VIDEO STATISTICS**\n"
        f"• **Total Videos:** `{len(videos)}`\n"
        f"• **Total Views:** `{stats.get('total_videos_sent', 0)}`\n"
        f"• **Avg Views/Video:** `{stats.get('total_videos_sent', 0) / max(len(videos), 1):.1f}`\n\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "**🏆 MOST WATCHED VIDEO**\n"
        f"• **ID:** `{most_watched_id or 'N/A'}`\n"
        f"• **Caption:** {most_watched_caption}\n"
        f"• **Views:** `{most_watched_count}`\n\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "**✅ VERIFICATION STATS**\n"
        f"• **Successful:** `{stats.get('total_verified', 0)}`\n"
        f"• **Rejected:** `{stats.get('total_rejected', 0)}`\n"
        f"• **Rate:** `{stats.get('total_verified', 0) / max(stats.get('total_verified', 0) + stats.get('total_rejected', 0), 1) * 100:.1f}%`"
    )

    await message.reply_text(stats_msg)


# ----- /users — List all users (Owner only) -----
@app.on_message(filters.command("users") & filters.private)
async def users_command(client: Client, message: Message):
    user_id = message.from_user.id

    if user_id != OWNER_ID:
        await message.reply_text("**❌ Unauthorized.**")
        return

    users = bot_data.get("users", {})
    if not users:
        await message.reply_text("**No users registered yet.**")
        return

    user_list = []
    for uid, uinfo in users.items():
        name = uinfo.get("first_name", "Unknown")
        uname = uinfo.get("username", "")
        last_active = uinfo.get("last_active", "")[:10]
        user_list.append(f"• `{uid}` — {name} (@{uname}) — Last: {last_active}")

    chunks = [user_list[i:i+30] for i in range(0, len(user_list), 30)]
    for i, chunk in enumerate(chunks):
        text = f"**📋 Registered Users ({len(users)} total)**\n\n" + "\n".join(chunk)
        await message.reply_text(text)


# ----- /broadcast — Send message to all users (Owner only) -----
@app.on_message(filters.command("broadcast") & filters.private)
async def broadcast_command(client: Client, message: Message):
    user_id = message.from_user.id

    if user_id != OWNER_ID:
        await message.reply_text("**❌ Unauthorized.**")
        return

    if not message.reply_to_message:
        await message.reply_text("**Reply to a message with /broadcast to send it to all users.**")
        return

    users = bot_data.get("users", {})
    sent = 0
    failed = 0

    status_msg = await message.reply_text(f"**📢 Broadcasting to {len(users)} users...**")

    for uid in users:
        try:
            await message.reply_to_message.copy(chat_id=int(uid))
            sent += 1
            await asyncio.sleep(0.05)  # Rate limit protection
        except Exception as e:
            failed += 1
            logger.warning(f"Broadcast failed to {uid}: {e}")

    await status_msg.edit_text(
        f"**📢 Broadcast Complete!**\n\n"
        f"• **Sent:** `{sent}`\n"
        f"• **Failed:** `{failed}`\n"
        f"• **Total:** `{len(users)}`"
    )


# ============================================================
# MAIN FUNCTION
# ============================================================

async def main():
    logger.info("=" * 50)
    logger.info("🚀 Starting Video Monetization Bot...")

    # Start health server
    asyncio.create_task(run_health_server())

    # Start bot
await app.start()
me = await app.get_me()
logger.info(f"BOT USERNAME = @{me.username}")
logger.info(f"✅ Bot started: @{app.me.username}")
logger.info("🔄 Bot is running. Waiting for messages...")

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
