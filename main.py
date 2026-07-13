import os
import telebot
from telebot import types
from flask import Flask, request
import json
from dotenv import load_dotenv
import time

load_dotenv()

TOKEN = os.getenv('BOT_TOKEN')
OWNER_ID = int(os.getenv('OWNER_ID'))
WEBHOOK_URL = os.getenv('WEBHOOK_URL')  # Render URL

bot = telebot.TeleBot(TOKEN, parse_mode='HTML')
app = Flask(__name__)

# Vaqtinchalik xotira (Render restart bo'lganda o'chib ketadi)
user_states = {}
channels = []
current_post = {}
pending_buttons = []

# Kanallarni yuklash (environment variable'dan)
def load_channels():
    global channels
    channels_json = os.getenv('CHANNELS', '[]')
    try:
        channels = json.loads(channels_json)
    except:
        channels = []

def save_channels():
    # Render'da environment variableni o'zgartirish imkoni yo'q,
    # lekin bu funksiya mavjud bo'lsin
    pass

load_channels()

# Keyboard yaratish
def get_owner_main_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=1)
    btn_create = types.InlineKeyboardButton("📝 Post yaratish", callback_data="create_post")
    btn_add_channel = types.InlineKeyboardButton("➕ Kanal qo'shish", callback_data="add_channel")
    btn_channels = types.InlineKeyboardButton("📋 Kanallar ro'yxati", callback_data="list_channels")
    markup.add(btn_create, btn_add_channel, btn_channels)
    return markup

def get_post_buttons():
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_add_button = types.InlineKeyboardButton("🔗 Tugma qo'shish", callback_data="add_button")
    btn_send = types.InlineKeyboardButton("📤 Yuborish", callback_data="send_post")
    btn_cancel = types.InlineKeyboardButton("❌ Bekor qilish", callback_data="cancel_post")
    markup.add(btn_add_button, btn_send, btn_cancel)
    return markup

def get_send_options():
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_select = types.InlineKeyboardButton("🎯 Tanlash", callback_data="select_channels")
    btn_all = types.InlineKeyboardButton("📢 Barchaga", callback_data="send_all")
    btn_back = types.InlineKeyboardButton("⬅️ Orqaga", callback_data="back_to_post")
    markup.add(btn_select, btn_all, btn_back)
    return markup

def get_channels_keyboard(selected_channels=None):
    if selected_channels is None:
        selected_channels = []
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    for channel in channels:
        check = "✅ " if channel['id'] in selected_channels else "⬜ "
        btn_text = f"{check}{channel['name']}"
        btn = types.InlineKeyboardButton(btn_text, callback_data=f"toggle_{channel['id']}")
        markup.add(btn)
    
    btn_done = types.InlineKeyboardButton("✅ Tayyor - Yuborish", callback_data="confirm_selected")
    btn_back = types.InlineKeyboardButton("⬅️ Orqaga", callback_data="back_to_send_options")
    markup.add(btn_done, btn_back)
    return markup

# Bot owner tekshirish
def is_owner(user_id):
    return user_id == OWNER_ID

# Start komandasi
@bot.message_handler(commands=['start'])
def start_command(message):
    if is_owner(message.from_user.id):
        bot.send_message(
            message.chat.id,
            "👋 Salom, xo'jayin! Post yaratishni istaysizmi?",
            reply_markup=get_owner_main_keyboard()
        )
    else:
        bot.send_message(
            message.chat.id,
            "Bot faqat egasi uchun ishlaydi (@Shadow_sxi)"
        )

# Admin panel
@bot.message_handler(commands=['admin'])
def admin_command(message):
    if is_owner(message.from_user.id):
        bot.send_message(
            message.chat.id,
            "👨‍💻 Admin panel",
            reply_markup=get_owner_main_keyboard()
        )
    else:
        bot.send_message(message.chat.id, "Bot faqat egasi uchun ishlaydi (@Shadow_sxi)")

