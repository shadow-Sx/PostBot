import os
import json
import telebot
from telebot import types
from flask import Flask, request
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
# current_post endi list - bir nechta post saqlash uchun
user_posts = {}  # {user_id: [{'message_id': ..., 'chat_id': ..., 'buttons': [...]}, ...]}
channels = []


# Kanallarni JSON formatida olish
def get_channels_json():
    return json.dumps(channels, ensure_ascii=False, indent=2)


# Kanallar faylini yuborish
def send_channels_file(chat_id):
    if channels:
        json_str = get_channels_json()
        
        with open('channels_backup.json', 'w', encoding='utf-8') as f:
            f.write(json_str)
        
        with open('channels_backup.json', 'rb') as f:
            bot.send_document(
                chat_id,
                f,
                caption=f"📋 Kanallar ro'yxati ({len(channels)} ta kanal)\n\n"
                       f"Bu faylni saqlab qo'ying. Bot qayta ishga tushganda \"📂 Kanallar fayli\" bo'limiga yuboring.",
                visible_file_name="channels_backup.json"
            )
        
        if os.path.exists('channels_backup.json'):
            os.remove('channels_backup.json')
    else:
        bot.send_message(chat_id, "❌ Hali hech qanday kanal qo'shilmagan!")


# Keyboard'lar
def get_owner_main_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    btn_create = types.KeyboardButton("📝 Post yaratish")
    btn_add_channel = types.KeyboardButton("➕ Kanal qo'shish")
    markup.add(btn_create, btn_add_channel)
    
    # 2-bo'lim
    btn_channels = types.KeyboardButton("📋 Kanallar ro'yxati")
    btn_delete_channel = types.KeyboardButton("🗑 Kanal o'chirish")
    btn_download = types.KeyboardButton("💾 Kanallar faylini yuklash")
    btn_upload = types.KeyboardButton("📂 Kanallar fayli")
    markup.add(btn_channels, btn_delete_channel)
    markup.add(btn_download, btn_upload)
    
    return markup


def get_post_buttons():
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_add_button = types.InlineKeyboardButton("🔗 Tugma qo'shish", callback_data="add_button")
    btn_done = types.InlineKeyboardButton("✅ Tugmalar tayyor", callback_data="buttons_done")
    markup.add(btn_add_button, btn_done)
    return markup


def get_send_options():
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_select = types.InlineKeyboardButton("🎯 Tanlash", callback_data="select_channels")
    btn_all = types.InlineKeyboardButton("📢 Barchaga", callback_data="send_all")
    btn_back = types.InlineKeyboardButton("⬅️ Orqaga", callback_data="back_to_main")
    markup.add(btn_select, btn_all, btn_back)
    return markup


def get_channels_keyboard(selected_channels=None, delete_mode=False):
    if selected_channels is None:
        selected_channels = []
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    for channel in channels:
        if delete_mode:
            btn_text = f"🗑 {channel['name']} ({channel['id']})"
            btn = types.InlineKeyboardButton(btn_text, callback_data=f"delete_ch_{channel['id']}")
        else:
            check = "✅ " if channel['id'] in selected_channels else "⬜ "
            btn_text = f"{check}{channel['name']}"
            btn = types.InlineKeyboardButton(btn_text, callback_data=f"toggle_{channel['id']}")
        markup.add(btn)
    
    if delete_mode:
        btn_back = types.InlineKeyboardButton("⬅️ Orqaga", callback_data="back_to_main")
        markup.add(btn_back)
    else:
        btn_done = types.InlineKeyboardButton("✅ Tayyor - Yuborish", callback_data="confirm_selected")
        btn_back = types.InlineKeyboardButton("⬅️ Orqaga", callback_data="back_to_main")
        markup.add(btn_done, btn_back)
    
    return markup


def get_confirm_delete_keyboard(channel_id, channel_name):
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_yes = types.InlineKeyboardButton("✅ Ha", callback_data=f"confirm_del_{channel_id}")
    btn_no = types.InlineKeyboardButton("❌ Yo'q", callback_data="back_to_main")
    markup.add(btn_yes, btn_no)
    return markup


def is_owner(user_id):
    return user_id == OWNER_ID


