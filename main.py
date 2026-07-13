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
user_posts = {}
channels = []
selected_channels_temp = {}  # {user_id: [channel_ids]}


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


def get_send_options():
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_select = types.InlineKeyboardButton("🎯 Tanlash", callback_data="select_channels")
    btn_all = types.InlineKeyboardButton("📢 Barchaga", callback_data="send_all")
    btn_back = types.InlineKeyboardButton("⬅️ Orqaga", callback_data="cancel_send")
    markup.add(btn_select, btn_all, btn_back)
    return markup


def get_channels_keyboard(user_id, delete_mode=False):
    if user_id not in selected_channels_temp:
        selected_channels_temp[user_id] = []
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    
    for channel in channels:
        if delete_mode:
            btn_text = f"🗑 {channel['name']}"
            btn = types.InlineKeyboardButton(btn_text, callback_data=f"delete_ch_{channel['id']}")
        else:
            # Tanlangan kanallar uchun ✅, tanlanmaganlar uchun ⭕
            is_selected = channel['id'] in selected_channels_temp[user_id]
            icon = "✅" if is_selected else "⭕"
            btn_text = f"{icon} {channel['name']}"
            btn = types.InlineKeyboardButton(btn_text, callback_data=f"toggle_{channel['id']}")
        markup.add(btn)
    
    if delete_mode:
        btn_back = types.InlineKeyboardButton("⬅️ Orqaga", callback_data="back_to_main")
        markup.add(btn_back)
    else:
        # Tanlanganlar sonini ko'rsatish
        selected_count = len(selected_channels_temp[user_id])
        btn_done = types.InlineKeyboardButton(f"✅ Tayyor ({selected_count} ta kanal) - Yuborish", callback_data="confirm_selected")
        btn_back = types.InlineKeyboardButton("⬅️ Orqaga", callback_data="cancel_send")
        markup.add(btn_done, btn_back)
    
    return markup


def get_confirm_delete_keyboard(channel_id, channel_name):
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_yes = types.InlineKeyboardButton("✅ Ha, o'chirish", callback_data=f"confirm_del_{channel_id}")
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


# /done komandasi
@bot.message_handler(commands=['done'])
def done_command(message):
    if is_owner(message.from_user.id):
        user_id = message.from_user.id
        if user_id in user_states and user_states[user_id] == "waiting_for_post":
            if user_id in user_posts and user_posts[user_id]:
                del user_states[user_id]
                bot.send_message(
                    message.chat.id,
                    f"📝 {len(user_posts[user_id])} ta post tayyor!",
                    reply_markup=get_owner_main_keyboard()
                )
                show_post_preview(message)
            else:
                bot.send_message(message.chat.id, "❌ Hech qanday post yubormadingiz!")
        else:
            bot.send_message(message.chat.id, "❌ Siz post yaratish rejimida emassiz!")


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
            "<b>HTML kodlaridan foydalanishingiz mumkin!</b>\n"
            "Masalan: <code>&lt;b&gt;Qalin&lt;/b&gt;</code>, <code>&lt;i&gt;Kursiv&lt;/i&gt;</code>\n\n"
            "Bir nechta post yuborishingiz mumkin.\n"
            "Tayyor bo'lgach, <b>/done</b> deb yozing yoki \"✅ Tayyor\" tugmasini bosing",
            parse_mode='HTML',
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
                reply_markup=get_channels_keyboard(user_id, delete_mode=True)
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
        try:
            # Postni ko'chirib yuborish (HTML bilan)
            bot.copy_message(
                chat_id=message.chat.id,
                from_chat_id=post['chat_id'],
                message_id=post['message_id']
            )
            
            # Agar matnli post bo'lsa va HTML teglari bo'lsa
            if post.get('text'):
                bot.send_message(
                    message.chat.id,
                    f"Post #{i} (HTML ko'rinishi):",
                    reply_markup=None
                )
            
            # Tugmalar so'rash
            markup = types.InlineKeyboardMarkup()
            btn_add = types.InlineKeyboardButton(f"🔗 Post #{i} ga tugma qo'shish", callback_data=f"add_btn_{i}")
            btn_skip = types.InlineKeyboardButton(f"⏭ Post #{i} ni o'tkazish", callback_data=f"skip_btn_{i}")
            markup.add(btn_add, btn_skip)
            
            buttons_count = len(post.get('buttons', []))
            btn_text = f"Post #{i}"
            if buttons_count > 0:
                btn_text += f" ({buttons_count} ta tugma)"
            btn_text += " uchun tugma qo'shish kerakmi?"
            
            bot.send_message(
                message.chat.id,
                btn_text,
                reply_markup=markup
            )
        except Exception as e:
            bot.send_message(message.chat.id, f"Post #{i} ko'rsatishda xatolik: {str(e)}")
    
    # Yuborish tugmasi
    markup = types.InlineKeyboardMarkup()
    btn_send = types.InlineKeyboardButton("📤 Barcha postlarni yuborish", callback_data="send_all_posts")
    btn_cancel = types.InlineKeyboardButton("❌ Bekor qilish", callback_data="cancel_post")
    markup.add(btn_send, btn_cancel)
    
    bot.send_message(message.chat.id, "Postlar tayyor! Yuborishni xohlaysizmi?", reply_markup=markup)