# Callback handler
@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    if not is_owner(call.from_user.id):
        bot.answer_callback_query(call.id, "Siz bot egasi emassiz!")
        return
    
    user_id = call.from_user.id
    
    # Post yaratish
    if call.data == "create_post":
        user_states[user_id] = "waiting_for_post"
        current_post[user_id] = {}
        pending_buttons.clear()
        bot.edit_message_text(
            "📝 Post yuboring (matn, rasm, video, gif, sticker, fayl, ovozli xabar):",
            call.message.chat.id,
            call.message.message_id
        )
    
    # Kanal qo'shish
    elif call.data == "add_channel":
        user_states[user_id] = "waiting_for_channel"
        bot.edit_message_text(
            "➕ Kanal ID sini kiriting:\n\n"
            "Masalan: @kanal_nomi yoki -1001234567890\n\n"
            "Bot kanalda admin bo'lishi kerak!",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=get_back_keyboard()
        )
    
    # Kanallar ro'yxati
    elif call.data == "list_channels":
        if channels:
            text = "📋 Mening kanallarim:\n\n"
            for i, ch in enumerate(channels, 1):
                text += f"{i}. {ch['name']}\n"
            
            markup = types.InlineKeyboardMarkup()
            btn_back = types.InlineKeyboardButton("⬅️ Orqaga", callback_data="back_to_main")
            markup.add(btn_back)
            
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)
        else:
            bot.edit_message_text(
                "❌ Hali hech qanday kanal qo'shilmagan.",
                call.message.chat.id,
                call.message.message_id,
                reply_markup=get_back_keyboard()
            )
    
    # Tugma qo'shish
    elif call.data == "add_button":
        user_states[user_id] = "waiting_for_button_name"
        msg = bot.edit_message_text(
            "🔗 Tugma nomini kiriting:",
            call.message.chat.id,
            call.message.message_id
        )
        bot.register_next_step_handler(msg, process_button_name)
    
    # Post yuborish
    elif call.data == "send_post":
        if user_id in current_post and current_post[user_id]:
            bot.edit_message_text(
                "📤 Yuborishga tayyormisiz?",
                call.message.chat.id,
                call.message.message_id,
                reply_markup=get_send_options()
            )
        else:
            bot.answer_callback_query(call.id, "❌ Avval post yarating!")
    
    # Kanallarni tanlash
    elif call.data == "select_channels":
        user_states[user_id] = "selecting_channels"
        if 'selected_channels' not in current_post.get(user_id, {}):
            if user_id not in current_post:
                current_post[user_id] = {}
            current_post[user_id]['selected_channels'] = []
        
        bot.edit_message_text(
            "🎯 Qaysi kanallarga yuboramiz?",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=get_channels_keyboard(current_post[user_id].get('selected_channels', []))
        )
    
    # Barchaga yuborish
    elif call.data == "send_all":
        send_to_all_channels(call.message)
        bot.edit_message_text(
            "✅ Post barcha kanallarga yuborildi!",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=get_owner_main_keyboard()
        )
    
    # Tanlangan kanallarni tasdiqlash
    elif call.data == "confirm_selected":
        if user_id in current_post and current_post[user_id].get('selected_channels'):
            send_to_selected_channels(call.message, current_post[user_id]['selected_channels'])
            bot.edit_message_text(
                "✅ Post tanlangan kanallarga yuborildi!",
                call.message.chat.id,
                call.message.message_id,
                reply_markup=get_owner_main_keyboard()
            )
        else:
            bot.answer_callback_query(call.id, "❌ Kamida bitta kanal tanlang!")
    
    # Bekor qilish
    elif call.data == "cancel_post":
        if user_id in user_states:
            del user_states[user_id]
        if user_id in current_post:
            del current_post[user_id]
        pending_buttons.clear()
        
        bot.edit_message_text(
            "❌ Post yaratish bekor qilindi.",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=get_owner_main_keyboard()
        )
    
    # Orqaga
    elif call.data == "back_to_main":
        bot.edit_message_text(
            "👋 Post yaratishni istaysizmi?",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=get_owner_main_keyboard()
        )
    
    elif call.data == "back_to_post":
        if user_id in current_post and current_post[user_id]:
            bot.edit_message_text(
                "📝 Postingiz tayyor!",
                call.message.chat.id,
                call.message.message_id,
                reply_markup=get_post_buttons()
            )
        else:
            bot.edit_message_text(
                "👋 Post yaratishni istaysizmi?",
                call.message.chat.id,
                call.message.message_id,
                reply_markup=get_owner_main_keyboard()
            )
    
    elif call.data == "back_to_send_options":
        bot.edit_message_text(
            "📤 Yuborishga tayyormisiz?",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=get_send_options()
        )
    
    # Kanal tanlash/tanlashni bekor qilish
    elif call.data.startswith("toggle_"):
        channel_id = call.data.replace("toggle_", "")
        
        if user_id not in current_post:
            current_post[user_id] = {}
        if 'selected_channels' not in current_post[user_id]:
            current_post[user_id]['selected_channels'] = []
        
        selected = current_post[user_id]['selected_channels']
        
        if channel_id in selected:
            selected.remove(channel_id)
        else:
            selected.append(channel_id)
        
        bot.edit_message_text(
            "🎯 Qaysi kanallarga yuboramiz?",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=get_channels_keyboard(selected)
        )

