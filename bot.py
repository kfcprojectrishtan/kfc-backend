"""
bot.py — Telegram Admin + Courier Bot + OTP
python-telegram-bot 21.x

✅ Admin:
  - pending → confirmed → cooking → ready
  - pending dan cancelled
  - 📞 Call + 📍 Maps tugmalar
✅ Courier:
  - ready → delivering → done
  - 📞 Call + 📍 Maps tugmalar
✅ User notify:
  - confirmed / ready / delivering / done / cancelled
✅ Coin + Review:
  - done bo'lganda userga 5% coin (har 1000 UZS = 1 coin, min 1)
  - done bo'lganda "⭐ Izoh qoldirish" tugmasi
✅ OTP:
  - send_otp(chat_id, code)
"""

import os
from typing import Optional
from urllib.parse import quote_plus

from telegram import (
    Update,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

import database as db


# ═══════════════════════════════════════════════════════════════
# STATUS + FLOW
# ═══════════════════════════════════════════════════════════════

STATUS = {
    "pending":    ("🕐", "Kutilmoqda"),
    "confirmed":  ("✅", "Tasdiqlandi"),
    "cooking":    ("🍗", "Tayyorlanmoqda"),
    "ready":      ("📦", "Kuryer kutmoqda"),
    "delivering": ("🚗", "Yetkazilmoqda"),
    "done":       ("🎉", "Yetkazildi"),
    "cancelled":  ("❌", "Bekor qilindi"),
}

FLOW = ["pending", "confirmed", "cooking", "ready", "delivering", "done"]
TERMINAL = {"done", "cancelled"}

PAYMENT_MAP = {"naqt": "💵 Naqt", "card": "💳 Karta"}


def _is_admin(chat_id: int) -> bool:
    return str(chat_id) == str(os.getenv("ADMIN_CHAT_ID", ""))


def _is_courier(chat_id: int) -> bool:
    return str(chat_id) == str(os.getenv("COURIER_CHAT_ID", ""))


def _can_move(old: str, new: str) -> bool:
    """Bot darajasida status flow tekshiruvi."""
    if old == new:
        return True
    if old in TERMINAL:
        return False
    if new == "cancelled":
        return old == "pending"
    if old not in FLOW or new not in FLOW:
        return True
    return FLOW.index(new) >= FLOW.index(old)


def _maps_url(address: str) -> str:
    return f"https://www.google.com/maps/search/?api=1&query={quote_plus(address or '')}"


def _tel_url(phone: str) -> str:
    p = (phone or "").strip().replace(" ", "").replace("-", "")
    if not p.startswith("+"):
        p = "+" + p
    return f"https://t.me/+{p.lstrip('+')}"


# ═══════════════════════════════════════════════════════════════
# USER NOTIFY (phone -> chat_id)
# ═══════════════════════════════════════════════════════════════

async def notify_user(
    ctx: ContextTypes.DEFAULT_TYPE,
    phone: str,
    text: str,
    reply_markup=None,
):
    """Telefon orqali chat_id topib userga xabar yuboradi."""
    try:
        tg_user = db.get_telegram_user(phone)
        if not tg_user or not tg_user.get("chat_id"):
            return
        await ctx.bot.send_message(
            chat_id=int(tg_user["chat_id"]),
            text=text,
            parse_mode="HTML",
            reply_markup=reply_markup,
        )
    except Exception as e:
        print(f"notify_user xato ({phone}): {e}")


# ═══════════════════════════════════════════════════════════════
# ORDER MESSAGE (Admin/Courier uchun format)
# ═══════════════════════════════════════════════════════════════

def build_order_message(order: dict, title: str = "Yangi zakaz") -> str:
    order_id = order.get("id", "—")
    address  = order.get("address", "—")
    items    = order.get("items") or []
    total    = int(order.get("total", 0) or 0)

    lines = []
    for i in items:
        name  = i.get("fullName") or i.get("name") or "—"
        qty   = int(i.get("quantity", 0) or 0)
        price = int(i.get("price", 0) or 0)
        lines.append(f"  • {name} x {qty} — {price * qty:,} UZS")
    items_text = "\n".join(lines) if lines else "  • —"

    payment_key = (order.get("payment") or "naqt").strip().lower()
    payment = PAYMENT_MAP.get(payment_key, "💵 Naqt")

    customer = order.get("customer_name", "") or ""
    phone    = order.get("phone", "—") or "—"
    extra_phone = order.get("extra_phone") or ""
    comment     = order.get("comment") or ""

    created = order.get("created_at") or ""
    created_view = created[:16].replace("T", " ") if created else "—"

    status = order.get("status", "pending")
    emoji, label = STATUS.get(status, ("🕐", status))

    coins_used = int(order.get("coins_used", 0) or 0)
    coins_text = ""
    if coins_used > 0:
        discount = coins_used * 1000
        coins_text = f"🪙 <b>Koinlar (chegirma):</b> -{discount:,} UZS ({coins_used} koin)\n"

    text = (
        f"🛒 <b>{title} #{order_id}</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"📍 <b>Manzil:</b> {address}\n\n"
        f"🍽 <b>Tarkib:</b>\n{items_text}\n\n"
        f"{coins_text}"
        f"💳 <b>Jami (to'lanishi kerak):</b> <b><u>{total:,} UZS</u></b>\n"
        f"💰 <b>To'lov:</b> {payment}\n"
        f"👤 <b>Mijoz:</b> {customer}\n"
        f"📞 <b>Telefon:</b> {phone}\n"
    )

    if extra_phone:
        text += f"📱 <b>Qo'sh. tel:</b> {extra_phone}\n"
    if comment:
        text += f"💬 <b>Izoh:</b> {comment}\n"

    text += (
        f"⏰ <b>Vaqt:</b> {created_view}\n\n"
        f"{emoji} <b>Status:</b> {label}"
    )
    return text
  
# ═══════════════════════════════════════════════════════════════
# KEYBOARDS (Admin/Courier)
# ═══════════════════════════════════════════════════════════════

def admin_keyboard(order: dict) -> InlineKeyboardMarkup:
    order_id = order.get("id", "")
    status   = order.get("status", "pending")

    address = order.get("address", "")
    phone   = order.get("phone", "")

    rows = [
        [
            InlineKeyboardButton("📞 Call", url=_tel_url(phone)),
            InlineKeyboardButton("📍 Maps", url=_maps_url(address)),
        ]
    ]

    if status == "pending":
        rows.append([
            InlineKeyboardButton("✅ Tasdiqlash",   callback_data=f"status:{order_id}:confirmed"),
            InlineKeyboardButton("❌ Bekor qilish", callback_data=f"status:{order_id}:cancelled"),
        ])
    elif status == "confirmed":
        rows.append([
            InlineKeyboardButton("🍗 Tayyorlanmoqda", callback_data=f"status:{order_id}:cooking"),
            InlineKeyboardButton("❌ Bekor qilish",   callback_data=f"status:{order_id}:cancelled"),
        ])
    elif status == "cooking":
        rows.append([
            InlineKeyboardButton("📦 Ovqat tayyor", callback_data=f"status:{order_id}:ready"),
        ])
    # ready/delivering/done/cancelled — admin tugma kerak emas

    return InlineKeyboardMarkup(rows)


def courier_keyboard(order: dict) -> InlineKeyboardMarkup:
    order_id = order.get("id", "")
    status   = order.get("status", "ready")

    address = order.get("address", "")
    phone   = order.get("phone", "")

    rows = [
        [
            InlineKeyboardButton("📞 Call", url=_tel_url(phone)),
            InlineKeyboardButton("📍 Maps", url=_maps_url(address)),
        ]
    ]

    if status == "ready":
        rows.append([InlineKeyboardButton("🚗 Yetkazilmoqda", callback_data=f"courier:{order_id}:delivering")])
    elif status == "delivering":
        rows.append([InlineKeyboardButton("✅ Yetkazildi", callback_data=f"courier:{order_id}:done")])

    return InlineKeyboardMarkup(rows)


def review_keyboard(order_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("⭐ Izoh qoldirish", callback_data=f"review:{order_id}")
    ]])