# Callback handler
@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    if not is_owner(call.from_user.id):
        bot.answer_callback_query(call.id, "Siz bot egasi emassiz!")
        return
    
    user_id = call.from_user.id
    data = call.data
    
    # Post uchun tugma qo'shish
    if data.startswith("add_btn_"):
        post_index = int(data.replace("add_btn_", "")) - 1
        if post_index < len(user_posts.get(user_id, [])):
            user_states[user_id] = f"waiting_for_button_name_{post_index}"
            msg = bot.edit_message_text(
                f"🔗 Post #{post_index + 1} uchun tugma nomini kiriting:",
                call.message.chat.id,
                call.message.message_id
            )
            bot.register_next_step_handler(msg, process_button_name, post_index)
    
    elif data.startswith("skip_btn_"):
        post_index = int(data.replace("skip_btn_", "")) - 1
        if post_index < len(user_posts.get(user_id, [])):
            if 'buttons' not in user_posts[user_id][post_index]:
                user_posts[user_id][post_index]['buttons'] = []
            bot.edit_message_text(
                f"✅ Post #{post_index + 1} tugmalarsiz tayyor.",
                call.message.chat.id,
                call.message.message_id
            )
    
    elif data == "send_all_posts":
        if user_id in user_posts and user_posts[user_id]:
            bot.edit_message_text(
                "📤 Yuborish usulini tanlang:",
                call.message.chat.id,
                call.message.message_id,
                reply_markup=get_send_options()
            )
        else:
            bot.answer_callback_query(call.id, "❌ Post topilmadi!")
    
    elif data == "send_all":
        send_all_posts_to_all_channels(call.message)
    
    elif data == "select_channels":
        if user_id not in selected_channels_temp:
            selected_channels_temp[user_id] = []
        
        bot.edit_message_text(
            "🎯 Qaysi kanallarga yuboramiz?\n\n"
            "Kanal ustiga bosib tanlang:",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=get_channels_keyboard(user_id)
        )
    
    elif data == "confirm_selected":
        if user_id in selected_channels_temp and selected_channels_temp[user_id]:
            send_posts_to_selected_channels(call.message, selected_channels_temp[user_id])
            # Tozalash
            selected_channels_temp[user_id] = []
        else:
            bot.answer_callback_query(call.id, "❌ Kamida bitta kanal tanlang!")
    
    elif data == "cancel_post" or data == "cancel_send":
        if user_id in user_states:
            del user_states[user_id]
        if user_id in user_posts:
            del user_posts[user_id]
        if user_id in selected_channels_temp:
            selected_channels_temp[user_id] = []
        
        try:
            bot.edit_message_text(
                "❌ Bekor qilindi.",
                call.message.chat.id,
                call.message.message_id
            )
        except:
            pass
        
        bot.send_message(
            call.message.chat.id,
            "Kerakli amalni tanlang:",
            reply_markup=get_owner_main_keyboard()
        )
    
    elif data == "back_to_main":
        try:
            bot.edit_message_text(
                "👋 Kerakli amalni tanlang:",
                call.message.chat.id,
                call.message.message_id
            )
        except:
            pass
        
        bot.send_message(
            call.message.chat.id,
            "Menu:",
            reply_markup=get_owner_main_keyboard()
        )
    
    elif data.startswith("delete_ch_"):
        channel_id = data.replace("delete_ch_", "")
        channel = next((ch for ch in channels if ch['id'] == channel_id), None)
        
        if channel:
            bot.edit_message_text(
                f"❗️ Rostdan ham '<b>{channel['name']}</b>' kanalini o'chirmoqchimisiz?",
                call.message.chat.id,
                call.message.message_id,
                reply_markup=get_confirm_delete_keyboard(channel_id, channel['name']),
                parse_mode='HTML'
            )
    
    elif data.startswith("confirm_del_"):
        channel_id = data.replace("confirm_del_", "")
        channel_name = next((ch['name'] for ch in channels if ch['id'] == channel_id), "Noma'lum")
        channels[:] = [ch for ch in channels if ch['id'] != channel_id]
        
        bot.edit_message_text(
            f"✅ <b>{channel_name}</b> kanali o'chirildi!",
            call.message.chat.id,
            call.message.message_id,
            parse_mode='HTML'
        )
        send_channels_file(call.message.chat.id)
    
    elif data.startswith("toggle_"):
        channel_id = data.replace("toggle_", "")
        
        if user_id not in selected_channels_temp:
            selected_channels_temp[user_id] = []
        
        if channel_id in selected_channels_temp[user_id]:
            selected_channels_temp[user_id].remove(channel_id)
        else:
            selected_channels_temp[user_id].append(channel_id)
        
        # Keyboardni yangilash
        bot.edit_message_text(
            "🎯 Qaysi kanallarga yuboramiz?\n\n"
            f"Tanlangan: {len(selected_channels_temp[user_id])} ta kanal",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=get_channels_keyboard(user_id)
        )
    
    elif data == "buttons_done":
        bot.edit_message_text(
            "✅ Tugmalar tayyor!",
            call.message.chat.id,
            call.message.message_id
        )
    
    bot.answer_callback_query(call.id)