def get_back_keyboard():
    markup = types.InlineKeyboardMarkup()
    btn_back = types.InlineKeyboardButton("⬅️ Orqaga", callback_data="back_to_main")
    markup.add(btn_back)
    return markup

# Kanal qo'shish
@bot.message_handler(func=lambda message: message.from_user.id == OWNER_ID and 
                     user_states.get(message.from_user.id) == "waiting_for_channel")
def add_channel(message):
    user_id = message.from_user.id
    channel_id = message.text.strip()
    
    try:
        # Kanal ma'lumotini olish
        chat = bot.get_chat(channel_id)
        channel_info = {
            'id': str(chat.id),
            'name': chat.title or channel_id
        }
        
        # Tekshirish: bot kanalda adminmi?
        try:
            bot_member = bot.get_chat_member(chat.id, bot.get_me().id)
            if bot_member.status in ['administrator', 'creator']:
                # Kanal mavjudligini tekshirish
                if not any(ch['id'] == channel_info['id'] for ch in channels):
                    channels.append(channel_info)
                    save_channels()
                    bot.send_message(
                        message.chat.id,
                        f"✅ Kanal qo'shildi: {channel_info['name']}\n\n"
                        f"ID: {channel_info['id']}",
                        reply_markup=get_owner_main_keyboard()
                    )
                else:
                    bot.send_message(
                        message.chat.id,
                        "⚠️ Bu kanal allaqachon qo'shilgan!",
                        reply_markup=get_owner_main_keyboard()
                    )
            else:
                bot.send_message(
                    message.chat.id,
                    "❌ Bot bu kanalda admin emas! Avval botni admin qiling.",
                    reply_markup=get_owner_main_keyboard()
                )
        except:
            bot.send_message(
                message.chat.id,
                "❌ Bot bu kanalga qo'shilmagan! Kanalga botni qo'shing va admin qiling.",
                reply_markup=get_owner_main_keyboard()
            )
        
        del user_states[user_id]
        
    except Exception as e:
        bot.send_message(
            message.chat.id,
            f"❌ Xatolik: Kanal topilmadi yoki noto'g'ri ID.\n\n"
            f"To'g'ri format: @kanal_nomi yoki -1001234567890",
            reply_markup=get_owner_main_keyboard()
        )

# Post qabul qilish
@bot.message_handler(func=lambda message: message.from_user.id == OWNER_ID and 
                     user_states.get(message.from_user.id) == "waiting_for_post",
                     content_types=['text', 'photo', 'video', 'animation', 'sticker', 
                                  'document', 'audio', 'voice', 'video_note'])
def receive_post(message):
    user_id = message.from_user.id
    
    # Post ma'lumotlarini saqlash
    post_data = {
        'chat_id': message.chat.id,
        'message_id': message.message_id,
        'content_type': message.content_type,
        'from_chat_id': message.chat.id
    }
    
    current_post[user_id] = post_data
    user_states[user_id] = "post_ready"
    
    # Postni ko'rsatish
    bot.send_message(
        message.chat.id,
        "📝 Postingiz tayyor!",
        reply_markup=get_post_buttons()
    )