# Start komandasi
@bot.message_handler(commands=['start'])
def start_command(message):
    if is_owner(message.from_user.id):
        bot.send_message(
            message.chat.id,
            "👋 Salom, xo'jayin! Kerakli amalni tanlang:",
            reply_markup=get_owner_main_keyboard()
        )
    else:
        bot.send_message(
            message.chat.id,
            "Bot faqat egasi uchun ishlaydi (@Shadow_sxi)"
        )


# Oddiy tugmalar handleri
@bot.message_handler(func=lambda message: is_owner(message.from_user.id))
def handle_buttons(message):
    user_id = message.from_user.id
    text = message.text
    
    if text == "📝 Post yaratish":
        user_states[user_id] = "waiting_for_post"
        if user_id not in user_posts:
            user_posts[user_id] = []
        bot.send_message(
            message.chat.id,
            "📝 Post yuboring (matn, rasm, video, gif, sticker, fayl, ovozli xabar)\n\n"
            "Bir nechta post yuborishingiz mumkin.\n"
            "Tayyor bo'lgach, /done deb yozing",
            reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add(
                types.KeyboardButton("✅ Tayyor"),
                types.KeyboardButton("❌ Bekor qilish")
            )
        )
    
    elif text == "➕ Kanal qo'shish":
        user_states[user_id] = "waiting_for_channel"
        bot.send_message(
            message.chat.id,
            "➕ Kanal ID sini kiriting:\n\n"
            "Masalan: @kanal_nomi yoki -1001234567890\n\n"
            "❗️ Bot kanalda admin bo'lishi kerak!",
            reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add(
                types.KeyboardButton("⬅️ Bekor qilish")
            )
        )
    
    elif text == "📋 Kanallar ro'yxati":
        if channels:
            text_msg = "📋 Mening kanallarim:\n\n"
            for i, ch in enumerate(channels, 1):
                text_msg += f"{i}. {ch['name']} - <code>{ch['id']}</code>\n"
            text_msg += f"\nJami: <b>{len(channels)}</b> ta kanal"
            bot.send_message(message.chat.id, text_msg, parse_mode='HTML')
        else:
            bot.send_message(message.chat.id, "❌ Hali hech qanday kanal qo'shilmagan.")
    
    elif text == "🗑 Kanal o'chirish":
        if channels:
            bot.send_message(
                message.chat.id,
                "🗑 Qaysi kanalni o'chirmoqchisiz?",
                reply_markup=get_channels_keyboard(delete_mode=True)
            )
        else:
            bot.send_message(message.chat.id, "O'chirish uchun kanallar mavjud emas!")
    
    elif text == "💾 Kanallar faylini yuklash":
        send_channels_file(message.chat.id)
    
    elif text == "📂 Kanallar fayli":
        user_states[user_id] = "waiting_for_channels_file"
        bot.send_message(
            message.chat.id,
            "📂 Iltimos, kanallar JSON faylini yuboring:\n\n"
            "(Oldin yuklab olingan channels_backup.json faylini yuboring)",
            reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add(
                types.KeyboardButton("⬅️ Bekor qilish")
            )
        )
    
    elif text == "✅ Tayyor":
        if user_id in user_states and user_states[user_id] == "waiting_for_post":
            if user_id in user_posts and user_posts[user_id]:
                del user_states[user_id]
                bot.send_message(
                    message.chat.id,
                    f"📝 {len(user_posts[user_id])} ta post tayyor!",
                    reply_markup=get_owner_main_keyboard()
                )
                # Har bir postni ko'rsatish va tugmalar so'rash
                show_post_preview(message)
            else:
                bot.send_message(message.chat.id, "❌ Hech qanday post yubormadingiz!")
    
    elif text == "❌ Bekor qilish" or text == "⬅️ Bekor qilish":
        if user_id in user_states:
            del user_states[user_id]
        if user_id in user_posts:
            del user_posts[user_id]
        bot.send_message(
            message.chat.id,
            "❌ Bekor qilindi.",
            reply_markup=get_owner_main_keyboard()
        )


