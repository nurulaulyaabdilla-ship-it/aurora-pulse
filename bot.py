"""
Aurora Pulse - Telegram bot (aiogram 3.x)
Fungsi: /start membuka Mini App, mencatat referral 1 level, menu tombol, /invite, /help.
Jalankan: python bot.py
"""
import asyncio
import html
import logging
import os
import re
import sqlite3

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import (
    BotCommand,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    MenuButtonWebApp,
    Message,
    WebAppInfo,
)
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
WEBAPP_URL = os.getenv("WEBAPP_URL", "")        # wajib HTTPS
CHANNEL_URL = os.getenv("CHANNEL_URL", "")      # opsional, mis. https://t.me/auroracahaya
ADMIN_ID = int(os.getenv("ADMIN_ID", "0") or 0) # opsional, untuk /stats
DB_PATH = os.getenv("DB_PATH", "aurora.db")

if not BOT_TOKEN:
    raise SystemExit("BOT_TOKEN belum diisi di .env")
if not WEBAPP_URL.startswith("https://"):
    raise SystemExit("WEBAPP_URL harus diawali https:// (syarat Telegram Mini App)")

bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
_username_cache: dict[str, str] = {}


# ---------- Database (SQLite sederhana; ganti ke PostgreSQL saat backend dibuat) ----------
def db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with db() as c:
        c.execute(
            """CREATE TABLE IF NOT EXISTS users(
                tg_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                ref_by INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP)"""
        )


def register(user, ref_by: int | None) -> tuple[bool, int | None]:
    """Daftarkan user. Return (user_baru, referrer_valid)."""
    with db() as c:
        if c.execute("SELECT 1 FROM users WHERE tg_id=?", (user.id,)).fetchone():
            return False, None
        valid_ref = None
        if ref_by and ref_by != user.id:
            if c.execute("SELECT 1 FROM users WHERE tg_id=?", (ref_by,)).fetchone():
                valid_ref = ref_by
        c.execute(
            "INSERT INTO users(tg_id, username, first_name, ref_by) VALUES(?,?,?,?)",
            (user.id, user.username, user.first_name, valid_ref),
        )
        return True, valid_ref


# ---------- Helper ----------
async def bot_username() -> str:
    if "u" not in _username_cache:
        _username_cache["u"] = (await bot.get_me()).username
    return _username_cache["u"]


async def invite_link(user_id: int) -> str:
    return f"https://t.me/{await bot_username()}?start=ref_{user_id}"


def open_kb(extra_rows: list[list[InlineKeyboardButton]] | None = None) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text="🌌 Buka Aurora Pulse", web_app=WebAppInfo(url=WEBAPP_URL))]]
    if extra_rows:
        rows += extra_rows
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def welcome_kb(user_id: int) -> InlineKeyboardMarkup:
    link = await invite_link(user_id)
    share = (
        "https://t.me/share/url?url=" + link
        + "&text=Ayo%20main%20Aurora%20Pulse%20bareng%20aku!%20Kita%20sama-sama%20dapat%20bonus%20%F0%9F%8C%8C"
    )
    row = [InlineKeyboardButton(text="👥 Ajak Teman", url=share)]
    if CHANNEL_URL:
        row.insert(0, InlineKeyboardButton(text="📣 Channel", url=CHANNEL_URL))
    return open_kb([row])


# ---------- Handler ----------
@dp.message(CommandStart())
async def cmd_start(m: Message, command: CommandObject):
    ref = None
    if command.args:
        match = re.fullmatch(r"ref_(\d+)", command.args.strip())
        if match:
            ref = int(match.group(1))

    is_new, referrer = register(m.from_user, ref)

    name = html.escape(m.from_user.first_name or "Teman")
    text = (
        f"✨ <b>Halo, {name}!</b>\n\n"
        "Selamat datang di <b>Aurora Pulse</b> 🌌\n"
        "Bersama <b>Lumi</b>, si rubah aurora, kumpulkan poin, selesaikan misi, "
        "naikkan level, dan ikut undian hadiah mingguan.\n\n"
        "🎁 Klaim poin tiap beberapa jam\n"
        "🎯 Misi &amp; check-in harian\n"
        "👥 Ajak teman: kalian sama-sama dapat bonus\n"
        "🏆 Papan peringkat &amp; skin langit\n\n"
        "<i>Poin tidak dijamin bernilai uang. Hadiah berasal dari undian &amp; "
        "penukaran dengan syarat yang tertulis di dalam aplikasi.</i>\n\n"
        "Tekan tombol di bawah untuk mulai 👇"
    )
    if is_new and referrer:
        text = "🎉 Kamu bergabung lewat undangan teman, bonus akan dicatat!\n\n" + text

    await m.answer(text, reply_markup=await welcome_kb(m.from_user.id))

    if is_new and referrer:
        try:
            await bot.send_message(
                referrer,
                f"👥 <b>{name}</b> bergabung lewat link undanganmu! "
                "Buka Aurora Pulse untuk melihat bonusnya.",
                reply_markup=open_kb(),
            )
        except Exception as e:  # user mungkin memblokir bot
            logging.info("Gagal notifikasi referrer %s: %s", referrer, e)


@dp.message(Command("app"))
async def cmd_app(m: Message):
    await m.answer("Siap main? 🌌", reply_markup=open_kb())


@dp.message(Command("invite"))
async def cmd_invite(m: Message):
    link = await invite_link(m.from_user.id)
    await m.answer(
        "👥 <b>Ajak teman &amp; dapat bonus</b>\n"
        "Kamu dan temanmu masing-masing dapat bonus tetap (1 level, tanpa bonus berjenjang).\n\n"
        f"Link kamu:\n<code>{link}</code>",
        reply_markup=open_kb(),
    )


@dp.message(Command("help"))
async def cmd_help(m: Message):
    await m.answer(
        "<b>Perintah</b>\n"
        "/start - mulai &amp; buka aplikasi\n"
        "/app - buka Aurora Pulse\n"
        "/invite - dapatkan link undangan\n"
        "/help - bantuan",
        reply_markup=open_kb(),
    )


@dp.message(Command("stats"))
async def cmd_stats(m: Message):
    if not ADMIN_ID or m.from_user.id != ADMIN_ID:
        return
    with db() as c:
        total = c.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        refs = c.execute("SELECT COUNT(*) FROM users WHERE ref_by IS NOT NULL").fetchone()[0]
    await m.answer(f"📊 Total user: <b>{total}</b>\nDari referral: <b>{refs}</b>")


@dp.message(F.text & ~F.text.startswith("/"))
async def fallback(m: Message):
    await m.answer("Tekan tombol di bawah untuk membuka Aurora Pulse 🌌", reply_markup=open_kb())


# ---------- Startup ----------
async def on_startup() -> None:
    await bot.set_my_commands(
        [
            BotCommand(command="start", description="Mulai & buka aplikasi"),
            BotCommand(command="app", description="Buka Aurora Pulse"),
            BotCommand(command="invite", description="Link undangan teman"),
            BotCommand(command="help", description="Bantuan"),
        ]
    )
    # Tombol menu di samping kolom ketik juga membuka Mini App
    await bot.set_chat_menu_button(
        menu_button=MenuButtonWebApp(text="Main", web_app=WebAppInfo(url=WEBAPP_URL))
    )
    logging.info("Bot siap: @%s", await bot_username())


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    init_db()
    dp.startup.register(on_startup)
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
