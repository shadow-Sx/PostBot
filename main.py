# main.py
# pip install pyTelegramBotAPI

import re
import telebot
from telebot import types

TOKEN = "YOUR_BOT_TOKEN_HERE"

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")

user_states = {}      # user_id -> state dict
inline_answers = {}   # btn_id -> answer text


def get_state(user_id):
    if user_id not in user_states:
        user_states[user_id] = {
            "step": "waiting_link",
            "target_chat_id": None,
            "target_message_id": None,
            "draft": None,          # {"type","data","caption"}
            "buttons": [],          # [{"text","url"}]
            "inline_buttons": []    # [{"id","text"}]
        }
    return user_states[user_id]


def reset_state(user_id):
    if user_id in user_states:
        user_states.pop(user_id, None)


@bot.message_handler(commands=["start"])
def cmd_start(message: telebot.types.Message):
    if message.chat.type != "private":
        return
    reset_state(message.from_user.id)
    get_state(message.from_user.id)
    bot.send_message(
        message.chat.id,
        "Post havolasini yuboring (kanaldagi post linki)."
    )


def parse_post_link(text: str):
    # public: https://t.me/username/123
    m = re.search(r"t\.me/([\w_]+)/(\d+)", text)
    if m and m.group(1) != "c":
        username = m.group(1)
        msg_id = int(m.group(2))
        chat = bot.get_chat(username)
        return chat.id, msg_id

    # private: https://t.me/c/123456789/10
    m2 = re.search(r"t\.me/c/(\d+)/(\d+)", text)
    if m2:
        internal_id = int(m2.group(1))
        msg_id = int(m2.group(2))
        chat_id = -100 * internal_id
        return chat_id, msg_id

    return None, None


def build_control_keyboard():
    kb = types.InlineKeyboardMarkup()
    kb.row(
        types.InlineKeyboardButton("✏️ Tahrirlash", callback_data="edit_content"),
        types.InlineKeyboardButton("🔗 Tugmalar", callback_data="edit_buttons_menu"),
    )
    kb.row(
        types.InlineKeyboardButton("✅ Yuborish", callback_data="send_edit"),
        types.InlineKeyboardButton("❌ Bekor qilish", callback_data="cancel_edit"),
    )
    return kb


def build_buttons_markup(state):
    kb = types.InlineKeyboardMarkup()
    if state["buttons"]:
        row = []
        for b in state["buttons"]:
            row.append(types.InlineKeyboardButton(b["text"], url=b["url"]))
        kb.row(*row)
    if state["inline_buttons"]:
        row = []
        for b in state["inline_buttons"]:
            row.append(types.InlineKeyboardButton(b["text"], callback_data=f"inline_ans:{b['id']}"))
        kb.row(*row)
    return kb if (state["buttons"] or state["inline_buttons"]) else None


@bot.message_handler(content_types=["text"])
def handle_text(message: telebot.types.Message):
    if message.chat.type != "private":
        return

    user_id = message.from_user.id
    state = get_state(user_id)

    # inline/url button steps handled separately below
    if state["step"] in ["waiting_url_title", "waiting_url_url",
                         "waiting_inline_title", "waiting_inline_text"]:
        return

    if state["step"] == "waiting_link":
        chat_id, msg_id = parse_post_link(message.text)
        if not chat_id:
            bot.reply_to(message, "Havola noto‘g‘ri. Kanaldagi post linkini yuboring.")
            return

        try:
            preview = bot.copy_message(
                chat_id=message.chat.id,
                from_chat_id=chat_id,
                message_id=msg_id
            )
        except Exception as e:
            bot.reply_to(message, f"Postni olib bo‘lmadi. Bot kanalga admin qilinganiga ishonch hosil qiling.")
            return

        draft = {"type": None, "data": None, "caption": None}

        if preview.content_type == "text":
            draft["type"] = "text"
            draft["data"] = preview.text
        elif preview.content_type == "photo":
            draft["type"] = "photo"
            draft["data"] = preview.photo[-1].file_id
            draft["caption"] = preview.caption
        elif preview.content_type == "video":
            draft["type"] = "video"
            draft["data"] = preview.video.file_id
            draft["caption"] = preview.caption
        elif preview.content_type == "document":
            draft["type"] = "document"
            draft["data"] = preview.document.file_id
            draft["caption"] = preview.caption
        elif preview.content_type == "animation":
            draft["type"] = "animation"
            draft["data"] = preview.animation.file_id
            draft["caption"] = preview.caption
        else:
            bot.reply_to(message, "Bu turdagi post hozircha qo‘llab-quvvatlanmaydi.")
            return

        state["target_chat_id"] = chat_id
        state["target_message_id"] = msg_id
        state["draft"] = draft
        state["buttons"] = []
        state["inline_buttons"] = []
        state["step"] = "idle"

        bot.send_message(
            message.chat.id,
            "Post preview. Endi tahrirlashingiz yoki tugma qo‘shishingiz mumkin.",
            reply_markup=build_control_keyboard()
        )
        return

    if state["step"] == "editing_content":
        draft = state["draft"]
        draft["type"] = "text"
        draft["data"] = message.text
        draft["caption"] = None
        state["step"] = "idle"
        bot.send_message(
            message.chat.id,
            "Matn yangilandi.",
            reply_markup=build_control_keyboard()
        )
        return

    bot.reply_to(message, "Post havolasini yuboring yoki /start bosing.")