def show_post_preview(message):
    user_id = message.from_user.id
    posts = user_posts.get(user_id, [])
    
    for i, post in enumerate(posts, 1):
        # Postni nusxalash (forward o'rniga copy)
        try:
            # Copy message
            bot.copy_message(
                chat_id=message.chat.id,
                from_chat_id=post['chat_id'],
                message_id=post['message_id']
            )
            
            # Tugmalar so'rash
            markup = types.InlineKeyboardMarkup()
            btn_add = types.InlineKeyboardButton(f"🔗 Post #{i} ga tugma qo'shish", callback_data=f"add_btn_{i}")
            btn_skip = types.InlineKeyboardButton(f"⏭ Post #{i} ni o'tkazish", callback_data=f"skip_btn_{i}")
            markup.add(btn_add, btn_skip)
            
            bot.send_message(
                message.chat.id,
                f"Post #{i} uchun tugma qo'shish kerakmi?",
                reply_markup=markup
            )
        except Exception as e:
            bot.send_message(message.chat.id, f"Post #{i} ko'rsatishda xatolik: {str(e)}")
    
    # Yuborish tugmasi
    markup = types.InlineKeyboardMarkup()
    btn_send = types.InlineKeyboardButton("📤 Barcha postlarni yuborish", callback_data="send_all_posts")
    btn_cancel = types.InlineKeyboardButton("❌ Bekor qilish", callback_data="cancel_post")
    markup.add(btn_send, btn_cancel)
    
    bot.send_message(message.chat.id, "Postlar tayyor!", reply_markup=markup)


# Callback handler
@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    if not is_owner(call.from_user.id):
        bot.answer_callback_query(call.id, "Siz bot egasi emassiz!")
        return
    
    user_id = call.from_user.id
    
    # Post uchun tugma qo'shish
    if call.data.startswith("add_btn_"):
        post_index = int(call.data.replace("add_btn_", "")) - 1
        user_states[user_id] = f"waiting_for_button_name_{post_index}"
        msg = bot.edit_message_text(
            f"🔗 Post #{post_index + 1} uchun tugma nomini kiriting:",
            call.message.chat.id,
            call.message.message_id
        )
        bot.register_next_step_handler(msg, process_button_name, post_index)
    
    elif call.data.startswith("skip_btn_"):
        post_index = int(call.data.replace("skip_btn_", "")) - 1
        if 'buttons' not in user_posts[user_id][post_index]:
            user_posts[user_id][post_index]['buttons'] = []
        bot.edit_message_text(
            f"Post #{post_index + 1} tugmalarsiz tayyor.",
            call.message.chat.id,
            call.message.message_id
        )
    
    elif call.data == "send_all_posts":
        bot.edit_message_text(
            "📤 Yuborishga tayyormisiz?",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=get_send_options()
        )
    
    elif call.data == "send_all":
        send_all_posts_to_all_channels(call.message)
    
    elif call.data == "select_channels":
        user_states[user_id] = "selecting_channels"
        if 'selected_channels' not in locals():
            selected = []
        else:
            selected = []
        
        bot.edit_message_text(
            "🎯 Qaysi kanallarga yuboramiz?",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=get_channels_keyboard(selected)
        )
    
    elif call.data == "confirm_selected":
        if 'selected_channels' in locals() and selected:
            send_posts_to_selected_channels(call.message, selected)
        else:
            bot.answer_callback_query(call.id, "❌ Kamida bitta kanal tanlang!")
    
    elif call.data == "cancel_post":
        if user_id in user_states:
            del user_states[user_id]
        if user_id in user_posts:
            del user_posts[user_id]
        
        bot.edit_message_text(
            "❌ Bekor qilindi.",
            call.message.chat.id,
            call.message.message_id
        )
        bot.send_message(
            call.message.chat.id,
            "Kerakli amalni tanlang:",
            reply_markup=get_owner_main_keyboard()
        )
    
    elif call.data == "back_to_main":
        bot.edit_message_text(
            "👋 Kerakli amalni tanlang:",
            call.message.chat.id,
            call.message.message_id
        )
        bot.send_message(
            call.message.chat.id,
            "...",
            reply_markup=get_owner_main_keyboard()
        )
    
    elif call.data.startswith("delete_ch_"):
        channel_id = call.data.replace("delete_ch_", "")
        channel = next((ch for ch in channels if ch['id'] == channel_id), None)
        
        if channel:
            bot.edit_message_text(
                f"❗️ Rostdan ham '<b>{channel['name']}</b>' kanalini o'chirmoqchimisiz?",
                call.message.chat.id,
                call.message.message_id,
                reply_markup=get_confirm_delete_keyboard(channel_id, channel['name']),
                parse_mode='HTML'
            )
    
    elif call.data.startswith("confirm_del_"):
        channel_id = call.data.replace("confirm_del_", "")
        channels[:] = [ch for ch in channels if ch['id'] != channel_id]
        
        bot.edit_message_text(
            "✅ Kanal muvaffaqiyatli o'chirildi!",
            call.message.chat.id,
            call.message.message_id
        )
        send_channels_file(call.message.chat.id)
    
    elif call.data.startswith("toggle_"):
        channel_id = call.data.replace("toggle_", "")
        # Bu qismni soddalashtirish kerak...
        bot.answer_callback_query(call.id, "✅ Tanlandi")
    
    bot.answer_callback_query(call.id)