# Tugma nomini qabul qilish
def process_button_name(message):
    user_id = message.from_user.id
    if message.text:
        pending_buttons.append({'name': message.text, 'url': ''})
        user_states[user_id] = "waiting_for_button_url"
        msg = bot.send_message(message.chat.id, "🔗 Tugma URL manzilini kiriting:")
        bot.register_next_step_handler(msg, process_button_url)
    else:
        bot.send_message(message.chat.id, "❌ Iltimos, tugma nomini matn ko'rinishida kiriting!")

# Tugma URL qabul qilish
def process_button_url(message):
    user_id = message.from_user.id
    if message.text:
        pending_buttons[-1]['url'] = message.text
        del user_states[user_id]
        
        # Tugmalarni ko'rsatish
        markup = get_post_buttons_with_added()
        bot.send_message(
            message.chat.id,
            f"✅ Tugma qo'shildi!\n\n"
            f"📝 Tugmalar soni: {len(pending_buttons)}",
            reply_markup=markup
        )
    else:
        bot.send_message(message.chat.id, "❌ Iltimos, URL manzilini matn ko'rinishida kiriting!")

def get_post_buttons_with_added():
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_add = types.InlineKeyboardButton("🔗 Tugma qo'shish", callback_data="add_button")
    btn_send = types.InlineKeyboardButton("📤 Yuborish", callback_data="send_post")
    btn_cancel = types.InlineKeyboardButton("❌ Bekor qilish", callback_data="cancel_post")
    markup.add(btn_add, btn_send, btn_cancel)
    return markup

# Kanallarga post yuborish
def send_to_all_channels(message):
    user_id = message.chat.id
    
    if user_id not in current_post:
        bot.send_message(message.chat.id, "❌ Post topilmadi!")
        return
    
    post_data = current_post[user_id]
    sent_count = 0
    
    for channel in channels:
        try:
            send_post_to_channel(post_data, channel['id'], pending_buttons)
            sent_count += 1
        except Exception as e:
            bot.send_message(
                user_id,
                f"❌ {channel['name']} kanaliga yuborishda xatolik: {str(e)}"
            )
    
    bot.send_message(user_id, f"✅ {sent_count}/{len(channels)} kanalga yuborildi!")

def send_to_selected_channels(message, selected_channel_ids):
    user_id = message.chat.id
    
    if user_id not in current_post:
        bot.send_message(message.chat.id, "❌ Post topilmadi!")
        return
    
    post_data = current_post[user_id]
    sent_count = 0
    
    for ch_id in selected_channel_ids:
        channel = next((ch for ch in channels if ch['id'] == ch_id), None)
        if channel:
            try:
                send_post_to_channel(post_data, ch_id, pending_buttons)
                sent_count += 1
            except Exception as e:
                bot.send_message(
                    user_id,
                    f"❌ {channel['name']} kanaliga yuborishda xatolik: {str(e)}"
                )
    
    bot.send_message(user_id, f"✅ {sent_count}/{len(selected_channel_ids)} kanalga yuborildi!")

def send_post_to_channel(post_data, channel_id, buttons=None):
    markup = None
    if buttons:
        markup = types.InlineKeyboardMarkup()
        for btn in buttons:
            markup.add(types.InlineKeyboardButton(btn['name'], url=btn['url']))
    
    # Forward qilish
    bot.forward_message(
        chat_id=channel_id,
        from_chat_id=post_data['from_chat_id'],
        message_id=post_data['message_id']
    )
    
    # Agar tugmalar bo'lsa, qo'shimcha xabar yuborish
    if buttons:
        bot.send_message(
            chat_id=channel_id,
            text="🔗 Havolalar:",
            reply_markup=markup
        )

# Webhook sozlamalari
@app.route('/' + TOKEN, methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return ''
    else:
        return 'error', 403

@app.route('/')
def index():
    return 'Bot ishlamoqda!', 200

@app.route('/setwebhook')
def set_webhook():
    webhook_url = f"{WEBHOOK_URL}/{TOKEN}"
    bot.remove_webhook()
    time.sleep(1)
    bot.set_webhook(url=webhook_url)
    return f'Webhook o\'rnatildi: {webhook_url}', 200

if __name__ == '__main__':
    # Webhook o'rnatish
    if WEBHOOK_URL:
        bot.remove_webhook()
        time.sleep(1)
        bot.set_webhook(url=f"{WEBHOOK_URL}/{TOKEN}")
    
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
