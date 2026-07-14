import os
import telebot
from telebot import types
from flask import Flask, request
import json
from dotenv import load_dotenv
import time
import tempfile
import re

load_dotenv()

TOKEN = os.getenv('BOT_TOKEN')
OWNER_ID = int(os.getenv('OWNER_ID'))
WEBHOOK_URL = os.getenv('WEBHOOK_URL')

bot = telebot.TeleBot(TOKEN, parse_mode='HTML')
app = Flask(__name__)

# Vaqtinchalik xotira
user_states = {}
current_posts = {}
channels = []

# Oddiy klaviatura tugmalari
def get_owner_main_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    btn_create = types.KeyboardButton("📝 Post yaratish")
    btn_add_channel = types.KeyboardButton("➕ Kanal qo'shish")
    btn_channels = types.KeyboardButton("📋 Kanallar ro'yxati")
    btn_delete_channel = types.KeyboardButton("🗑 Kanal o'chirish")
    btn_export = types.KeyboardButton("📤 Kanallarni export")
    btn_import = types.KeyboardButton("📥 Kanallarni import")
    markup.add(btn_create, btn_add_channel)
    markup.add(btn_channels, btn_delete_channel)
    markup.add(btn_export, btn_import)
    return markup

def get_post_management_keyboard(post_id):
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_add_button = types.InlineKeyboardButton("➕ Tugma qo'shish", callback_data=f"add_btn_{post_id}")
    btn_show_buttons = types.InlineKeyboardButton("👁 Tugmalarni ko'rish", callback_data=f"show_btn_{post_id}")
    btn_send = types.InlineKeyboardButton("📤 Yuborish", callback_data=f"send_{post_id}")
    btn_cancel = types.InlineKeyboardButton("❌ Bekor qilish", callback_data=f"cancel_{post_id}")
    markup.add(btn_add_button, btn_show_buttons)
    markup.add(btn_send, btn_cancel)
    return markup

def get_back_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    btn_back = types.KeyboardButton("⬅️ Bosh menyu")
    markup.add(btn_back)
    return markup

# Owner tekshirish
def is_owner(user_id):
    return user_id == OWNER_ID

def fix_url(url):
    """URL ni to'g'irlash - https:// qo'shish"""
    url = url.strip()
    if not url.startswith('http://') and not url.startswith('https://'):
        url = 'https://' + url
    return url

def parse_button_text(text):
    """Tugma matnini parse qilish"""
    buttons = []
    lines = text.strip().split('\n')
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        row_buttons = []
        parts = line.split('|')
        
        for part in parts:
            part = part.strip()
            match = re.match(r'(.+?)\s*-\s*(\S+)\s*(?:-\s*style:(\w+))?', part)
            if match:
                name = match.group(1).strip()
                url = match.group(2).strip()
                color = match.group(3) or 'default'
                url = fix_url(url)
                
                row_buttons.append({
                    'name': name,
                    'url': url,
                    'color': color
                })
        
        if row_buttons:
            buttons.append(row_buttons)
    
    return buttons

def create_inline_keyboard(buttons):
    """Parsed tugmalardan inline keyboard yaratish"""
    if not buttons:
        return None
    
    markup = types.InlineKeyboardMarkup(row_width=8)
    for row in buttons:
        row_buttons = []
        for btn in row:
            row_buttons.append(types.InlineKeyboardButton(
                text=btn['name'],
                url=btn['url']
            ))
        markup.row(*row_buttons)
    
    return markup

# Barcha xabarlarni qabul qilish uchun asosiy handler
@bot.message_handler(commands=['start'])
def start_command(message):
    if is_owner(message.from_user.id):
        if message.from_user.id in user_states:
            del user_states[message.from_user.id]
        
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

# Fayl qabul qilish - Kanallarni import
@bot.message_handler(content_types=['document'],
                     func=lambda message: is_owner(message.from_user.id) and 
                     user_states.get(message.from_user.id) == "waiting_for_import")