# ═══════════════════════════════════════════════════════════════
# GLOBAL APP INSTANCE (main.py dan chaqirish uchun)
# ═══════════════════════════════════════════════════════════════

_app_instance: Optional[Application] = None


def _get_app() -> Optional[Application]:
    return _app_instance


# ═══════════════════════════════════════════════════════════════
# NOTIFY (main.py dan chaqiriladi)
# ═══════════════════════════════════════════════════════════════

async def notify_new_order(order: dict):
    app = _get_app()
    if not app:
        return

    admin_id = os.getenv("ADMIN_CHAT_ID")
    if not admin_id:
        print("⚠️ ADMIN_CHAT_ID o'rnatilmagan!")
        return

    try:
        msg = await app.bot.send_message(
            chat_id=int(admin_id),
            text=build_order_message(order, title="Yangi zakaz"),
            parse_mode="HTML",
            reply_markup=admin_keyboard(order),
        )
        try:
            db.update_tg_msg_id(order["id"], msg.message_id)
        except Exception:
            pass
    except Exception as e:
        print(f"notify_new_order xato: {e}")


async def notify_cancelled(order: dict):
    app = _get_app()
    if not app:
        return

    admin_id = os.getenv("ADMIN_CHAT_ID")
    if not admin_id:
        return

    try:
        await app.bot.send_message(
            chat_id=int(admin_id),
            text=(
                f"❌ <b>Zakaz bekor qilindi #{order.get('id','—')}</b>\n"
                f"💳 {int(order.get('total',0) or 0):,} UZS\n"
                f"👤 {order.get('customer_name','')} {order.get('phone','')}"
            ),
            parse_mode="HTML",
        )
    except Exception as e:
        print(f"notify_cancelled xato: {e}")


