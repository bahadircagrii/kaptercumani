import logging
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

_pending = {}
_awaiting_edit = {}


async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "KAP Radar botu aktif.\n/pending - bekleyen bildirimler\n/status - durum"
    )


async def cmd_pending(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    queue = _pending.get(TELEGRAM_ADMIN_CHAT_ID, [])
    await update.message.reply_text(
        f"Bekleyen bildirim: {len(queue)}" if queue else "Bekleyen bildirim yok."
    )


async def cmd_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    queue = _pending.get(TELEGRAM_ADMIN_CHAT_ID, [])
    await update.message.reply_text(f"Bot calisiyor. Kuyruk: {len(queue)} bildirim.")


async def send_approval_request(app: Application, item: dict) -> None:
    post_text = item["post_text"]
    disc_id   = item["disclosure"]["id"]
    ticker    = item["disclosure"].get("ticker", "?")

    msg = f"*{ticker}* — yeni bildirim\n\n```\n{post_text}\n```"
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("Onayla", callback_data=f"approve|{disc_id}"),
        InlineKeyboardButton("Duzenle", callback_data=f"edit|{disc_id}"),
        InlineKeyboardButton("Gec",    callback_data=f"skip|{disc_id}"),
    ]])

    try:
        await app.bot.send_message(
            chat_id=TELEGRAM_ADMIN_CHAT_ID,
            text=msg,
            parse_mode="Markdown",
            reply_markup=keyboard,
        )
        _pending.setdefault(TELEGRAM_ADMIN_CHAT_ID, []).append(item)
    except Exception as exc:
        logger.error("Onay mesaji gonderilemedi: %s", exc)


async def callback_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    action, disc_id = query.data.split("|", 1)
    queue = _pending.get(TELEGRAM_ADMIN_CHAT_ID, [])
    item  = next((i for i in queue if i["disclosure"]["id"] == disc_id), None)

    if action == "approve":
        if item:
            queue.remove(item)
            tg_ok = await publish_to_telegram(ctx.application, item["post_text"])
            x_ok  = publish_to_x(item["post_text"])
            hedef = []
            if tg_ok: hedef.append("Telegram")
            if x_ok:  hedef.append("X")
            await query.edit_message_text(
                f"Yayinlandi: {' + '.join(hedef) or 'hata'}"
            )
        else:
            await query.edit_message_text("Bu bildirim artik kuyrukta yok.")

    elif action == "edit":
        if item:
            queue.remove(item)
            _awaiting_edit[TELEGRAM_ADMIN_CHAT_ID] = item
            await query.edit_message_text(
                f"Yeni metni gonder:\n\n```\n{item['post_text']}\n```",
                parse_mode="Markdown",
            )
        else:
            await query.edit_message_text("Bu bildirim artik kuyrukta yok.")

    elif action == "skip":
        if item:
            queue.remove(item)
        await query.edit_message_text("Bildirim gecildi.")


async def edit_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != TELEGRAM_ADMIN_CHAT_ID:
        return
    item = _awaiting_edit.pop(TELEGRAM_ADMIN_CHAT_ID, None)
    if item is None:
        return
    item["post_text"] = update.message.text.strip()
    _pending.setdefault(TELEGRAM_ADMIN_CHAT_ID, []).append(item)
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("Onayla", callback_data=f"approve|{item['disclosure']['id']}"),
        InlineKeyboardButton("Gec",    callback_data=f"skip|{item['disclosure']['id']}"),
    ]])
    await update.message.reply_text(
        f"Guncellendi:\n\n```\n{item['post_text']}\n```",
        parse_mode="Markdown",
        reply_markup=keyboard,
    )


def build_app() -> Application:
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start",   cmd_start))
    app.add_handler(CommandHandler("pending", cmd_pending))
    app.add_handler(CommandHandler("status",  cmd_status))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.Chat(TELEGRAM_ADMIN_CHAT_ID),
        edit_handler,
    ))
    return app