def import_channels_file(message):
    global channels
    user_id = message.from_user.id
    
    try:
        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        imported_channels = json.loads(downloaded_file.decode('utf-8'))
        
        if not isinstance(imported_channels, list):
            raise ValueError("Noto'g'ri format")
        
        added_count = 0
        skipped_count = 0
        
        for channel in imported_channels:
            if 'id' in channel and 'name' in channel:
                channel_id = str(channel['id'])
                if not any(ch['id'] == channel_id for ch in channels):
                    channels.append({'id': channel_id, 'name': channel['name']})
                    added_count += 1
                else:
                    skipped_count += 1
        
        del user_states[user_id]
        
        bot.send_message(
            message.chat.id,
            f"✅ Kanallar import qilindi!\n\n"
            f"📥 Qo'shilgan: {added_count}\n"
            f"⏭ O'tkazib yuborilgan: {skipped_count}\n"
            f"📊 Jami kanallar: {len(channels)}",
            reply_markup=get_owner_main_keyboard()
        )
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Xatolik: {str(e)}", 
                        reply_markup=get_owner_main_keyboard())

# Text xabarlarni qayta ishlash
@bot.message_handler(content_types=['text'], func=lambda message: is_owner(message.from_user.id))
def handle_text_messages(message):
    global channels
    user_id = message.from_user.id
    
    # Bosh menyu
    if message.text == "⬅️ Bosh menyu":
        if user_id in user_states:
            del user_states[user_id]
        if user_id in current_posts:
            del current_posts[user_id]
        bot.send_message(message.chat.id, "👋 Bosh menyu", reply_markup=get_owner_main_keyboard())
        return
    
    # Post yaratish
    if message.text == "📝 Post yaratish":
        user_states[user_id] = "waiting_for_post"
        bot.send_message(
            message.chat.id,
            "📝 Post yuboring (matn, rasm, video, gif, sticker, fayl, ovozli xabar):\n\n"
            "Matn HTML formatda bo'lishi mumkin!",
            reply_markup=get_back_keyboard()
        )
        return
    
    # Kanal qo'shish
    if message.text == "➕ Kanal qo'shish":
        user_states[user_id] = "waiting_for_channel"
        bot.send_message(
            message.chat.id,
            "➕ Kanal ID sini kiriting:\n\n"
            "Masalan: @kanal_nomi yoki -1001234567890",
            reply_markup=get_back_keyboard()
        )
        return
    
    # Kanallar ro'yxati
    if message.text == "📋 Kanallar ro'yxati":
        if channels:
            text = "📋 Mening kanallarim:\n\n"
            for i, ch in enumerate(channels, 1):
                text += f"{i}. {ch['name']}\n   ID: <code>{ch['id']}</code>\n\n"
            text += f"📊 Jami: {len(channels)} ta kanal"
        else:
            text = "❌ Hali hech qanday kanal qo'shilmagan."
        bot.send_message(message.chat.id, text, reply_markup=get_owner_main_keyboard())
        return
    
    # Kanal o'chirish
    if message.text == "🗑 Kanal o'chirish":
        if channels:
            user_states[user_id] = "deleting_channel"
            text = "🗑 Qaysi kanalni o'chirmoqchisiz?\n\n"
            for i, ch in enumerate(channels, 1):
                text += f"{i}. {ch['name']} (ID: {ch['id']})\n"
            text += "\nRaqamini kiriting:"
            bot.send_message(message.chat.id, text, reply_markup=get_back_keyboard())
        else:
            bot.send_message(message.chat.id, "❌ O'chirish uchun kanallar yo'q!", 
                           reply_markup=get_owner_main_keyboard())
        return
    
    # Kanallarni export
    if message.text == "📤 Kanallarni export":
        export_channels(message)
        return
    
    # Kanallarni import
    if message.text == "📥 Kanallarni import":
        user_states[user_id] = "waiting_for_import"
        bot.send_message(message.chat.id, "📥 Kanallar JSON faylini yuboring:", 
                        reply_markup=get_back_keyboard())
        return
    
    # Kanal qo'shish ID
    if user_states.get(user_id) == "waiting_for_channel":
        add_channel_handler(message)
        return
    
    # Kanal o'chirish raqami
    if user_states.get(user_id) == "deleting_channel":
        delete_channel_handler(message)
        return
    
    # Tugma qo'shish matni
    if user_states.get(user_id, "").startswith("waiting_for_buttons_"):
        handle_button_input(message)
        return
    
    # Post yaratish - text post
    if user_states.get(user_id) == "waiting_for_post":
        # Tugma formatini tekshirish
        if re.match(r'.+\s*-\s*\S+', message.text):
            bot.send_message(
                message.chat.id,
                "⚠️ Bu tugma formatiga o'xshaydi. Post yaratish uchun kontent yuboring.\n"
                "Tugma qo'shish uchun avval post yarating, keyin '+' tugmasini bosing.",
                reply_markup=get_back_keyboard()
            )
            return
        
        # Oddiy text post
        receive_post(message)

