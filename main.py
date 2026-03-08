# main.py
# pip install pyTelegramBotAPI

import telebot
from telebot import types
import os

TOKEN = "YOUR_BOT_TOKEN_HERE"
CHANNELS_FILE = "channels.txt"

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")

# user_id -> draft data
user_states = {}

# =======================
#  KANALLAR BILAN ISHLASH
# =======================

def load_channels():
    channels = []
    if not os.path.exists(CHANNELS_FILE):
        return channels
    with open(CHANNELS_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split("|", 2)
            if len(parts) == 3:
                ch_id, title, username = parts
            elif len(parts) == 2:
                ch_id, title = parts
                username = ""
            else:
                continue
            channels.append({
                "id": int(ch_id),
                "title": title,
                "username": username
            })
    return channels

def save_channel(chat_id: int, title: str, username: str):
    channels = load_channels()
    for ch in channels:
        if ch["id"] == chat_id:
            return
    with open(CHANNELS_FILE, "a", encoding="utf-8") as f:
        f.write(f"{chat_id}|{title}|{username or ''}\n")

# /register ni kanal ichida yozish orqali kanalni ulash
@bot.message_handler(commands=["register"])
def register_channel(message: telebot.types.Message):
    if message.chat.type not in ["channel", "supergroup"]:
        return
    # faqat kanal uchun ishlatamiz
    if message.chat.type == "channel":
        save_channel(message.chat.id, message.chat.title or "No title", message.chat.username or "")
        try:
            bot.delete_message(message.chat.id, message.message_id)
        except:
            pass
        text = "Kanal botga ulandi. Endi bot orqali post yaratishingiz mumkin."
        bot.send_message(message.chat.id, text)
    else:
        # agar supergroup bo'lsa, e'tiborsiz qoldiramiz
        return

# =======================
#  FOYDALANUVCHI HOLATI
# =======================

def reset_user_state(user_id):
    user_states[user_id] = {
        "step": None,
        "channel_id": None,
        "posts": [],  # har bir element: {"type": "text/photo/video/...", "data": ..., "caption": str, "buttons": [], "inline_buttons": [], "silent": False}
    }

def get_user_state(user_id):
    if user_id not in user_states:
        reset_user_state(user_id)
    return user_states[user_id]

# =======================
#  ASOSIY /start
# =======================

@bot.message_handler(commands=["start"])
def start(message: telebot.types.Message):
    if message.chat.type != "private":
        return
    state = get_user_state(message.from_user.id)
    state["step"] = None

    text = (
        "Salom, bugun ham post tayyorlaymizmi yoki rejalashtirilgan postlarni to‘g‘rilamoqchimisiz?"
    )
    kb = types.InlineKeyboardMarkup()
    kb.add(
        types.InlineKeyboardButton("Post yaratish", callback_data="main_post_create"),
        types.InlineKeyboardButton("Rejalar", callback_data="main_rejalar")
    )
    bot.send_message(message.chat.id, text, reply_markup=kb)

# =======================
#  ASOSIY MENYU CALLBACK
# =======================

@bot.callback_query_handler(func=lambda c: c.data.startswith("main_"))
def main_menu_callback(call: telebot.types.CallbackQuery):
    user_id = call.from_user.id
    state = get_user_state(user_id)

    if call.data == "main_post_create":
        # kanal tanlash sahifasi
        state["step"] = "choose_channel"
        show_channels_page(call.message, user_id, page=0)
    elif call.data == "main_rejalar":
        bot.answer_callback_query(call.id, "Rejalar hozircha yoq (kechiktirish o‘chirib tashlangan).")
    else:
        bot.answer_callback_query(call.id)

# =======================
#  KANAL TANLASH SAHIFASI
# =======================

def show_channels_page(message, user_id, page=0):
    channels = load_channels()
    if not channels:
        text = (
            "Hali birorta kanal ulanmagan.\n\n"
            "Kanalga botni admin qiling va kanal ichida /register yozing."
        )
        bot.edit_message_text(
            text,
            chat_id=message.chat.id,
            message_id=message.message_id
        )
        return

    per_page = 10
    start_idx = page * per_page
    end_idx = start_idx + per_page
    page_channels = channels[start_idx:end_idx]

    kb = types.InlineKeyboardMarkup(row_width=2)
    for ch in page_channels:
        title = ch["title"]
        btn_text = title
        kb.add(types.InlineKeyboardButton(btn_text, callback_data=f"choose_channel:{ch['id']}"))

    nav_row = []
    if page > 0:
        nav_row.append(types.InlineKeyboardButton("⬅️ Orqaga", callback_data=f"channels_page:{page-1}"))
    if end_idx < len(channels):
        nav_row.append(types.InlineKeyboardButton("Oldinga ➡️", callback_data=f"channels_page:{page+1}"))
    if nav_row:
        kb.row(*nav_row)

    kb.row(types.InlineKeyboardButton("Asosiy menyu", callback_data="back_to_main"))

    text = "Qaysi kanalga post yaratmoqchisiz?"
    try:
        bot.edit_message_text(
            text,
            chat_id=message.chat.id,
            message_id=message.message_id,
            reply_markup=kb
        )
    except:
        bot.send_message(message.chat.id, text, reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("channels_page:") or c.data.startswith("choose_channel:") or c.data == "back_to_main")
def channels_callback(call: telebot.types.CallbackQuery):
    user_id = call.from_user.id
    state = get_user_state(user_id)

    if call.data == "back_to_main":
        state["step"] = None
        bot.delete_message(call.message.chat.id, call.message.message_id)
        start(call.message)
        return

    if call.data.startswith("channels_page:"):
        page = int(call.data.split(":")[1])
        show_channels_page(call.message, user_id, page)
        return

    if call.data.startswith("choose_channel:"):
        ch_id = int(call.data.split(":")[1])
        state["channel_id"] = ch_id
        state["posts"] = []
        state["step"] = "post_menu"

        text = f"{ch_id} kanaliga haqiqatdan ham habar yubormoqchimisiz?\n\nEndi post yaratish bo‘limi."
        kb = post_menu_keyboard()
        bot.edit_message_text(
            text,
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=kb
        )

# =======================
#  POST MENYUSI
# =======================

def post_menu_keyboard():
    kb = types.InlineKeyboardMarkup()
    kb.row(
        types.InlineKeyboardButton("Post yuborish", callback_data="post_add"),
        types.InlineKeyboardButton("Tahrirlash/Tugma qo‘shish", callback_data="post_edit_menu")
    )
    kb.row(
        types.InlineKeyboardButton("Tozalash", callback_data="post_clear"),
        types.InlineKeyboardButton("O‘chirish", callback_data="post_delete"),
    )
    kb.row(
        types.InlineKeyboardButton("Ko‘rish", callback_data="post_preview_all"),
        types.InlineKeyboardButton("Yuborish", callback_data="post_send_step1"),
    )
    kb.row(types.InlineKeyboardButton("Asosiy menyu", callback_data="back_to_main"))
    return kb

@bot.callback_query_handler(func=lambda c: c.data.startswith("post_"))
def post_menu_handler(call: telebot.types.CallbackQuery):
    user_id = call.from_user.id
    state = get_user_state(user_id)

    if state.get("channel_id") is None:
        bot.answer_callback_query(call.id, "Avval kanal tanlang.")
        return

    if call.data == "post_add":
        state["step"] = "waiting_post"
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, "Post yuboring (matn, rasm, video va hokazo).")
    elif call.data == "post_edit_menu":
        state["step"] = "edit_menu"
        show_edit_menu(call.message)
    elif call.data == "post_clear":
        state["posts"] = []
        bot.answer_callback_query(call.id, "Barcha postlar tozalandi.")
    elif call.data == "post_delete":
        reset_user_state(user_id)
        bot.answer_callback_query(call.id, "Post bekor qilindi.")
        bot.edit_message_text(
            "Post bekor qilindi.",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id
        )
    elif call.data == "post_preview_all":
        bot.answer_callback_query(call.id)
        preview_all_posts(call.message, state)
    elif call.data == "post_send_step1":
        bot.answer_callback_query(call.id)
        post_send_step1(call.message, state)
    else:
        bot.answer_callback_query(call.id)