@bot.message_handler(content_types=["photo", "video", "document", "animation"])
def handle_media(message: telebot.types.Message):
    if message.chat.type != "private":
        return

    user_id = message.from_user.id
    state = get_state(user_id)

    if state["step"] != "editing_content":
        return

    draft = state["draft"]

    if message.content_type == "photo":
        draft["type"] = "photo"
        draft["data"] = message.photo[-1].file_id
        draft["caption"] = message.caption
    elif message.content_type == "video":
        draft["type"] = "video"
        draft["data"] = message.video.file_id
        draft["caption"] = message.caption
    elif message.content_type == "document":
        draft["type"] = "document"
        draft["data"] = message.document.file_id
        draft["caption"] = message.caption
    elif message.content_type == "animation":
        draft["type"] = "animation"
        draft["data"] = message.animation.file_id
        draft["caption"] = message.caption
    else:
        bot.reply_to(message, "Bu turdagi media qo‘llab-quvvatlanmaydi.")
        return

    state["step"] = "idle"
    bot.send_message(
        message.chat.id,
        "Media yangilandi.",
        reply_markup=build_control_keyboard()
    )


@bot.callback_query_handler(func=lambda c: c.data in ["edit_content", "edit_buttons_menu", "send_edit", "cancel_edit"])
def control_callback(call: telebot.types.CallbackQuery):
    user_id = call.from_user.id
    state = get_state(user_id)

    if not state["draft"]:
        bot.answer_callback_query(call.id, "Avval post havolasini yuboring.")
        return

    if call.data == "edit_content":
        state["step"] = "editing_content"
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, "Yangi matn yoki media yuboring.")
    elif call.data == "edit_buttons_menu":
        bot.answer_callback_query(call.id)
        show_buttons_menu(call.message)
    elif call.data == "cancel_edit":
        reset_state(user_id)
        bot.answer_callback_query(call.id, "Bekor qilindi.")
        bot.edit_message_text(
            "Tahrirlash bekor qilindi.",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id
        )
    elif call.data == "send_edit":
        bot.answer_callback_query(call.id)
        apply_edit(call.message, state)


def show_buttons_menu(message):
    kb = types.InlineKeyboardMarkup()
    kb.row(
        types.InlineKeyboardButton("➕ URL tugma", callback_data="btn_add_url"),
        types.InlineKeyboardButton("➕ Inline tugma", callback_data="btn_add_inline"),
    )
    kb.row(
        types.InlineKeyboardButton("🧹 Tugmalarni tozalash", callback_data="btn_clear_all"),
    )
    kb.row(
        types.InlineKeyboardButton("⬅️ Orqaga", callback_data="btn_back")
    )
    bot.edit_message_text(
        "Tugmalar bo‘limi:",
        chat_id=message.chat.id,
        message_id=message.message_id,
        reply_markup=kb
    )