# Media xabarlarni qabul qilish (sticker, rasm, video va h.k.)
@bot.message_handler(content_types=['photo', 'video', 'animation', 'sticker', 
                                  'document', 'audio', 'voice', 'video_note'],
                     func=lambda message: is_owner(message.from_user.id))
def handle_media_messages(message):
    user_id = message.from_user.id
    
    # Agar import qilish holatida bo'lsa va document bo'lsa
    if message.content_type == 'document' and user_states.get(user_id) == "waiting_for_import":
        import_channels_file(message)
        return
    
    # Post yaratish holatida bo'lsa
    if user_states.get(user_id) == "waiting_for_post":
        receive_post(message)
    else:
        # Agar post yaratish holatida bo'lmasa, ogohlantirish
        bot.send_message(
            message.chat.id,
            "⚠️ Avval '📝 Post yaratish' tugmasini bosing!",
            reply_markup=get_owner_main_keyboard()
        )

def export_channels(message):
    global channels
    if channels:
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', 
                                            delete=False, encoding='utf-8') as f:
                json.dump(channels, f, ensure_ascii=False, indent=2)
                temp_file_path = f.name
            
            with open(temp_file_path, 'rb') as f:
                bot.send_document(
                    message.chat.id, f,
                    caption=f"📤 Kanallar ro'yxati ({len(channels)} ta kanal)",
                    reply_markup=get_owner_main_keyboard()
                )
            os.unlink(temp_file_path)
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ Xatolik: {str(e)}", 
                           reply_markup=get_owner_main_keyboard())
    else:
        bot.send_message(message.chat.id, "❌ Export qilish uchun kanallar yo'q!", 
                       reply_markup=get_owner_main_keyboard())

def add_channel_handler(message):
    global channels
    user_id = message.from_user.id
    channel_input = message.text.strip()
    
    try:
        chat = bot.get_chat(channel_input)
        channel_id = str(chat.id)
        channel_name = chat.title or channel_input
        
        try:
            bot_member = bot.get_chat_member(chat.id, bot.get_me().id)
            if bot_member.status in ['administrator', 'creator']:
                if not any(ch['id'] == channel_id for ch in channels):
                    channels.append({'id': channel_id, 'name': channel_name})
                    bot.send_message(
                        message.chat.id,
                        f"✅ Kanal qo'shildi!\n\n"
                        f"📝 Nomi: {channel_name}\n"
                        f"🆔 ID: <code>{channel_id}</code>\n"
                        f"📊 Jami kanallar: {len(channels)}",
                        reply_markup=get_owner_main_keyboard()
                    )
                else:
                    bot.send_message(message.chat.id, "⚠️ Bu kanal allaqachon qo'shilgan!",
                                   reply_markup=get_owner_main_keyboard())
            else:
                bot.send_message(message.chat.id, "❌ Bot bu kanalda admin emas!",
                               reply_markup=get_owner_main_keyboard())
        except:
            bot.send_message(message.chat.id, "❌ Bot kanalga qo'shilmagan!",
                           reply_markup=get_owner_main_keyboard())
        
        if user_id in user_states:
            del user_states[user_id]
    except:
        bot.send_message(message.chat.id, "❌ Kanal topilmadi!", reply_markup=get_owner_main_keyboard())

def delete_channel_handler(message):
    global channels
    user_id = message.from_user.id
    
    try:
        index = int(message.text) - 1
        if 0 <= index < len(channels):
            deleted_channel = channels.pop(index)
            del user_states[user_id]
            bot.send_message(
                message.chat.id,
                f"✅ '{deleted_channel['name']}' kanali o'chirildi!\n"
                f"📊 Qolgan kanallar: {len(channels)}",
                reply_markup=get_owner_main_keyboard()
            )
        else:
            bot.send_message(message.chat.id, "❌ Noto'g'ri raqam!", reply_markup=get_back_keyboard())
    except ValueError:
        bot.send_message(message.chat.id, "❌ Iltimos, raqam kiriting!", reply_markup=get_back_keyboard())