# =======================
#  POST QABUL QILISH
# =======================

@bot.message_handler(content_types=["text", "photo", "video", "document", "animation"])
def handle_post_content(message: telebot.types.Message):
    if message.chat.type != "private":
        return

    user_id = message.from_user.id
    state = get_user_state(user_id)

    if state.get("step") != "waiting_post":
        # oddiy foydalanuvchi uchun javob
        if message.chat.type == "private":
            bot.reply_to(message, "Ushbu post bot @AniCratorBot tomonidan tayyorlandi.")
        return

    post_entry = {
        "type": None,
        "data": None,
        "caption": None,
        "buttons": [],        # URL tugmalar
        "inline_buttons": [], # inline text tugmalar
        "silent": False
    }

    if message.content_type == "text":
        post_entry["type"] = "text"
        post_entry["data"] = message.text
    elif message.content_type == "photo":
        post_entry["type"] = "photo"
        post_entry["data"] = message.photo[-1].file_id
        post_entry["caption"] = message.caption
    elif message.content_type == "video":
        post_entry["type"] = "video"
        post_entry["data"] = message.video.file_id
        post_entry["caption"] = message.caption
    elif message.content_type == "document":
        post_entry["type"] = "document"
        post_entry["data"] = message.document.file_id
        post_entry["caption"] = message.caption
    elif message.content_type == "animation":
        post_entry["type"] = "animation"
        post_entry["data"] = message.animation.file_id
        post_entry["caption"] = message.caption
    else:
        bot.reply_to(message, "Bu turdagi kontent qo‘llab-quvvatlanmaydi.")
        return

    state["posts"].append(post_entry)
    state["step"] = "post_menu"

    # preview sifatida qayta yuborish
    bot.send_message(message.chat.id, "Post qabul qilindi. Kanalga shunday ko‘rinishda yuboriladi:")
    send_single_preview(message.chat.id, post_entry)

    kb = post_menu_keyboard()
    bot.send_message(message.chat.id, "Post menyusi:", reply_markup=kb)

