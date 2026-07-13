import os
import json
import telebot
from telebot import types
from flask import Flask, request
from dotenv import load_dotenv
import time
import re

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
selected_channels_temp = {}


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
            is_selected = channel['id'] in selected_channels_temp[user_id]
            icon = "✅" if is_selected else "⭕"
            btn_text = f"{icon} {channel['name']}"
            btn = types.InlineKeyboardButton(btn_text, callback_data=f"toggle_{channel['id']}")
        markup.add(btn)
    
    if delete_mode:
        btn_back = types.InlineKeyboardButton("⬅️ Orqaga", callback_data="back_to_main")
        markup.add(btn_back)
    else:
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


# Tugmalarni parse qilish
def parse_buttons(text):
    """Format: Кнопка 1 - http://example1.com | Кнопка 2 - http://example2.com"""
    buttons = []
    lines = text.strip().split('\n')
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # | bilan ajratilgan tugmalar (bir qator)
        parts = line.split('|')
        row_buttons = []
        
        for part in parts:
            part = part.strip()
            if not part:
                continue
            
            # Формат: Кнопка - URL - style:color
            match = re.match(r'^(.+?)\s*-\s*(https?://\S+)(?:\s*-\s*style:(\w+))?$', part)
            if match:
                name = match.group(1).strip()
                url = match.group(2).strip()
                style = match.group(3) or 'default'
                
                row_buttons.append({
                    'name': name,
                    'url': url,
                    'style': style
                })
        
        if row_buttons:
            buttons.append(row_buttons)
    
    return buttons


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
                    f"📝 {len(user_posts[user_id])} ta post tayyor! Endi tugmalarni qo'shing:",
                    reply_markup=get_owner_main_keyboard()
                )
                show_button_input(message)
            else:
                bot.send_message(message.chat.id, "❌ Hech qanday post yubormadingiz!")
        else:
            bot.send_message(message.chat.id, "❌ Siz post yaratish rejimida emassiz!")


def show_button_input(message):
    """Tugmalarni kiritish uchun yo'riqnoma"""
    user_id = message.from_user.id
    
    text = (
        "🔗 <b>Tugmalarni quyidagi formatda yuboring:</b>\n\n"
        "<code>Tugma nomi - https://url.com</code>\n\n"
        "<b>Bir qatorga bir nechta tugma:</b>\n"
        "<code>Tugma 1 - https://url1.com | Tugma 2 - https://url2.com</code>\n\n"
        "<b>Rang qo'shish (ixtiyoriy):</b>\n"
        "<code>Tugma - https://url.com - style:green</code>\n\n"
        "<b>Misol:</b>\n"
        "<code>Kanal - https://t.me/channel | Chat - https://t.me/group\n"
        "Sayt - https://example.com - style:blue</code>\n\n"
        "<i>Agar tugma kerak bo'lmasa, /skip deb yozing</i>"
    )
    
    user_states[user_id] = "waiting_for_buttons"
    
    bot.send_message(
        message.chat.id,
        text,
        parse_mode='HTML',
        reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add(
            types.KeyboardButton("⏭ Tugmalarsiz"),
            types.KeyboardButton("❌ Bekor qilish")
        )
    )


# /skip komandasi
@bot.message_handler(commands=['skip'])
def skip_buttons(message):
    if is_owner(message.from_user.id):
        user_id = message.from_user.id
        if user_id in user_posts and user_posts[user_id]:
            bot.send_message(
                message.chat.id,
                "✅ Tugmalarsiz davom etamiz. Yuborish usulini tanlang:",
                reply_markup=get_owner_main_keyboard()
            )
            show_send_options(message)
        else:
            bot.send_message(message.chat.id, "❌ Avval post yarating!")