def handle_button_input(message):
    user_id = message.from_user.id
    post_id = user_states[user_id].replace("waiting_for_buttons_", "")
    
    try:
        parsed_buttons = parse_button_text(message.text)
        
        if not parsed_buttons:
            bot.send_message(
                message.chat.id,
                "❌ Noto'g'ri format! Qaytadan urinib ko'ring:\n\n"
                "<b>Format:</b>\n"
                "<code>Tugma 1 - example.com</code>\n"
                "<code>Tugma 2 - example.com - style:green</code>\n\n"
                "<b>Bir qatorga:</b>\n"
                "<code>Tugma 1 - site.com | Tugma 2 - site2.com</code>",
                parse_mode='HTML',
                reply_markup=get_back_keyboard()
            )
            return
        
        if user_id not in current_posts:
            current_posts[user_id] = {}
        if post_id not in current_posts[user_id]:
            current_posts[user_id][post_id] = {'post_data': {}, 'buttons': []}
        
        current_posts[user_id][post_id]['buttons'] = parsed_buttons
        del user_states[user_id]
        
        buttons_text = "✅ Tugmalar qo'shildi!\n\n📋 Tugmalar:\n"
        for row in parsed_buttons:
            for btn in row:
                color_emoji = {"green": "🟢", "blue": "🔵", "red": "🔴"}.get(btn['color'], "⚪")
                buttons_text += f"{color_emoji} {btn['name']} → {btn['url']}\n"
        
        bot.send_message(
            message.chat.id,
            buttons_text,
            reply_markup=get_post_management_keyboard(post_id)
        )
    except Exception as e:
        bot.send_message(
            message.chat.id,
            f"❌ Xatolik: {str(e)}",
            reply_markup=get_back_keyboard()
        )