# Post qabul qilish (bir nechta post)
@bot.message_handler(func=lambda message: is_owner(message.from_user.id) and 
                     user_states.get(message.from_user.id) == "waiting_for_post",
                     content_types=['text', 'photo', 'video', 'animation', 'sticker', 
                                  'document', 'audio', 'voice', 'video_note'])
def receive_post(message):
    user_id = message.from_user.id
    
    post_data = {
        'chat_id': message.chat.id,
        'message_id': message.message_id,
        'content_type': message.content_type,
        'from_chat_id': message.chat.id,
        'buttons': []
    }
    
    if user_id not in user_posts:
        user_posts[user_id] = []
    
    user_posts[user_id].append(post_data)
    
    # Postni qayta yuborish (forward emas, copy)
    bot.copy_message(
        chat_id=message.chat.id,
        from_chat_id=message.chat.id,
        message_id=message.message_id
    )
    
    bot.send_message(
        message.chat.id,
        f"✅ Post qabul qilindi! ({len(user_posts[user_id])} ta post)\n"
        "Yana post yuboring yoki /done yoki \"✅ Tayyor\" tugmasini bosing."
    )


def process_button_name(message, post_index):
    user_id = message.from_user.id
    if message.text:
        user_states[user_id] = f"waiting_for_button_url_{post_index}"
        temp_button = {'name': message.text, 'url': ''}
        msg = bot.send_message(message.chat.id, "🔗 Tugma URL manzilini kiriting:")
        bot.register_next_step_handler(msg, process_button_url, post_index, temp_button)


def process_button_url(message, post_index, temp_button):
    user_id = message.from_user.id
    if message.text:
        temp_button['url'] = message.text
        
        if 'buttons' not in user_posts[user_id][post_index]:
            user_posts[user_id][post_index]['buttons'] = []
        
        user_posts[user_id][post_index]['buttons'].append(temp_button)
        
        # Tugmalar ro'yxatini ko'rsatish
        buttons_text = "📋 Qo'shilgan tugmalar:\n"
        for i, btn in enumerate(user_posts[user_id][post_index]['buttons'], 1):
            buttons_text += f"{i}. {btn['name']} - {btn['url']}\n"
        
        markup = types.InlineKeyboardMarkup(row_width=2)
        btn_add = types.InlineKeyboardButton("➕ Yana tugma qo'shish", callback_data=f"add_btn_{post_index + 1}")
        btn_done = types.InlineKeyboardButton("✅ Tugmalar tayyor", callback_data=f"skip_btn_{post_index + 1}")
        markup.add(btn_add, btn_done)
        
        bot.send_message(message.chat.id, buttons_text, reply_markup=markup)


def send_all_posts_to_all_channels(message):
    user_id = message.chat.id
    
    if not channels:
        bot.send_message(message.chat.id, "❌ Avval kanal qo'shing!")
        return
    
    if user_id not in user_posts or not user_posts[user_id]:
        bot.send_message(message.chat.id, "❌ Post topilmadi!")
        return
    
    posts = user_posts[user_id]
    total_sent = 0
    
    for channel in channels:
        try:
            for post in posts:
                send_single_post_to_channel(post, channel['id'])
                total_sent += 1
                time.sleep(0.5)
        except Exception as e:
            bot.send_message(
                user_id,
                f"❌ {channel['name']} kanaliga yuborishda xatolik: {str(e)}"
            )
    
    bot.send_message(
        user_id,
        f"✅ {len(posts)} ta post {len(channels)} ta kanalga yuborildi!\nJami: {total_sent} ta",
        reply_markup=get_owner_main_keyboard()
    )