# Post qabul qilish (bir nechta post, HTML bilan)
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
        'buttons': [],
        'text': message.text if message.content_type == 'text' else None
    }
    
    if user_id not in user_posts:
        user_posts[user_id] = []
    
    user_posts[user_id].append(post_data)
    
    # Postni ko'chirib yuborish (HTML formatida)
    try:
        if message.content_type == 'text':
            # Matnli postni HTML bilan yuborish
            bot.send_message(
                chat_id=message.chat.id,
                text=message.text,
                parse_mode='HTML',
                disable_web_page_preview=True
            )
        else:
            # Boshqa turdagi postlarni copy qilish
            bot.copy_message(
                chat_id=message.chat.id,
                from_chat_id=message.chat.id,
                message_id=message.message_id
            )
    except Exception as e:
        # Agar HTML xatolik bo'lsa, oddiy copy qilish
        bot.copy_message(
            chat_id=message.chat.id,
            from_chat_id=message.chat.id,
            message_id=message.message_id
        )
    
    bot.send_message(
        message.chat.id,
        f"✅ Post qabul qilindi! ({len(user_posts[user_id])} ta post)\n"
        "Yana post yuboring yoki <b>/done</b> yoki \"✅ Tayyor\" tugmasini bosing.",
        parse_mode='HTML'
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
        buttons_text = f"📋 Post #{post_index + 1} uchun qo'shilgan tugmalar:\n\n"
        for i, btn in enumerate(user_posts[user_id][post_index]['buttons'], 1):
            buttons_text += f"{i}. <b>{btn['name']}</b>\n   {btn['url']}\n"
        
        buttons_text += f"\nJami: {len(user_posts[user_id][post_index]['buttons'])} ta tugma"
        
        markup = types.InlineKeyboardMarkup(row_width=2)
        btn_add = types.InlineKeyboardButton("➕ Yana tugma qo'shish", callback_data=f"add_btn_{post_index + 1}")
        btn_done = types.InlineKeyboardButton("✅ Tugmalar tayyor", callback_data=f"skip_btn_{post_index + 1}")
        markup.add(btn_add, btn_done)
        
        bot.send_message(message.chat.id, buttons_text, parse_mode='HTML', reply_markup=markup)


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


def send_posts_to_selected_channels(message, selected_channel_ids):
    user_id = message.chat.id
    
    if user_id not in user_posts or not user_posts[user_id]:
        bot.send_message(message.chat.id, "❌ Post topilmadi!")
        return
    
    posts = user_posts[user_id]
    total_sent = 0
    
    for ch_id in selected_channel_ids:
        channel = next((ch for ch in channels if ch['id'] == ch_id), None)
        if channel:
            try:
                for post in posts:
                    send_single_post_to_channel(post, ch_id)
                    total_sent += 1
                    time.sleep(0.5)
            except Exception as e:
                bot.send_message(
                    user_id,
                    f"❌ {channel['name']} kanaliga yuborishda xatolik: {str(e)}"
                )
    
    bot.edit_message_text(
        f"✅ {len(posts)} ta post {len(selected_channel_ids)} ta kanalga yuborildi!\nJami: {total_sent} ta",
        message.chat.id,
        message.message_id
    )
    bot.send_message(
        user_id,
        "Kerakli amalni tanlang:",
        reply_markup=get_owner_main_keyboard()
    )


def send_single_post_to_channel(post, channel_id):
    # Post turiga qarab yuborish
    try:
        if post['content_type'] == 'text' and post.get('text'):
            # Matnli postni HTML formatida yuborish
            bot.send_message(
                chat_id=channel_id,
                text=post['text'],
                parse_mode='HTML',
                disable_web_page_preview=True
            )
        else:
            # Boshqa turdagi postlarni copy qilish
            bot.copy_message(
                chat_id=channel_id,
                from_chat_id=post['from_chat_id'],
                message_id=post['message_id']
            )
        
        # Agar tugmalar bo'lsa, qo'shimcha xabar
        if post.get('buttons'):
            markup = types.InlineKeyboardMarkup(row_width=2)
            buttons = post['buttons']
            
            # Tugmalarni yonma-yon qilish (juft-juft)
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
    except Exception as e:
        # Agar HTML xatolik bo'lsa, oddiy copy qilish
        bot.copy_message(
            chat_id=channel_id,
            from_chat_id=post['from_chat_id'],
            message_id=post['message_id']
        )
        
        if post.get('buttons'):
            markup = types.InlineKeyboardMarkup(row_width=2)
            for i in range(0, len(post['buttons']), 2):
                row = []
                row.append(types.InlineKeyboardButton(post['buttons'][i]['name'], url=post['buttons'][i]['url']))
                if i + 1 < len(post['buttons']):
                    row.append(types.InlineKeyboardButton(post['buttons'][i+1]['name'], url=post['buttons'][i+1]['url']))
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
                        f"✅ Kanal qo'shildi: <b>{channel_info['name']}</b>\n\n"
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