def receive_post(message):
    """Postni qabul qilish va qayta yuborish"""
    user_id = message.from_user.id
    post_id = str(int(time.time()))
    
    print(f"[DEBUG] Post qabul qilindi: user={user_id}, type={message.content_type}, post_id={post_id}")
    
    # Post ma'lumotlarini saqlash
    post_data = {
        'chat_id': message.chat.id,
        'message_id': message.message_id,
        'content_type': message.content_type,
        'from_chat_id': message.chat.id,
        'text': message.text if message.content_type == 'text' else message.caption,
        'caption': message.caption,
    }
    
    # Media fayl ID sini saqlash
    if message.content_type == 'photo':
        post_data['file_id'] = message.photo[-1].file_id
    elif message.content_type == 'video':
        post_data['file_id'] = message.video.file_id
    elif message.content_type == 'animation':
        post_data['file_id'] = message.animation.file_id
    elif message.content_type == 'sticker':
        post_data['file_id'] = message.sticker.file_id
        print(f"[DEBUG] Sticker qabul qilindi: file_id={message.sticker.file_id}")
    elif message.content_type == 'document':
        post_data['file_id'] = message.document.file_id
    elif message.content_type == 'audio':
        post_data['file_id'] = message.audio.file_id
    elif message.content_type == 'voice':
        post_data['file_id'] = message.voice.file_id
    elif message.content_type == 'video_note':
        post_data['file_id'] = message.video_note.file_id
    
    if user_id not in current_posts:
        current_posts[user_id] = {}
    
    current_posts[user_id][post_id] = {
        'post_data': post_data,
        'buttons': []
    }
    
    user_states[user_id] = f"post_ready_{post_id}"
    
    # Postni qayta yuborish
    try:
        sent_message = None
        
        if message.content_type == 'text':
            sent_message = bot.send_message(
                message.chat.id,
                message.text,
                parse_mode='HTML',
                reply_markup=get_post_management_keyboard(post_id)
            )
        elif message.content_type == 'photo':
            sent_message = bot.send_photo(
                message.chat.id,
                post_data['file_id'],
                caption=message.caption or "",
                parse_mode='HTML' if message.caption else None,
                reply_markup=get_post_management_keyboard(post_id)
            )
        elif message.content_type == 'video':
            sent_message = bot.send_video(
                message.chat.id,
                post_data['file_id'],
                caption=message.caption or "",
                parse_mode='HTML' if message.caption else None,
                reply_markup=get_post_management_keyboard(post_id)
            )
        elif message.content_type == 'animation':
            sent_message = bot.send_animation(
                message.chat.id,
                post_data['file_id'],
                caption=message.caption or "",
                parse_mode='HTML' if message.caption else None,
                reply_markup=get_post_management_keyboard(post_id)
            )
        elif message.content_type == 'sticker':
            sent_message = bot.send_sticker(
                message.chat.id,
                post_data['file_id'],
                reply_markup=get_post_management_keyboard(post_id)
            )
            print(f"[DEBUG] Sticker qayta yuborildi: message_id={sent_message.message_id}")
        elif message.content_type == 'document':
            sent_message = bot.send_document(
                message.chat.id,
                post_data['file_id'],
                caption=message.caption or "",
                parse_mode='HTML' if message.caption else None,
                reply_markup=get_post_management_keyboard(post_id)
            )
        elif message.content_type == 'audio':
            sent_message = bot.send_audio(
                message.chat.id,
                post_data['file_id'],
                caption=message.caption or "",
                parse_mode='HTML' if message.caption else None,
                reply_markup=get_post_management_keyboard(post_id)
            )
        elif message.content_type == 'voice':
            sent_message = bot.send_voice(
                message.chat.id,
                post_data['file_id'],
                caption=message.caption or "",
                parse_mode='HTML' if message.caption else None,
                reply_markup=get_post_management_keyboard(post_id)
            )
        elif message.content_type == 'video_note':
            sent_message = bot.send_video_note(
                message.chat.id,
                post_data['file_id'],
                reply_markup=get_post_management_keyboard(post_id)
            )
        
        if sent_message:
            current_posts[user_id][post_id]['copy_message_id'] = sent_message.message_id
            current_posts[user_id][post_id]['copy_chat_id'] = sent_message.chat.id
            print(f"[DEBUG] Post muvaffaqiyatli qayta yuborildi: {post_id}")
        
    except Exception as e:
        print(f"[ERROR] Post qayta yuborishda xatolik: {str(e)}")
        bot.send_message(
            message.chat.id,
            f"❌ Postni qayta yuborishda xatolik: {str(e)}",
            reply_markup=get_owner_main_keyboard()
        )
        if user_id in current_posts and post_id in current_posts[user_id]:
            del current_posts[user_id][post_id]
        if user_id in user_states:
            del user_states[user_id]