def show_send_options(message):
    """Yuborish opsiyalarini ko'rsatish"""
    bot.send_message(
        message.chat.id,
        "📤 Yuborish usulini tanlang:",
        reply_markup=get_send_options()
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
            "<b>HTML kodlaridan foydalanishingiz mumkin!</b>\n"
            "<b>Rasmga caption sifatida HTML yozishingiz mumkin!</b>\n\n"
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
                    f"📝 {len(user_posts[user_id])} ta post tayyor! Endi tugmalarni qo'shing:",
                    reply_markup=get_owner_main_keyboard()
                )
                show_button_input(message)
            else:
                bot.send_message(message.chat.id, "❌ Hech qanday post yubormadingiz!")
    
    elif text == "⏭ Tugmalarsiz":
        if user_id in user_states and user_states[user_id] == "waiting_for_buttons":
            del user_states[user_id]
            for post in user_posts.get(user_id, []):
                post['buttons'] = []
            bot.send_message(
                message.chat.id,
                "✅ Tugmalarsiz davom etamiz.",
                reply_markup=get_owner_main_keyboard()
            )
            show_send_options(message)
    
    elif text == "❌ Bekor qilish" or text == "⬅️ Bekor qilish":
        if user_id in user_states:
            del user_states[user_id]
        if user_id in user_posts:
            del user_posts[user_id]
        if user_id in selected_channels_temp:
            selected_channels_temp[user_id] = []
        bot.send_message(
            message.chat.id,
            "❌ Bekor qilindi.",
            reply_markup=get_owner_main_keyboard()
        )


# Tugmalarni qabul qilish
@bot.message_handler(func=lambda message: is_owner(message.from_user.id) and 
                     user_states.get(message.from_user.id) == "waiting_for_buttons")
def receive_buttons(message):
    user_id = message.from_user.id
    text = message.text
    
    if text in ["⏭ Tugmalarsiz", "❌ Bekor qilish"]:
        return handle_buttons(message)
    
    try:
        buttons = parse_buttons(text)
        
        if buttons:
            # Barcha postlarga bir xil tugmalar
            for post in user_posts.get(user_id, []):
                post['buttons'] = buttons
            
            del user_states[user_id]
            
            # Tugmalarni ko'rsatish
            response = "✅ Tugmalar qo'shildi!\n\n<b>Ko'rinishi:</b>\n"
            for row in buttons:
                row_text = " | ".join([f"{btn['name']} → {btn['url']}" for btn in row])
                response += f"{row_text}\n"
            
            bot.send_message(
                message.chat.id,
                response,
                parse_mode='HTML',
                reply_markup=get_owner_main_keyboard()
            )
            
            show_send_options(message)
        else:
            bot.send_message(
                message.chat.id,
                "❌ Noto'g'ri format! Qaytadan urinib ko'ring:\n\n"
                "<code>Tugma nomi - https://url.com</code>\n\n"
                "Yoki /skip deb yozing",
                parse_mode='HTML'
            )
    except Exception as e:
        bot.send_message(
            message.chat.id,
            f"❌ Xatolik: {str(e)}\n\nTo'g'ri formatda yuboring yoki /skip deb yozing",
            parse_mode='HTML'
        )


# Callback handler
@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    if not is_owner(call.from_user.id):
        bot.answer_callback_query(call.id, "Siz bot egasi emassiz!")
        return
    
    user_id = call.from_user.id
    data = call.data
    
    if data == "send_all":
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
            bot.edit_message_text("❌ Bekor qilindi.", call.message.chat.id, call.message.message_id)
        except:
            pass
        
        bot.send_message(
            call.message.chat.id,
            "Kerakli amalni tanlang:",
            reply_markup=get_owner_main_keyboard()
        )
    
    elif data == "back_to_main":
        try:
            bot.edit_message_text("👋 Kerakli amalni tanlang:", call.message.chat.id, call.message.message_id)
        except:
            pass
        bot.send_message(call.message.chat.id, "Menu:", reply_markup=get_owner_main_keyboard())
    
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
        
        bot.edit_message_text(
            "🎯 Qaysi kanallarga yuboramiz?\n\n"
            f"Tanlangan: {len(selected_channels_temp[user_id])} ta kanal",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=get_channels_keyboard(user_id)
        )
    
    bot.answer_callback_query(call.id)


# Post qabul qilish (rasm caption bilan HTML)
@bot.message_handler(func=lambda message: is_owner(message.from_user.id) and 
                     user_states.get(message.from_user.id) == "waiting_for_post",
                     content_types=['text', 'photo', 'video', 'animation', 'sticker', 
                                  'document', 'audio', 'voice', 'video_note'])
