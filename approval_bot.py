"""
Onay Botu (Telegram)
--------------------
Her yeni bildirim için sana şunu gönderir:

  📋 [Taslak post]
  [✅ Onayla] [✏️ Düzenle] [⏭ Geç]

Onayla  → Telegram kanalına + X'e (açıksa) gönderir
Düzenle → Düzenleme metni bekler, sonra yeniden sorar
Geç     → Bildirim görmezden gelinir
"""

import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from config import TELEGRAM_BOT_TOKEN, TELEGRAM_ADMIN_CHAT_ID
from publisher import publish_to_telegram, publish_to_x

logger = logging.getLogger(__name__)

# Bekleyen onay kuyrukları: chat_id → list[dict]
_pending: dict[int, list[dict]] = {}
# Düzenleme bekleniyor mu?
_awaiting_edit: dict[int, dict] = {}


# ---------------------------------------------------------------------------
# Komutlar
# ---------------------------------------------------------------------------

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "KAP Radar botu aktif.\n"
        "/pending → bekleyen bildirimleri göster\n"
        "/status  → durum bilgisi"
    )


async def cmd_pending(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    queue = _pending.get(TELEGRAM_ADMIN_CHAT_ID, [])
    if not queue:
        await update.message.reply_text("Bekleyen bildirim yok.")
    else:
        await update.message.reply_text(f"{len(queue)} bildirim onay bekliyor.")


async def cmd_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    queue = _pending.get(TELEGRAM_ADMIN_CHAT_ID, [])
    await update.message.reply_text(
        f"Kuyruk: {len(queue)} bildirim\nBot çalışıyor."
    )


# ---------------------------------------------------------------------------
# Onay akışı
# ---------------------------------------------------------------------------

async def send_approval_request(app: Application, item: dict) -> None:
    """
    Admin'e taslak postu ve onay butonlarını gönderir.
    item: {'disclosure': ..., 'post_text': str, 'label': str}
    """
    post_text = item["post_text"]
    disc_id   = item["disclosure"]["id"]
    ticker    = item["disclosure"].get("ticker", "?")

    msg_text = (
        f"🆕 *{ticker}* — yeni bildirim\n\n"
        f"```\n{post_text}\n```\n\n"
        f"_Onay, düzenleme veya geçme için butonları kullan._"
    )

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Onayla",   callback_data=f"approve|{disc_id}"),
            InlineKeyboardButton("✏️ Düzenle",  callback_data=f"edit|{disc_id}"),
            InlineKeyboardButton("⏭ Geç",       callback_data=f"skip|{disc_id}"),
        ]
    ])

    try:
        await app.bot.send_message(
            chat_id=TELEGRAM_ADMIN_CHAT_ID,
            text=msg_text,
            parse_mode="Markdown",
            reply_markup=keyboard,
        )
        # Kuyruğa ekle
        _pending.setdefault(TELEGRAM_ADMIN_CHAT_ID, []).append(item)
    except Exception as exc:
        logger.error("Onay mesajı gönderilemedi: %s", exc)


async def callback_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    action, disc_id = query.data.split("|", 1)
    queue = _pending.get(TELEGRAM_ADMIN_CHAT_ID, [])

    # Kuyruğu ara
    item = next((i for i in queue if i["disclosure"]["id"] == disc_id), None)

    if action == "approve":
        if item:
            await _do_publish(ctx.application, item, query)
            queue.remove(item)
        else:
            await query.edit_message_text("Bu bildirim artık kuyrukta yok.")

    elif action == "edit":
        if item:
            _awaiting_edit[TELEGRAM_ADMIN_CHAT_ID] = item
            queue.remove(item)
            await query.edit_message_text(
                f"✏️ Düzenlenmiş metni gönder:\n\n```\n{item['post_text']}\n```",
                parse_mode="Markdown",
            )
        else:
            await query.edit_message_text("Bu bildirim artık kuyrukta yok.")

    elif action == "skip":
        if item:
            queue.remove(item)
        await query.edit_message_text("⏭ Bildirim geçildi.")


async def _do_publish(app: Application, item: dict, query=None) -> None:
    post_text = item["post_text"]
    tg_ok  = await publish_to_telegram(app, post_text)
    x_ok   = publish_to_x(post_text)

    status_parts = []
    if tg_ok:  status_parts.append("📢 Telegram kanalı")
    if x_ok:   status_parts.append("🐦 X")
    published = " + ".join(status_parts) if status_parts else "Hiçbir platform"

    msg = f"✅ Yayınlandı → {published}"
    if query:
        await query.edit_message_text(msg)
    else:
        await app.bot.send_message(chat_id=TELEGRAM_ADMIN_CHAT_ID, text=msg)


async def edit_message_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Kullanıcı düzenleme metni gönderdiğinde yakala."""
    if update.effective_chat.id != TELEGRAM_ADMIN_CHAT_ID:
        return

    item = _awaiting_edit.pop(TELEGRAM_ADMIN_CHAT_ID, None)
    if item is None:
        return  # beklenen düzenleme yok, normal mesaj

    item["post_text"] = update.message.text.strip()

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Onayla",    callback_data=f"approve|{item['disclosure']['id']}"),
            InlineKeyboardButton("⏭ Geç",        callback_data=f"skip|{item['disclosure']['id']}"),
        ]
    ])
    _pending.setdefault(TELEGRAM_ADMIN_CHAT_ID, []).append(item)

    await update.message.reply_text(
        f"Güncellenmiş taslak:\n\n```\n{item['post_text']}\n```\nOnaylıyor musun?",
        parse_mode="Markdown",
        reply_markup=keyboard,
    )


# ---------------------------------------------------------------------------
# Uygulama fabrikası
# ---------------------------------------------------------------------------

def build_app() -> Application:
    app = (
        Application.builder()
        .token(TELEGRAM_BOT_TOKEN)
        .build()
    )
    app.add_handler(CommandHandler("start",   cmd_start))
    app.add_handler(CommandHandler("pending", cmd_pending))
    app.add_handler(CommandHandler("status",  cmd_status))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND & filters.Chat(TELEGRAM_ADMIN_CHAT_ID),
            edit_message_handler,
        )
    )
    return app