async def send_otp(chat_id: int, code: str):
    app = _get_app()
    if not app:
        raise RuntimeError("Bot instance mavjud emas — create_app() chaqirilmagan")

    await app.bot.send_message(
        chat_id=chat_id,
        text=(
            f"🔐 <b>KFC Riston — Tasdiqlash kodi</b>\n\n"
            f"Sizning kodingiz: <code>{code}</code>\n\n"
            f"⏱ Kod 5 daqiqa ichida amal qiladi.\n"
            f"Kodni hech kimga bermang!"
        ),
        parse_mode="HTML",
    )


# ═══════════════════════════════════════════════════════════════
# /start
# ═══════════════════════════════════════════════════════════════

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    if _is_admin(chat_id):
        kb = ReplyKeyboardMarkup([["📊 Statistika"]], resize_keyboard=True)
        await update.message.reply_text(
            f"👋 <b>KFC Admin Bot</b>\n\nChat ID: <code>{chat_id}</code>",
            parse_mode="HTML",
            reply_markup=kb,
        )
        return

    if _is_courier(chat_id):
        await update.message.reply_text(
            "🚗 <b>Kuryer panel</b>\n\nTayyor zakazlar shu yerga keladi.",
            parse_mode="HTML",
        )
        return

    # User: ro'yxatdan o'tganmi?
    existing = db.get_telegram_user_by_chat_id(str(chat_id))
    if existing:
        website = os.getenv("WEBSITE_URL", "https://kfs-menu.vercel.app/")
        first = (existing.get("full_name") or "").split()[0] or "do'st"
        await update.message.reply_text(
            f"👋 <b>Salom, {first}!</b>\n\n"
            f"📱 Raqamingiz saqlangan: <code>{existing.get('phone','')}</code>\n\n"
            f"Buyurtma berish uchun saytni oching:",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🍗 Ochish / Открыть", url=website)
            ]]),
        )
        return

    keyboard = ReplyKeyboardMarkup(
        [[KeyboardButton("📱 Telefon raqamni yuborish", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )
    await update.message.reply_text(
        "👋 <b>KFC Riston</b> ga xush kelibsiz! 🍗\n\n"
        "Ro'yxatdan o'tish uchun telefon raqamingizni yuboring.\n\n"
        "⬇️ Pastdagi tugmani bosing:",
        parse_mode="HTML",
        reply_markup=keyboard,
    )


# ═══════════════════════════════════════════════════════════════
# Contact handler
# ═══════════════════════════════════════════════════════════════

async def handle_contact(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    contact = update.message.contact
    chat_id = update.effective_chat.id

    if contact.user_id and contact.user_id != update.effective_user.id:
        await update.message.reply_text(
            "❌ Iltimos, faqat <b>o'z raqamingizni</b> yuboring.",
            parse_mode="HTML",
        )
        return

    phone = (contact.phone_number or "").replace("+", "").replace(" ", "")
    if not phone.startswith("998"):
        phone = "998" + phone[-9:]
    phone = "+" + phone

    website = os.getenv("WEBSITE_URL", "https://kfs-menu.vercel.app/")

    rm = await update.message.reply_text("⏳", reply_markup=ReplyKeyboardRemove())
    try:
        await rm.delete()
    except Exception:
        pass

    existing = db.get_telegram_user_by_chat_id(str(chat_id))
    if existing:
        first = (existing.get("full_name") or contact.first_name or "do'st").split()[0]
        await update.message.reply_text(
            f"👋 <b>Salom, {first}!</b>\n\n"
            f"📱 Raqamingiz allaqachon saqlangan: <code>{existing.get('phone','')}</code>\n\n"
            f"Buyurtma berish uchun saytni oching:",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🍗 Ochish / Открыть", url=website)
            ]]),
        )
        return

    full_name = " ".join(filter(None, [contact.first_name, contact.last_name or ""])).strip()
    db.save_telegram_user(phone=phone, chat_id=str(chat_id), full_name=full_name)

    await update.message.reply_text(
        "✅ <b>Raqam saqlandi!</b>\n\nBuyurtma berish uchun tugmani bosing ⬇️",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🍗 Ochish / Открыть", url=website)
        ]]),
    )