# Callback handler
@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    if not is_owner(call.from_user.id):
        bot.answer_callback_query(call.id, "Siz bot egasi emassiz!")
        return
    
    user_id = call.from_user.id
    
    if call.data.startswith("add_btn_"):
        post_id = call.data.replace("add_btn_", "")
        user_states[user_id] = f"waiting_for_buttons_{post_id}"
        
        bot.send_message(
            call.message.chat.id,
            "📝 Tugmalarni quyidagi formatda yuboring:\n\n"
            "<b>Format:</b>\n"
            "<code>Tugma 1 - example.com</code>\n"
            "<code>Tugma 2 - example.com - style:green</code>\n\n"
            "<b>Bir qatorga:</b>\n"
            "<code>Tugma 1 - site.com | Tugma 2 - site2.com</code>",
            parse_mode='HTML'
        )
        bot.answer_callback_query(call.id)
    
    elif call.data.startswith("show_btn_"):
        post_id = call.data.replace("show_btn_", "")
        
        if user_id in current_posts and post_id in current_posts[user_id] and \
           current_posts[user_id][post_id]['buttons']:
            buttons = current_posts[user_id][post_id]['buttons']
            text = "📋 Post tugmalari:\n\n"
            for row in buttons:
                for btn in row:
                    color_emoji = {"green": "🟢", "blue": "🔵", "red": "🔴"}.get(btn['color'], "⚪")
                    text += f"{color_emoji} {btn['name']} → {btn['url']}\n"
        else:
            text = "❌ Hali hech qanday tugma qo'shilmagan."
        
        bot.answer_callback_query(call.id, text[:200], show_alert=True)
    
    elif call.data.startswith("send_"):
        post_id = call.data.replace("send_", "")
        
        if user_id not in current_posts or post_id not in current_posts[user_id]:
            bot.answer_callback_query(call.id, "❌ Post topilmadi!")
            return
        
        if not channels:
            bot.answer_callback_query(call.id, "❌ Avval kanal qo'shing!")
            return
        
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("🎯 Tanlash", callback_data=f"select_{post_id}"),
            types.InlineKeyboardButton("📢 Barchaga", callback_data=f"sendall_{post_id}")
        )
        markup.add(
            types.InlineKeyboardButton("⬅️ Bekor qilish", callback_data=f"cancelsend_{post_id}")
        )
        
        try:
            bot.edit_message_reply_markup(
                call.message.chat.id,
                call.message.message_id,
                reply_markup=markup
            )
        except:
            pass
    
    elif call.data.startswith("select_"):
        post_id = call.data.replace("select_", "")
        
        if not channels:
            bot.answer_callback_query(call.id, "❌ Avval kanal qo'shing!")
            return
        
        if user_id not in current_posts:
            current_posts[user_id] = {}
        if post_id not in current_posts[user_id]:
            current_posts[user_id][post_id] = {'post_data': {}, 'buttons': [], 'selected_channels': []}
        if 'selected_channels' not in current_posts[user_id][post_id]:
            current_posts[user_id][post_id]['selected_channels'] = []
        
        selected = current_posts[user_id][post_id]['selected_channels']
        
        markup = types.InlineKeyboardMarkup(row_width=1)
        for channel in channels:
            check = "✅ " if channel['id'] in selected else "⬜ "
            markup.add(types.InlineKeyboardButton(
                f"{check}{channel['name']}", 
                callback_data=f"toggle_{post_id}_{channel['id']}"
            ))
        
        markup.add(
            types.InlineKeyboardButton("✅ Tayyor - Yuborish", callback_data=f"confirm_{post_id}"),
            types.InlineKeyboardButton("⬅️ Bekor qilish", callback_data=f"cancelsend_{post_id}")
        )
        
        bot.edit_message_text(
            "🎯 Qaysi kanallarga yuboramiz?",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup
        )
    
    elif call.data.startswith("sendall_"):
        post_id = call.data.replace("sendall_", "")
        if not channels:
            bot.answer_callback_query(call.id, "❌ Avval kanal qo'shing!")
            return
        send_to_channels(call.message, user_id, post_id, 'all')
    
    elif call.data.startswith("confirm_"):
        post_id = call.data.replace("confirm_", "")
        if user_id in current_posts and post_id in current_posts[user_id] and \
           current_posts[user_id][post_id].get('selected_channels'):
            send_to_channels(call.message, user_id, post_id, 'selected')
        else:
            bot.answer_callback_query(call.id, "❌ Kamida bitta kanal tanlang!")
    
    elif call.data.startswith("cancel_"):
        post_id = call.data.replace("cancel_", "")
        if user_id in current_posts and post_id in current_posts[user_id]:
            del current_posts[user_id][post_id]
        
        try:
            bot.edit_message_text("❌ Post o'chirildi.", call.message.chat.id, call.message.message_id)
        except:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        
        bot.send_message(call.message.chat.id, "👋 Bosh menyu", reply_markup=get_owner_main_keyboard())
    
    elif call.data.startswith("cancelsend_"):
        post_id = call.data.replace("cancelsend_", "")
        try:
            bot.edit_message_reply_markup(
                call.message.chat.id,
                call.message.message_id,
                reply_markup=get_post_management_keyboard(post_id)
            )
        except:
            pass
    
    elif call.data.startswith("toggle_"):
        parts = call.data.split("_", 2)
        post_id = parts[1]
        channel_id = parts[2] if len(parts) > 2 else ""
        
        if user_id not in current_posts:
            current_posts[user_id] = {}
        if post_id not in current_posts[user_id]:
            current_posts[user_id][post_id] = {'post_data': {}, 'buttons': [], 'selected_channels': []}
        if 'selected_channels' not in current_posts[user_id][post_id]:
            current_posts[user_id][post_id]['selected_channels'] = []
        
        selected = current_posts[user_id][post_id]['selected_channels']
        
        if channel_id in selected:
            selected.remove(channel_id)
        else:
            selected.append(channel_id)
        
        markup = types.InlineKeyboardMarkup(row_width=1)
        for channel in channels:
            check = "✅ " if channel['id'] in selected else "⬜ "
            markup.add(types.InlineKeyboardButton(
                f"{check}{channel['name']}", 
                callback_data=f"toggle_{post_id}_{channel['id']}"
            ))
        
        markup.add(
            types.InlineKeyboardButton("✅ Tayyor - Yuborish", callback_data=f"confirm_{post_id}"),
            types.InlineKeyboardButton("⬅️ Bekor qilish", callback_data=f"cancelsend_{post_id}")
        )
        
        try:
            bot.edit_message_text(
                "🎯 Qaysi kanallarga yuboramiz?",
                call.message.chat.id,
                call.message.message_id,
                reply_markup=markup
            )
        except:
            pass