def receive_post(message):
    user_id = message.from_user.id
    
    # Caption ni saqlash (rasm/video uchun)
    caption = message.caption if hasattr(message, 'caption') and message.caption else None
    
    post_data = {
        'chat_id': message.chat.id,
        'message_id': message.message_id,
        'content_type': message.content_type,
        'from_chat_id': message.chat.id,
        'buttons': [],
        'text': message.text if message.content_type == 'text' else None,
        'caption': caption  # Rasm caption
    }
    
    if user_id not in user_posts:
        user_posts[user_id] = []
    
    user_posts[user_id].append(post_data)
    
    # Postni ko'rsatish (HTML bilan)
    try:
        if message.content_type == 'text':
            bot.send_message(
                chat_id=message.chat.id,
                text=message.text,
                parse_mode='HTML',
                disable_web_page_preview=True
            )
        elif message.content_type == 'photo' and caption:
            # Rasmni caption bilan qayta yuborish
            bot.send_photo(
                chat_id=message.chat.id,
                photo=message.photo[-1].file_id,
                caption=caption,
                parse_mode='HTML'
            )
        elif message.content_type == 'video' and caption:
            bot.send_video(
                chat_id=message.chat.id,
                video=message.video.file_id,
                caption=caption,
                parse_mode='HTML'
            )
        else:
            bot.copy_message(
                chat_id=message.chat.id,
                from_chat_id=message.chat.id,
                message_id=message.message_id
            )
    except Exception as e:
        # Agar HTML xatolik bo'lsa, oddiy copy
        bot.copy_message(
            chat_id=message.chat.id,
            from_chat_id=message.chat.id,
            message_id=message.message_id
        )
    
    bot.send_message(
        message.chat.id,
        f"✅ Post qabul qilindi! ({len(user_posts[user_id])} ta post)\n"
        "Yana post yuboring yoki <b>/done</b> / \"✅ Tayyor\" tugmasini bosing.",
        parse_mode='HTML'
    )


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
    
    try:
        bot.edit_message_text(
            f"✅ {len(posts)} ta post {len(channels)} ta kanalga yuborildi!\nJami: {total_sent} ta",
            message.chat.id,
            message.message_id
        )
    except:
        pass
    
    bot.send_message(
        user_id,
        "Kerakli amalni tanlang:",
        reply_markup=get_owner_main_keyboard()
    )
    
    # Tozalash
    if user_id in user_posts:
        del user_posts[user_id]


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
    
    try:
        bot.edit_message_text(
            f"✅ {len(posts)} ta post {len(selected_channel_ids)} ta kanalga yuborildi!\nJami: {total_sent} ta",
            message.chat.id,
            message.message_id
        )
    except:
        pass
    
    bot.send_message(
        user_id,
        "Kerakli amalni tanlang:",
        reply_markup=get_owner_main_keyboard()
    )
    
    # Tozalash
    if user_id in user_posts:
        del user_posts[user_id]


def send_single_post_to_channel(post, channel_id):
    try:
        buttons = post.get('buttons', [])
        markup = None
        
        if buttons:
            markup = types.InlineKeyboardMarkup(row_width=8)
            for row in buttons:
                row_btns = []
                for btn in row:
                    row_btns.append(types.InlineKeyboardButton(btn['name'], url=btn['url']))
                markup.add(*row_btns)
        
        # Post turiga qarab yuborish
        if post['content_type'] == 'text':
            bot.send_message(
                chat_id=channel_id,
                text=post.get('text', ''),
                parse_mode='HTML',
                disable_web_page_preview=True,
                reply_markup=markup
            )
        elif post['content_type'] == 'photo':
            caption = post.get('caption', '')
            bot.send_photo(
                chat_id=channel_id,
                photo=post['message_id'],
                caption=caption if caption else None,
                parse_mode='HTML' if caption else None,
                reply_markup=markup
            )
        elif post['content_type'] == 'video':
            caption = post.get('caption', '')
            bot.send_video(
                chat_id=channel_id,
                video=post['message_id'],
                caption=caption if caption else None,
                parse_mode='HTML' if caption else None,
                reply_markup=markup
            )
        else:
            # Boshqa turdagi postlarni copy qilish
            bot.copy_message(
                chat_id=channel_id,
                from_chat_id=post['from_chat_id'],
                message_id=post['message_id'],
                reply_markup=markup
            )
            
            # Agar tugmalar bo'lsa va copy message ishlamasa, alohida yuborish
            if markup:
                bot.send_message(
                    chat_id=channel_id,
                    text="🔗",
                    reply_markup=markup
                )
    except Exception as e:
        print(f"Post yuborishda xatolik: {e}")
        # Xatolik bo'lsa, oddiy copy
        bot.copy_message(
            chat_id=channel_id,
            from_chat_id=post['from_chat_id'],
            message_id=post['message_id']
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