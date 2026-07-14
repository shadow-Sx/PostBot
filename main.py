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
WEBHOOK_URL = os.getenv('WEBHOOK_URL')

bot = telebot.TeleBot(TOKEN, parse_mode='HTML')
app = Flask(__name__)

# Vaqtinchalik xotira
user_states = {}
channels = []
current_posts = {}  # Har bir user uchun alohida post va tugmalar

# Kanallarni yuklash
def load_channels():
    global channels
    channels_json = os.getenv('CHANNELS', '[]')
    try:
        channels = json.loads(channels_json)
    except:
        channels = []

load_channels()

# Owner keyboard
def get_owner_main_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=1)
    btn_create = types.InlineKeyboardButton("📝 Post yaratish", callback_data="create_post")
    btn_add_channel = types.InlineKeyboardButton("➕ Kanal qo'shish", callback_data="add_channel")
    btn_channels = types.InlineKeyboardButton("📋 Kanallar ro'yxati", callback_data="list_channels")
    markup.add(btn_create, btn_add_channel, btn_channels)
    return markup

def get_post_management_keyboard(user_id):
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_add_button = types.InlineKeyboardButton("🔗 Tugma qo'shish", callback_data="add_button")
    btn_show_buttons = types.InlineKeyboardButton("📋 Tugmalarni ko'rish", callback_data="show_buttons")
    btn_send = types.InlineKeyboardButton("📤 Yuborish", callback_data="send_post")
    btn_cancel = types.InlineKeyboardButton("❌ Bekor qilish", callback_data="cancel_post")
    markup.add(btn_add_button, btn_show_buttons)
    markup.add(btn_send, btn_cancel)
    return markup

def get_send_options():
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_select = types.InlineKeyboardButton("🎯 Tanlash", callback_data="select_channels")
    btn_all = types.InlineKeyboardButton("📢 Barchaga", callback_data="send_all")
    btn_back = types.InlineKeyboardButton("⬅️ Orqaga", callback_data="back_to_post")
    markup.add(btn_select, btn_all, btn_back)
    return markup

def get_channels_keyboard(selected_channels):
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

def get_buttons_management_keyboard(user_id):
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_add = types.InlineKeyboardButton("➕ Yangi tugma", callback_data="add_button")
    btn_delete = types.InlineKeyboardButton("🗑 Tugma o'chirish", callback_data="delete_button")
    btn_clear = types.InlineKeyboardButton("🔄 Hammasini tozalash", callback_data="clear_buttons")
    btn_back = types.InlineKeyboardButton("⬅️ Orqaga", callback_data="back_to_post")
    markup.add(btn_add, btn_delete)
    markup.add(btn_clear, btn_back)
    return markup

# Owner tekshirish
def is_owner(user_id):
    return user_id == OWNER_ID

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