def send_to_channels(message, user_id, post_id, send_type):
    if user_id not in current_posts or post_id not in current_posts[user_id]:
        bot.send_message(message.chat.id, "❌ Post topilmadi!")
        return
    
    post_data = current_posts[user_id][post_id]['post_data']
    buttons = current_posts[user_id][post_id].get('buttons', [])
    inline_markup = create_inline_keyboard(buttons)
    
    if send_type == 'all':
        target_channels = channels
    else:
        selected_ids = current_posts[user_id][post_id].get('selected_channels', [])
        target_channels = [ch for ch in channels if ch['id'] in selected_ids]
    
    sent_count = 0
    failed_channels = []
    
    for channel in target_channels:
        try:
            content_type = post_data['content_type']
            channel_id = int(channel['id'])
            
            if content_type == 'text':
                bot.send_message(chat_id=channel_id, text=post_data['text'], 
                               parse_mode='HTML', reply_markup=inline_markup)
            elif content_type == 'photo':
                bot.send_photo(chat_id=channel_id, photo=post_data['file_id'],
                             caption=post_data.get('caption') or "",
                             parse_mode='HTML' if post_data.get('caption') else None,
                             reply_markup=inline_markup)
            elif content_type == 'video':
                bot.send_video(chat_id=channel_id, video=post_data['file_id'],
                             caption=post_data.get('caption') or "",
                             parse_mode='HTML' if post_data.get('caption') else None,
                             reply_markup=inline_markup)
            elif content_type == 'animation':
                bot.send_animation(chat_id=channel_id, animation=post_data['file_id'],
                                 caption=post_data.get('caption') or "",
                                 parse_mode='HTML' if post_data.get('caption') else None,
                                 reply_markup=inline_markup)
            elif content_type == 'sticker':
                bot.send_sticker(chat_id=channel_id, sticker=post_data['file_id'],
                               reply_markup=inline_markup)
            elif content_type == 'document':
                bot.send_document(chat_id=channel_id, document=post_data['file_id'],
                                caption=post_data.get('caption') or "",
                                parse_mode='HTML' if post_data.get('caption') else None,
                                reply_markup=inline_markup)
            elif content_type == 'audio':
                bot.send_audio(chat_id=channel_id, audio=post_data['file_id'],
                             caption=post_data.get('caption') or "",
                             parse_mode='HTML' if post_data.get('caption') else None,
                             reply_markup=inline_markup)
            elif content_type == 'voice':
                bot.send_voice(chat_id=channel_id, voice=post_data['file_id'],
                             caption=post_data.get('caption') or "",
                             parse_mode='HTML' if post_data.get('caption') else None,
                             reply_markup=inline_markup)
            elif content_type == 'video_note':
                bot.send_video_note(chat_id=channel_id, video_note=post_data['file_id'],
                                  reply_markup=inline_markup)
            
            sent_count += 1
            time.sleep(0.5)
        except Exception as e:
            failed_channels.append(f"{channel['name']}: {str(e)[:100]}")
    
    result_text = f"✅ {sent_count}/{len(target_channels)} kanalga yuborildi!"
    if failed_channels:
        result_text += "\n\n❌ Xatoliklar:\n"
        for fail in failed_channels[:5]:
            result_text += f"• {fail}\n"
    
    try:
        bot.edit_message_text(result_text, message.chat.id, message.message_id)
    except:
        bot.send_message(message.chat.id, result_text)
    
    bot.send_message(message.chat.id, "👋 Asosiy menyu", reply_markup=get_owner_main_keyboard())
    
    if user_id in current_posts and post_id in current_posts[user_id]:
        del current_posts[user_id][post_id]

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