@bot.callback_query_handler(func=lambda c: c.data.startswith("btn_"))
def buttons_menu_callback(call: telebot.types.CallbackQuery):
    user_id = call.from_user.id
    state = get_state(user_id)

    if not state["draft"]:
        bot.answer_callback_query(call.id, "Avval post havolasini yuboring.")
        return

    if call.data == "btn_back":
        bot.answer_callback_query(call.id)
        bot.edit_message_text(
            "Post boshqaruvi:",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=build_control_keyboard()
        )
    elif call.data == "btn_clear_all":
        state["buttons"] = []
        state["inline_buttons"] = []
        bot.answer_callback_query(call.id, "Barcha tugmalar o‘chirildi.")
    elif call.data == "btn_add_url":
        state["step"] = "waiting_url_title"
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, "URL tugma nomini yuboring:")
    elif call.data == "btn_add_inline":
        state["step"] = "waiting_inline_title"
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, "Inline tugma nomini yuboring:")


@bot.message_handler(func=lambda m: get_state(m.from_user.id)["step"] in ["waiting_url_title", "waiting_url_url"])
def handle_url_button(message: telebot.types.Message):
    user_id = message.from_user.id
    state = get_state(user_id)
    draft = state["draft"]
    if not draft:
        bot.send_message(message.chat.id, "Avval post havolasini yuboring.")
        state["step"] = "waiting_link"
        return

    if state["step"] == "waiting_url_title":
        state["tmp_url_title"] = message.text
        state["step"] = "waiting_url_url"
        bot.send_message(message.chat.id, "Endi URL yuboring:")
    elif state["step"] == "waiting_url_url":
        title = state.get("tmp_url_title")
        url = message.text.strip()
        if not url.startswith("http"):
            bot.send_message(message.chat.id, "URL noto‘g‘ri. Masalan: https://example.com")
            return
        state["buttons"].append({"text": title, "url": url})
        state.pop("tmp_url_title", None)
        state["step"] = "idle"
        bot.send_message(
            message.chat.id,
            "URL tugma qo‘shildi.",
            reply_markup=build_control_keyboard()
        )


@bot.message_handler(func=lambda m: get_state(m.from_user.id)["step"] in ["waiting_inline_title", "waiting_inline_text"])
def handle_inline_button(message: telebot.types.Message):
    user_id = message.from_user.id
    state = get_state(user_id)
    draft = state["draft"]
    if not draft:
        bot.send_message(message.chat.id, "Avval post havolasini yuboring.")
        state["step"] = "waiting_link"
        return

    if state["step"] == "waiting_inline_title":
        state["tmp_inline_title"] = message.text
        state["step"] = "waiting_inline_text"
        bot.send_message(message.chat.id, "Tugma bosilganda chiqadigan matnni yuboring:")
    elif state["step"] == "waiting_inline_text":
        title = state.get("tmp_inline_title")
        ans_text = message.text
        btn_id = f"{user_id}_{len(inline_answers)+1}"
        inline_answers[btn_id] = ans_text
        state["inline_buttons"].append({"id": btn_id, "text": title})
        state.pop("tmp_inline_title", None)
        state["step"] = "idle"
        bot.send_message(
            message.chat.id,
            "Inline tugma qo‘shildi.",
            reply_markup=build_control_keyboard()
        )


@bot.callback_query_handler(func=lambda c: c.data.startswith("inline_ans:"))
def inline_answer_handler(call: telebot.types.CallbackQuery):
    btn_id = call.data.split(":", 1)[1]
    text = inline_answers.get(btn_id, "Hatolik yuz berdi.")
    bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id, text)


def apply_edit(message, state):
    chat_id = state["target_chat_id"]
    msg_id = state["target_message_id"]
    draft = state["draft"]
    markup = build_buttons_markup(state)

    try:
        if draft["type"] == "text":
            bot.edit_message_text(
                draft["data"],
                chat_id=chat_id,
                message_id=msg_id,
                reply_markup=markup
            )
        elif draft["type"] in ["photo", "video", "document", "animation"]:
            # faqat caption va tugmalarni yangilaymiz
            bot.edit_message_caption(
                chat_id=chat_id,
                message_id=msg_id,
                caption=draft.get("caption"),
                reply_markup=markup
            )
        bot.edit_message_text(
            "Post tahrirlandi va kanalga yangilandi.",
            chat_id=message.chat.id,
            message_id=message.message_id
        )
        reset_state(message.chat.id)
    except Exception as e:
        bot.send_message(message.chat.id, f"Tahrirlashda xatolik: {e}")


print("Bot ishga tushdi.")
bot.infinity_polling(skip_pending=True)