def send_single_post_to_channel(post, channel_id):
    # Forward o'rniga copy_message ishlatamiz
    bot.copy_message(
        chat_id=channel_id,
        from_chat_id=post['from_chat_id'],
        message_id=post['message_id']
    )
    
    # Agar tugmalar bo'lsa, qo'shimcha xabar
    if post.get('buttons'):
        # Tugmalarni yaratish
        markup = types.InlineKeyboardMarkup(row_width=2)
        buttons = post['buttons']
        
        # Tugmalarni juft-juft qilish
        for i in range(0, len(buttons), 2):
            row = []
            row.append(types.InlineKeyboardButton(buttons[i]['name'], url=buttons[i]['url']))
            if i + 1 < len(buttons):
                row.append(types.InlineKeyboardButton(buttons[i+1]['name'], url=buttons[i+1]['url']))
            markup.add(*row)
        
        bot.send_message(
            chat_id=channel_id,
            text="🔗 Havolalar:",
            reply_markup=markup
        )


# Fayl qabul qilish handleri
@bot.message_handler(content_types=['document'],
                     func=lambda message: is_owner(message.from_user.id) and 
                     user_states.get(message.from_user.id) == "waiting_for_channels_file")
def receive_channels_file(message):
    user_id = message.from_user.id
    
    try:
        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        channels_data = json.loads(downloaded_file.decode('utf-8'))
        
        if isinstance(channels_data, list):
            new_channels = []
            for ch in channels_data:
                if isinstance(ch, dict) and 'id' in ch and 'name' in ch:
                    if not any(existing['id'] == ch['id'] for existing in channels):
                        new_channels.append(ch)
            
            channels.extend(new_channels)
            
            del user_states[user_id]
            
            bot.send_message(
                message.chat.id,
                f"✅ Kanallar muvaffaqiyatli yuklandi!\n\n"
                f"📊 Yangi qo'shilgan kanallar: {len(new_channels)} ta\n"
                f"📊 Jami kanallar: {len(channels)} ta",
                reply_markup=get_owner_main_keyboard()
            )
        else:
            bot.send_message(
                message.chat.id,
                "❌ Noto'g'ri JSON format! Kanallar ro'yxati bo'lishi kerak.",
                reply_markup=get_owner_main_keyboard()
            )
            
    except Exception as e:
        del user_states[user_id]
        bot.send_message(
            message.chat.id,
            f"❌ Xatolik: {str(e)}\n\nIltimos, to'g'ri JSON faylini yuboring.",
            reply_markup=get_owner_main_keyboard()
        )


# Kanal qo'shish
@bot.message_handler(func=lambda message: is_owner(message.from_user.id) and 
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
                        f"✅ Kanal qo'shildi: {channel_info['name']}\n\n"
                        f"ID: <code>{channel_info['id']}</code>\n\n"
                        f"📊 Jami kanallar: {len(channels)} ta",
                        parse_mode='HTML'
                    )
                    
                    send_channels_file(message.chat.id)
                else:
                    bot.send_message(message.chat.id, "⚠️ Bu kanal allaqachon qo'shilgan!")
            else:
                bot.send_message(message.chat.id, "❌ Bot bu kanalda admin emas! Avval botni admin qiling.")
        except:
            bot.send_message(message.chat.id, "❌ Bot bu kanalga qo'shilmagan! Kanalga botni qo'shing va admin qiling.")
        
        del user_states[user_id]
        
    except Exception as e:
        bot.send_message(
            message.chat.id,
            f"❌ Xatolik: Kanal topilmadi yoki noto'g'ri ID.\n\n"
            f"To'g'ri format: @kanal_nomi yoki -1001234567890",
            reply_markup=get_owner_main_keyboard()
        )


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
    port = int(os.environ.get('PORT', 10000))
    
    if WEBHOOK_URL:
        try:
            bot.remove_webhook()
            time.sleep(1)
            bot.set_webhook(url=f"{WEBHOOK_URL}/{TOKEN}")
            print(f"✅ Webhook o'rnatildi: {WEBHOOK_URL}/{TOKEN}")
        except Exception as e:
            print(f"❌ Webhook xatolik: {e}")
    
    app.run(host='0.0.0.0', port=port)