# =======================
#  PREVIEW FUNKSIYALARI
# =======================

def build_markup_for_post(post_entry):
    kb = types.InlineKeyboardMarkup()
    # URL tugmalar
    if post_entry["buttons"]:
        row = []
        for btn in post_entry["buttons"]:
            row.append(types.InlineKeyboardButton(btn["text"], url=btn["url"]))
        kb.row(*row)
    # Inline tugmalar (callback)
    if post_entry["inline_buttons"]:
        row = []
        for btn in post_entry["inline_buttons"]:
            row.append(types.InlineKeyboardButton(btn["text"], callback_data=f"inline_ans:{btn['id']}"))
        kb.row(*row)
    return kb if (post_entry["buttons"] or post_entry["inline_buttons"]) else None

def send_single_preview(chat_id, post_entry):
    markup = build_markup_for_post(post_entry)
    if post_entry["type"] == "text":
        bot.send_message(chat_id, post_entry["data"], reply_markup=markup)
    elif post_entry["type"] == "photo":
        bot.send_photo(chat_id, post_entry["data"], caption=post_entry["caption"], reply_markup=markup)
    elif post_entry["type"] == "video":
        bot.send_video(chat_id, post_entry["data"], caption=post_entry["caption"], reply_markup=markup)
    elif post_entry["type"] == "document":
        bot.send_document(chat_id, post_entry["data"], caption=post_entry["caption"], reply_markup=markup)
    elif post_entry["type"] == "animation":
        bot.send_animation(chat_id, post_entry["data"], caption=post_entry["caption"], reply_markup=markup)

def preview_all_posts(message, state):
    posts = state.get("posts", [])
    if not posts:
        bot.send_message(message.chat.id, "Hali birorta post qo‘shilmagan.")
        return
    bot.send_message(message.chat.id, "Barcha postlar preview holatida:")
    for p in posts:
        send_single_preview(message.chat.id, p)

# =======================
#  YUBORISH BOSQICHLARI
# =======================