# ═══════════════════════════════════════════════════════════════
# Admin callback: status:order_id:new_status
# ═══════════════════════════════════════════════════════════════

async def handle_admin_status_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data or ""

    if not _is_admin(update.effective_chat.id):
        await query.answer("❌ Ruxsat yo'q", show_alert=True)
        return

    if not data.startswith("status:"):
        return

    _, order_id, new_status = data.split(":", 2)

    order = db.get_by_id(order_id)
    if not order:
        await query.answer("❌ Zakaz topilmadi", show_alert=True)
        return

    old_status = order.get("status", "pending")
    if not _can_move(old_status, new_status):
        await query.answer("⚠️ Status ketma-ketligi xato", show_alert=True)
        return

    updated = db.update_status(order_id, new_status)
    if not updated:
        await query.answer("❌ Yangilab bo'lmadi", show_alert=True)
        return

    # admin message update
    try:
        await query.edit_message_text(
            text=build_order_message(updated, title="Yangi zakaz"),
            parse_mode="HTML",
            reply_markup=admin_keyboard(updated),
        )
    except Exception as e:
        print(f"Admin message update xato: {e}")

    emoji, label = STATUS.get(new_status, ("✅", new_status))
    await query.answer(f"{emoji} {label}")

    phone = updated.get("phone")

    # ✅ User notify (confirmed / ready)
    if new_status == "confirmed" and phone:
        await notify_user(
            ctx, phone,
            f"✅ <b>Buyurtmangiz tasdiqlandi!</b>\n\n"
            f"📦 Buyurtma: <b>#{order_id}</b>\n"
            f"💰 Summa: <b>{int(updated.get('total',0) or 0):,} UZS</b>\n\n"
            f"🍗 Tayyorlanmoqda, tez orada yetkazamiz!"
        )

    if new_status == "ready":
        # courierga yuborish
        courier_id = os.getenv("COURIER_CHAT_ID", "")
        if courier_id:
            try:
                await ctx.bot.send_message(
                    chat_id=int(courier_id),
                    text=build_order_message({**updated, "status": "ready"}, title="Yetkazish"),
                    parse_mode="HTML",
                    reply_markup=courier_keyboard({**updated, "status": "ready"}),
                )
            except Exception as e:
                print(f"Courierga yuborishda xato: {e}")

        # userga ham notify
        if phone:
            await notify_user(
                ctx, phone,
                f"📦 <b>Buyurtmangiz tayyor!</b>\n\n"
                f"📦 Zakaz: <b>#{order_id}</b>\n"
                f"🚗 Kuryer tez orada yo'lga chiqadi."
            )


# ═══════════════════════════════════════════════════════════════
# Courier callback: courier:order_id:action
# ═══════════════════════════════════════════════════════════════