@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    if not is_owner(call.from_user.id):
        bot.answer_callback_query(call.id, "Siz bot egasi emassiz!")
        return
    
    user_id = call.from_user.id
    
    # Post yaratish
    if call.data == "create_post":
        user_states[user_id] = "waiting_for_post"
        current_posts[user_id] = {
            'post_data': {},
            'buttons': []
        }
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
                text += f"{i}. {ch['name']} (ID: {ch['id']})\n"
            
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
    
    # Tugmalarni ko'rish
    elif call.data == "show_buttons":
        if user_id in current_posts and current_posts[user_id]['buttons']:
            buttons = current_posts[user_id]['buttons']
            text = "📋 Post tugmalari:\n\n"
            for i, btn in enumerate(buttons, 1):
                text += f"{i}. {btn['name']} → {btn['url']}\n"
            
            bot.edit_message_text(
                text,
                call.message.chat.id,
                call.message.message_id,
                reply_markup=get_buttons_management_keyboard(user_id)
            )
        else:
            bot.edit_message_text(
                "❌ Hali hech qanday tugma qo'shilmagan.",
                call.message.chat.id,
                call.message.message_id,
                reply_markup=get_buttons_management_keyboard(user_id)
            )
    
    # Tugma o'chirish
    elif call.data == "delete_button":
        if user_id in current_posts and current_posts[user_id]['buttons']:
            user_states[user_id] = "deleting_button"
            buttons = current_posts[user_id]['buttons']
            markup = types.InlineKeyboardMarkup(row_width=1)
            for i, btn in enumerate(buttons):
                markup.add(types.InlineKeyboardButton(
                    f"🗑 {btn['name']}", 
                    callback_data=f"delbtn_{i}"
                ))
            markup.add(types.InlineKeyboardButton("⬅️ Orqaga", callback_data="back_to_post"))
            
            bot.edit_message_text(
                "🗑 Qaysi tugmani o'chirmoqchisiz?",
                call.message.chat.id,
                call.message.message_id,
                reply_markup=markup
            )
        else:
            bot.answer_callback_query(call.id, "❌ O'chirish uchun tugmalar yo'q!")
    
    # Tugma o'chirish amali
    elif call.data.startswith("delbtn_"):
        index = int(call.data.replace("delbtn_", ""))
        if user_id in current_posts and 0 <= index < len(current_posts[user_id]['buttons']):
            deleted_btn = current_posts[user_id]['buttons'].pop(index)
            bot.answer_callback_query(call.id, f"✅ '{deleted_btn['name']}' o'chirildi!")
            
            if current_posts[user_id]['buttons']:
                bot.edit_message_text(
                    f"✅ Tugma o'chirildi! Qolgan tugmalar: {len(current_posts[user_id]['buttons'])}",
                    call.message.chat.id,
                    call.message.message_id,
                    reply_markup=get_buttons_management_keyboard(user_id)
                )
            else:
                bot.edit_message_text(
                    "✅ Barcha tugmalar o'chirildi!",
                    call.message.chat.id,
                    call.message.message_id,
                    reply_markup=get_post_management_keyboard(user_id)
                )
    
    # Barcha tugmalarni tozalash
    elif call.data == "clear_buttons":
        if user_id in current_posts:
            current_posts[user_id]['buttons'] = []
            bot.edit_message_text(
                "✅ Barcha tugmalar tozalandi!",
                call.message.chat.id,
                call.message.message_id,
                reply_markup=get_post_management_keyboard(user_id)
            )
    
    # Post yuborish
    elif call.data == "send_post":
        if user_id in current_posts and current_posts[user_id]['post_data']:
            # Post preview ko'rsatish
            post_data = current_posts[user_id]['post_data']
            buttons = current_posts[user_id].get('buttons', [])
            
            preview_text = "📤 Post ma'lumotlari:\n\n"
            preview_text += f"📝 Tugmalar soni: {len(buttons)}\n"
            if buttons:
                preview_text += "\nTugmalar:\n"
                for btn in buttons:
                    preview_text += f"• {btn['name']}\n"
            
            bot.edit_message_text(
                preview_text + "\n📤 Yuborishga tayyormisiz?",
                call.message.chat.id,
                call.message.message_id,
                reply_markup=get_send_options()
            )
        else:
            bot.answer_callback_query(call.id, "❌ Avval post yarating!")
    
    # Kanallarni tanlash
    elif call.data == "select_channels":
        if user_id not in current_posts:
            current_posts[user_id] = {'post_data': {}, 'buttons': [], 'selected_channels': []}
        if 'selected_channels' not in current_posts[user_id]:
            current_posts[user_id]['selected_channels'] = []
        
        bot.edit_message_text(
            "🎯 Qaysi kanallarga yuboramiz?",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=get_channels_keyboard(current_posts[user_id]['selected_channels'])
        )
    
    # Barchaga yuborish
    elif call.data == "send_all":
        send_to_channels(call.message, user_id, 'all')
    
    # Tanlanganlarga yuborish
    elif call.data == "confirm_selected":
        if user_id in current_posts and current_posts[user_id].get('selected_channels'):
            send_to_channels(call.message, user_id, 'selected')
        else:
            bot.answer_callback_query(call.id, "❌ Kamida bitta kanal tanlang!")
    
    # Bekor qilish
    elif call.data == "cancel_post":
        if user_id in user_states:
            del user_states[user_id]
        if user_id in current_posts:
            del current_posts[user_id]
        
        bot.edit_message_text(
            "❌ Post yaratish bekor qilindi.",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=get_owner_main_keyboard()
        )
    
    # Orqaga tugmalari
    elif call.data == "back_to_main":
        bot.edit_message_text(
            "👋 Post yaratishni istaysizmi?",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=get_owner_main_keyboard()
        )
    
    elif call.data == "back_to_post":
        if user_id in current_posts and current_posts[user_id]['post_data']:
            bot.edit_message_text(
                "📝 Postingiz tayyor! Tugma qo'shish yoki yuborish mumkin.",
                call.message.chat.id,
                call.message.message_id,
                reply_markup=get_post_management_keyboard(user_id)
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
    
    # Kanal tanlash
    elif call.data.startswith("toggle_"):
        channel_id = call.data.replace("toggle_", "")
        
        if user_id not in current_posts:
            current_posts[user_id] = {'post_data': {}, 'buttons': [], 'selected_channels': []}
        if 'selected_channels' not in current_posts[user_id]:
            current_posts[user_id]['selected_channels'] = []
        
        selected = current_posts[user_id]['selected_channels']
        
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
    
    if user_id not in current_posts:
        current_posts[user_id] = {
            'post_data': {},
            'buttons': []
        }
    
    current_posts[user_id]['post_data'] = post_data
    user_states[user_id] = "post_ready"
    
    # Post preview
    bot.send_message(
        message.chat.id,
        "✅ Post qabul qilindi!\n\n"
        "Endi quyidagi amallarni bajarishingiz mumkin:",
        reply_markup=get_post_management_keyboard(user_id)
    )

# Kanal qo'shish
@bot.message_handler(func=lambda message: message.from_user.id == OWNER_ID and 
                     user_states.get(message.from_user.id) == "waiting_for_channel")
def add_channel(message):
    user_id = message.from_user.id
    channel_id = message.text.strip()
    
    try:
        chat = bot.get_chat(channel_id)
        channel_info = {
            'id': str(chat.id),
            'name': chat.title or channel_id
        }
        
        try:
            bot_member = bot.get_chat_member(chat.id, bot.get_me().id)
            if bot_member.status in ['administrator', 'creator']:
                if not any(ch['id'] == channel_info['id'] for ch in channels):
                    channels.append(channel_info)
                    bot.send_message(
                        message.chat.id,
                        f"✅ Kanal qo'shildi: {channel_info['name']}",
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
        
        if user_id in user_states:
            del user_states[user_id]
            
    except Exception as e:
        bot.send_message(
            message.chat.id,
            f"❌ Xatolik: Kanal topilmadi yoki noto'g'ri ID.\n\n"
            f"To'g'ri format: @kanal_nomi yoki -1001234567890",
            reply_markup=get_owner_main_keyboard()
        )

# Tugma nomini qabul qilish
def process_button_name(message):
    user_id = message.from_user.id
    if message.text:
        user_states[user_id] = "waiting_for_button_url"
        # Vaqtinchalik saqlash
        user_states[f"{user_id}_btn_name"] = message.text
        msg = bot.send_message(message.chat.id, "🔗 Tugma URL manzilini kiriting:")
        bot.register_next_step_handler(msg, process_button_url)
    else:
        msg = bot.send_message(message.chat.id, "❌ Iltimos, tugma nomini matn ko'rinishida kiriting!")
        bot.register_next_step_handler(msg, process_button_name)

# Tugma URL qabul qilish
def process_button_url(message):
    user_id = message.from_user.id
    if message.text:
        btn_name = user_states.get(f"{user_id}_btn_name", "")
        btn_url = message.text
        
        # Post uchun tugma qo'shish
        if user_id not in current_posts:
            current_posts[user_id] = {
                'post_data': {},
                'buttons': []
            }
        
        current_posts[user_id]['buttons'].append({
            'name': btn_name,
            'url': btn_url
        })
        
        # Tozalash
        if user_id in user_states:
            del user_states[user_id]
        if f"{user_id}_btn_name" in user_states:
            del user_states[f"{user_id}_btn_name"]
        
        # Ko'rsatish
        buttons_count = len(current_posts[user_id]['buttons'])
        bot.send_message(
            message.chat.id,
            f"✅ Tugma qo'shildi!\n\n"
            f"📝 Nomi: {btn_name}\n"
            f"🔗 URL: {btn_url}\n"
            f"📊 Jami tugmalar: {buttons_count}",
            reply_markup=get_post_management_keyboard(user_id)
        )
    else:
        msg = bot.send_message(message.chat.id, "❌ Iltimos, URL manzilini matn ko'rinishida kiriting!")
        bot.register_next_step_handler(msg, process_button_url)

# Kanallarga yuborish
def send_to_channels(message, user_id, send_type):
    if user_id not in current_posts or not current_posts[user_id]['post_data']:
        bot.send_message(message.chat.id, "❌ Post topilmadi!")
        return
    
    post_data = current_posts[user_id]['post_data']
    buttons = current_posts[user_id].get('buttons', [])
    
    # Inline keyboard yaratish
    inline_markup = None
    if buttons:
        inline_markup = types.InlineKeyboardMarkup(row_width=1)
        for btn in buttons:
            inline_markup.add(types.InlineKeyboardButton(btn['name'], url=btn['url']))
    
    if send_type == 'all':
        target_channels = channels
    else:
        selected_ids = current_posts[user_id].get('selected_channels', [])
        target_channels = [ch for ch in channels if ch['id'] in selected_ids]
    
    sent_count = 0
    failed_channels = []
    
    for channel in target_channels:
        try:
            # Postni forward qilish
            forwarded = bot.forward_message(
                chat_id=channel['id'],
                from_chat_id=post_data['from_chat_id'],
                message_id=post_data['message_id']
            )
            
            # Agar tugmalar bo'lsa, post ostiga qo'shish
            if inline_markup:
                # Forward qilingan post uchun tugmalar to'g'ridan-to'g'ri qo'shila olmaydi
                # Shuning uchun alohida xabar yuboramiz
                bot.send_message(
                    chat_id=channel['id'],
                    text="🔗 Havolalar:",
                    reply_markup=inline_markup,
                    reply_to_message_id=forwarded.message_id
                )
            
            sent_count += 1
        except Exception as e:
            failed_channels.append(f"{channel['name']}: {str(e)}")
    
    # Natijani ko'rsatish
    result_text = f"✅ {sent_count}/{len(target_channels)} kanalga yuborildi!"
    if failed_channels:
        result_text += "\n\n❌ Xatoliklar:\n"
        for fail in failed_channels:
            result_text += f"• {fail}\n"
    
    bot.edit_message_text(
        result_text,
        message.chat.id,
        message.message_id,
        reply_markup=get_owner_main_keyboard()
    )
    
    # Tozalash
    if user_id in current_posts:
        del current_posts[user_id]

# Webhook
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
    if WEBHOOK_URL:
        bot.remove_webhook()
        time.sleep(1)
        bot.set_webhook(url=f"{WEBHOOK_URL}/{TOKEN}")
    
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