def post_send_step1(message, state):
    posts = state.get("posts", [])
    if not posts:
        bot.send_message(message.chat.id, "Hali post yo‘q.")
        return
    text = "Postni hozir tashlamoqchimisiz?"
    kb = types.InlineKeyboardMarkup()
    kb.row(
        types.InlineKeyboardButton("Yuborish", callback_data="send_now_step2"),
        types.InlineKeyboardButton("Kechiktirish", callback_data="send_delay_disabled"),
        types.InlineKeyboardButton("Orqaga qaytish", callback_data="send_back_to_post_menu")
    )
    bot.send_message(message.chat.id, text, reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("send_"))
def send_callback(call: telebot.types.CallbackQuery):
    user_id = call.from_user.id
    state = get_user_state(user_id)

    if call.data == "send_back_to_post_menu":
        kb = post_menu_keyboard()
        bot.edit_message_text(
            "Post menyusi:",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=kb
        )
    elif call.data == "send_delay_disabled":
        bot.answer_callback_query(call.id, "Kechiktirish o‘chirib tashlangan.")
    elif call.data == "send_now_step2":
        text = "Haqiqatdan ham shu habar(lar)ni yubormoqchimisiz?"
        kb = types.InlineKeyboardMarkup()
        kb.row(
            types.InlineKeyboardButton("Yuborish", callback_data="send_confirm"),
            types.InlineKeyboardButton("Orqaga qaytish", callback_data="send_back_to_step1")
        )
        bot.edit_message_text(
            text,
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=kb
        )
    elif call.data == "send_back_to_step1":
        post_send_step1(call.message, state)
    elif call.data == "send_confirm":
        send_posts_to_channel(call.message, state)
        reset_user_state(user_id)
        bot.edit_message_text(
            "Post(lar) kanalga yuborildi.",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id
        )
    else:
        bot.answer_callback_query(call.id)

def send_posts_to_channel(message, state):
    channel_id = state.get("channel_id")
    posts = state.get("posts", [])
    if not channel_id or not posts:
        return
    for p in posts:
        markup = build_markup_for_post(p)
        disable_notification = p.get("silent", False)
        if p["type"] == "text":
            bot.send_message(channel_id, p["data"], reply_markup=markup, disable_notification=disable_notification)
        elif p["type"] == "photo":
            bot.send_photo(channel_id, p["data"], caption=p["caption"], reply_markup=markup, disable_notification=disable_notification)
        elif p["type"] == "video":
            bot.send_video(channel_id, p["data"], caption=p["caption"], reply_markup=markup, disable_notification=disable_notification)
        elif p["type"] == "document":
            bot.send_document(channel_id, p["data"], caption=p["caption"], reply_markup=markup, disable_notification=disable_notification)
        elif p["type"] == "animation":
            bot.send_animation(channel_id, p["data"], caption=p["caption"], reply_markup=markup, disable_notification=disable_notification)

# =======================
#  TAHRIRLASH / TUGMA QO‘SHISH MENYUSI
# =======================

def show_edit_menu(message):
    kb = types.InlineKeyboardMarkup()
    kb.row(
        types.InlineKeyboardButton("Reaksiya", callback_data="edit_reaction_disabled"),
        types.InlineKeyboardButton("Tugma (URL)", callback_data="edit_url_buttons")
    )
    kb.row(
        types.InlineKeyboardButton("Ovozsiz yuborish ON/OFF", callback_data="edit_silent_toggle"),
        types.InlineKeyboardButton("Inline tugma", callback_data="edit_inline_buttons")
    )
    kb.row(types.InlineKeyboardButton("Orqaga", callback_data="edit_back_to_post_menu"))
    bot.edit_message_text(
        "Tahrirlash / Tugma qo‘shish bo‘limi:",
        chat_id=message.chat.id,
        message_id=message.message_id,
        reply_markup=kb
    )