async def courier_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data or ""

    if not _is_courier(update.effective_chat.id):
        await query.answer("❌ Ruxsat yo'q", show_alert=True)
        return

    if not data.startswith("courier:"):
        return

    await query.answer()
    _, order_id, action = data.split(":", 2)

    order = db.get_by_id(order_id)
    if not order:
        await query.answer("❌ Zakaz topilmadi", show_alert=True)
        return

    old_status = order.get("status", "pending")

    # delivering
    if action == "delivering":
        if not _can_move(old_status, "delivering"):
            await query.answer("⚠️ Status ketma-ketligi xato", show_alert=True)
            return

        updated = db.update_status(order_id, "delivering") or order

        # courier markup update
        try:
            await query.edit_message_reply_markup(
                reply_markup=courier_keyboard({**updated, "status": "delivering"})
            )
        except Exception:
            pass

        # ✅ User notify delivering
        phone = updated.get("phone")
        if phone:
            await notify_user(
                ctx, phone,
                f"🚗 <b>Kuryer yo'lda!</b>\n\n"
                f"📦 Zakaz: <b>#{order_id}</b>\n"
                f"Iltimos, tayyor bo'ling! 🍗"
            )

        # admin signal (ixtiyoriy)
        admin_id = os.getenv("ADMIN_CHAT_ID", "")
        if admin_id:
            try:
                await ctx.bot.send_message(
                    chat_id=int(admin_id),
                    text=f"🚗 <b>Kuryer yo'lda!</b>\n📦 Zakaz #{order_id}",
                    parse_mode="HTML",
                )
            except Exception:
                pass

    # done
    elif action == "done":
        if not _can_move(old_status, "done"):
            await query.answer("⚠️ Status ketma-ketligi xato", show_alert=True)
            return

        updated = db.update_status(order_id, "done") or order

        # courier confirmation
        try:
            await query.edit_message_text(
                text=f"✅ <b>Zakaz #{order_id} yetkazildi!</b>\n\nRahmat! 🎉",
                parse_mode="HTML",
            )
        except Exception:
            pass

        # admin signal (ixtiyoriy)
        admin_id = os.getenv("ADMIN_CHAT_ID", "")
        if admin_id:
            try:
                await ctx.bot.send_message(
                    chat_id=int(admin_id),
                    text=f"✅ <b>Zakaz #{order_id} yetkazildi!</b>",
                    parse_mode="HTML",
                )
            except Exception:
                pass

        # ✅ COIN + REVIEW + user notify done
        phone = updated.get("phone")
        if phone:
            total = int(updated.get("total", 0) or 0)
            coins_used = int(updated.get("coins_used", 0) or 0)

            # coins ishlatilgan bo'lsa, cashback hisobida "asl total"ni tiklaymiz
            actual_total = total + (coins_used * 1000)

            earned = max(1, round(actual_total * 0.05 / 1000))

            new_balance = 0
            try:
                new_balance = db.add_coins(phone=phone, amount=earned, order_id=order_id)
            except Exception as e:
                print(f"db.add_coins xato: {e}")

            await notify_user(
                ctx, phone,
                f"🎉 <b>Buyurtmangiz yetkazildi!</b>\n\n"
                f"🪙 Sizga <b>+{earned} coin</b> qo'shildi\n"
                f"💰 Bu <b>{earned * 1000:,} UZS</b> chegirmaga teng\n"
                f"📊 Joriy balans: <b>{new_balance} coin</b>\n\n"
                f"Keyingi zakazda ishlatishingiz mumkin! 🛍",
                reply_markup=review_keyboard(order_id),
            )


# ═══════════════════════════════════════════════════════════════
# Review callbacks
# ═══════════════════════════════════════════════════════════════

async def review_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data or ""
    if not data.startswith("review:"):
        return

    await query.answer()
    order_id = data.split(":", 1)[1]
    ctx.user_data["awaiting_review"] = order_id

    await query.message.reply_text(
        f"✍️ <b>Izohingizni yozing</b>\n\n"
        f"#{order_id} buyurtma haqida fikringizni bildiring.\n"
        f"(Masalan: ovqat mazasi, yetkazib berish tezligi va h.k.)",
        parse_mode="HTML",
    )


async def handle_review_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if "awaiting_review" not in ctx.user_data:
        return

    order_id = ctx.user_data.pop("awaiting_review")
    review_text = (update.message.text or "").strip()
    user = update.effective_user

    admin_id = os.getenv("ADMIN_CHAT_ID", "")
    if admin_id and review_text:
        try:
            await ctx.bot.send_message(
                chat_id=int(admin_id),
                text=(
                    f"💬 <b>Yangi izoh!</b>\n\n"
                    f"📦 Buyurtma: #{order_id}\n"
                    f"👤 {user.full_name} (@{user.username or '—'})\n\n"
                    f"\"{review_text}\""
                ),
                parse_mode="HTML",
            )
        except Exception:
            pass

    await update.message.reply_text(
        "🙏 Izohingiz uchun rahmat! 🍗",
        parse_mode="HTML",
    )


# ═══════════════════════════════════════════════════════════════
# Admin commands / stats button
# ═══════════════════════════════════════════════════════════════

async def cmd_orders(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update.effective_chat.id):
        return

    orders = db.get_all(limit=10)
    if not orders:
        await update.message.reply_text("📭 Hali zakaz yo'q.")
        return

    lines = []
    for o in orders:
        st = o.get("status", "pending")
        emoji, label = STATUS.get(st, ("🕐", st))
        lines.append(f"{emoji} #{o.get('id','—')} — {int(o.get('total',0) or 0):,} UZS — {label}")

    await update.message.reply_text(
        "📋 <b>Oxirgi zakazlar:</b>\n\n" + "\n".join(lines),
        parse_mode="HTML",
    )


async def cmd_stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update.effective_chat.id):
        return
    s = db.stats_today()
    await update.message.reply_text(
        f"📊 <b>Bugungi statistika</b>\n\n"
        f"📦 Jami zakazlar : {s.get('total',0)}\n"
        f"🎉 Yetkazildi   : {s.get('done',0)}\n"
        f"🕐 Kutilmoqda   : {s.get('pending',0)}\n"
        f"❌ Bekor        : {s.get('cancelled',0)}\n"
        f"💰 Daromad      : {int(s.get('revenue',0) or 0):,} UZS",
        parse_mode="HTML",
    )


async def handle_statistics_btn(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update.effective_chat.id):
        return

    s = db.stats_monthly()
    lines = [
        f"📊 <b>Oylik statistika — {s.get('month_label','')}</b>\n",
        f"📦 Jami zakazlar : <b>{s.get('total',0)}</b>",
        f"✅ Yetkazildi    : <b>{s.get('done',0)}</b>",
        f"❌ Bekor qilindi : <b>{s.get('cancelled',0)}</b>",
        f"💰 Daromad       : <b>{int(s.get('revenue',0) or 0):,} UZS</b>",
        "",
        "👤 <b>Userlar bo'yicha:</b>",
    ]

    users = s.get("users") or []
    if not users:
        lines.append("  — bu oyda zakaz yo'q")
    else:
        for i, u in enumerate(users, 1):
            rev_str = f"  💵 {int(u.get('revenue',0) or 0):,} UZS" if u.get("revenue") else ""
            cancel_str = f"  ❌{u.get('cancelled',0)}" if u.get("cancelled") else ""
            lines.append(
                f"{i}. {u.get('name','—')} ({u.get('phone','—')})\n"
                f"   📦 {u.get('total',0)} zakaz  ✅{u.get('done',0)}{cancel_str}{rev_str}"
            )

    text = "\n".join(lines)
    if len(text) <= 4096:
        await update.message.reply_text(text, parse_mode="HTML")
        return

    chunk = ""
    for line in lines:
        if len(chunk) + len(line) + 1 > 4096:
            await update.message.reply_text(chunk, parse_mode="HTML")
            chunk = line
        else:
            chunk += ("\n" if chunk else "") + line
    if chunk:
        await update.message.reply_text(chunk, parse_mode="HTML")


# ═══════════════════════════════════════════════════════════════
# App yaratish
# ═══════════════════════════════════════════════════════════════

def create_app() -> Application:
    global _app_instance

    token = os.getenv("BOT_TOKEN", "")
    if not token:
        print("⚠️ BOT_TOKEN environment variable o'rnatilmagan!")

    app = Application.builder().token(token).build()

    # commands
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("orders", cmd_orders))
    app.add_handler(CommandHandler("stats", cmd_stats))

    # contact
    app.add_handler(MessageHandler(filters.CONTACT, handle_contact))

    # admin reply button
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^📊 Statistika$"), handle_statistics_btn))

    # review text
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_review_text))

    # callbacks
    app.add_handler(CallbackQueryHandler(review_callback, pattern=r"^review:"))
    app.add_handler(CallbackQueryHandler(courier_callback, pattern=r"^courier:"))
    app.add_handler(CallbackQueryHandler(handle_admin_status_callback, pattern=r"^status:"))

    _app_instance = app
    return app