@bot.callback_query_handler(func=lambda c: c.data.startswith("edit_"))
def edit_menu_handler(call: telebot.types.CallbackQuery):
    user_id = call.from_user.id
    state = get_user_state(user_id)
    posts = state.get("posts", [])

    if not posts:
        bot.answer_callback_query(call.id, "Hali post yo‘q.")
        return

    last_post = posts[-1]

    if call.data == "edit_back_to_post_menu":
        kb = post_menu_keyboard()
        bot.edit_message_text(
            "Post menyusi:",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=kb
        )
    elif call.data == "edit_reaction_disabled":
        bot.answer_callback_query(call.id, "Reaksiya hisoblashsiz qoldirildi (o‘chirib tashlangan).")
    elif call.data == "edit_silent_toggle":
        last_post["silent"] = not last_post.get("silent", False)
        status = "Ovozsiz yuboriladi" if last_post["silent"] else "Ovozli yuboriladi"
        bot.answer_callback_query(call.id, status)
    elif call.data == "edit_url_buttons":
        state["step"] = "waiting_url_button_title"
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, "URL tugma nomini yuboring:")
    elif call.data == "edit_inline_buttons":
        state["step"] = "waiting_inline_button_title"
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, "Inline tugma nomini yuboring:")
    else:
        bot.answer_callback_query(call.id)

# =======================
#  URL TUGMA QO‘SHISH
# =======================

@bot.message_handler(func=lambda m: get_user_state(m.from_user.id).get("step") in ["waiting_url_button_title", "waiting_url_button_url"])
def handle_url_button(message: telebot.types.Message):
    user_id = message.from_user.id
    state = get_user_state(user_id)
    posts = state.get("posts", [])
    if not posts:
        bot.send_message(message.chat.id, "Hali post yo‘q.")
        state["step"] = "post_menu"
        return
    last_post = posts[-1]

    if state["step"] == "waiting_url_button_title":
        state["tmp_btn_title"] = message.text
        state["step"] = "waiting_url_button_url"
        bot.send_message(message.chat.id, "Endi URL yuboring:")
    elif state["step"] == "waiting_url_button_url":
        title = state.get("tmp_btn_title")
        url = message.text
        if not url.startswith("http"):
            bot.send_message(message.chat.id, "URL noto‘g‘ri. Masalan: https://example.com")
            return
        last_post["buttons"].append({"text": title, "url": url})
        state["step"] = "edit_menu"
        state.pop("tmp_btn_title", None)
        bot.send_message(message.chat.id, "URL tugma qo‘shildi.")
        show_edit_menu(message)

# =======================
#  INLINE TUGMA QO‘SHISH
# =======================

inline_answers = {}  # id -> text

@bot.message_handler(func=lambda m: get_user_state(m.from_user.id).get("step") in ["waiting_inline_button_title", "waiting_inline_button_text"])
def handle_inline_button(message: telebot.types.Message):
    user_id = message.from_user.id
    state = get_user_state(user_id)
    posts = state.get("posts", [])
    if not posts:
        bot.send_message(message.chat.id, "Hali post yo‘q.")
        state["step"] = "post_menu"
        return
    last_post = posts[-1]

    if state["step"] == "waiting_inline_button_title":
        state["tmp_inline_title"] = message.text
        state["step"] = "waiting_inline_button_text"
        bot.send_message(message.chat.id, "Endi tugma bosilganda chiqadigan matnni yuboring:")
    elif state["step"] == "waiting_inline_button_text":
        title = state.get("tmp_inline_title")
        ans_text = message.text
        btn_id = f"{message.from_user.id}_{len(inline_answers)+1}"
        inline_answers[btn_id] = ans_text
        last_post["inline_buttons"].append({"id": btn_id, "text": title})
        state["step"] = "edit_menu"
        state.pop("tmp_inline_title", None)
        bot.send_message(message.chat.id, "Inline tugma qo‘shildi.")
        show_edit_menu(message)

@bot.callback_query_handler(func=lambda c: c.data.startswith("inline_ans:"))
def inline_answer_handler(call: telebot.types.CallbackQuery):
    btn_id = call.data.split(":", 1)[1]
    text = inline_answers.get(btn_id, "Hatolik yuz berdi.")
    # kanalga obuna tekshirishni bu yerda qo‘shish mumkin (agar xohlasang keyin alohida qilamiz)
    bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id, text)

# =======================
#  RUN
# =======================

print("Bot ishga tushdi.")
bot.infinity_polling(skip_pending=True)
