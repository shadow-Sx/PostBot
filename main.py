import os
import telebot
from telebot import types
from flask import Flask, request
import json
from dotenv import load_dotenv
import time
import tempfile

load_dotenv()

TOKEN = os.getenv('BOT_TOKEN')
OWNER_ID = int(os.getenv('OWNER_ID'))
WEBHOOK_URL = os.getenv('WEBHOOK_URL')

bot = telebot.TeleBot(TOKEN, parse_mode='HTML')
app = Flask(__name__)

# Vaqtinchalik xotira
user_states = {}
current_posts = {}
channels = []  # Asosiy kanallar ro'yxati

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

def get_post_management_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    btn_add_button = types.KeyboardButton("🔗 Tugma qo'shish")
    btn_show_buttons = types.KeyboardButton("📋 Tugmalarni ko'rish")
    btn_delete_button = types.KeyboardButton("🗑 Tugma o'chirish")
    btn_clear_buttons = types.KeyboardButton("🔄 Hammasini tozalash")
    btn_send = types.KeyboardButton("📤 Post yuborish")
    btn_cancel = types.KeyboardButton("❌ Bekor qilish")
    btn_back = types.KeyboardButton("⬅️ Bosh menyu")
    markup.add(btn_add_button, btn_show_buttons)
    markup.add(btn_delete_button, btn_clear_buttons)
    markup.add(btn_send, btn_cancel)
    markup.add(btn_back)
    return markup

def get_back_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    btn_back = types.KeyboardButton("⬅️ Bosh menyu")
    markup.add(btn_back)
    return markup

# Owner tekshirish
def is_owner(user_id):
    return user_id == OWNER_ID

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

# Fayl qabul qilish - Kanallarni import qilish
@bot.message_handler(content_types=['document'],
                     func=lambda message: is_owner(message.from_user.id) and 
                     user_states.get(message.from_user.id) == "waiting_for_import")
def import_channels_file(message):
    global channels
    user_id = message.from_user.id
    
    try:
        # Fayl ma'lumotlarini olish
        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        # JSON ni o'qish
        imported_channels = json.loads(downloaded_file.decode('utf-8'))
        
        if not isinstance(imported_channels, list):
            raise ValueError("Noto'g'ri format")
        
        # Kanallarni qo'shish
        added_count = 0
        skipped_count = 0
        
        for channel in imported_channels:
            if 'id' in channel and 'name' in channel:
                # Takroriy kanallarni tekshirish
                if not any(ch['id'] == channel['id'] for ch in channels):
                    channels.append(channel)
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
        bot.send_message(
            message.chat.id,
            f"❌ Xatolik: Noto'g'ri format yoki fayl buzilgan.\n"
            f"Avval kanallarni export qiling va o'sha faylni yuklang.",
            reply_markup=get_owner_main_keyboard()
        )

# Matnli xabarlarni qayta ishlash
@bot.message_handler(func=lambda message: is_owner(message.from_user.id))
def handle_messages(message):
    global channels
    user_id = message.from_user.id
    
    # Bosh menyu
    if message.text == "⬅️ Bosh menyu":
        if user_id in user_states:
            del user_states[user_id]
        if user_id in current_posts:
            del current_posts[user_id]
        bot.send_message(
            message.chat.id,
            "👋 Bosh menyu",
            reply_markup=get_owner_main_keyboard()
        )
        return
    
    # Post yaratish
    if message.text == "📝 Post yaratish":
        user_states[user_id] = "waiting_for_post"
        current_posts[user_id] = {
            'post_data': {},
            'buttons': []
        }
        bot.send_message(
            message.chat.id,
            "📝 Post yuboring (matn, rasm, video, gif, sticker, fayl, ovozli xabar):",
            reply_markup=get_back_keyboard()
        )
        return
    
    # Kanal qo'shish
    if message.text == "➕ Kanal qo'shish":
        user_states[user_id] = "waiting_for_channel"
        bot.send_message(
            message.chat.id,
            "➕ Kanal ID sini kiriting:\n\n"
            "Masalan: @kanal_nomi yoki -1001234567890\n\n"
            "Bot kanalda admin bo'lishi kerak!",
            reply_markup=get_back_keyboard()
        )
        return
    
    # Kanallar ro'yxati
    if message.text == "📋 Kanallar ro'yxati":
        if channels:
            text = "📋 Mening kanallarim:\n\n"
            for i, ch in enumerate(channels, 1):
                text += f"{i}. {ch['name']} (ID: {ch['id']})\n"
            text += f"\n📊 Jami: {len(channels)} ta kanal"
        else:
            text = "❌ Hali hech qanday kanal qo'shilmagan."
        
        bot.send_message(
            message.chat.id,
            text,
            reply_markup=get_owner_main_keyboard()
        )
        return
    
    # Kanal o'chirish
    if message.text == "🗑 Kanal o'chirish":
        if channels:
            user_states[user_id] = "deleting_channel"
            text = "🗑 Qaysi kanalni o'chirmoqchisiz?\n\n"
            for i, ch in enumerate(channels, 1):
                text += f"{i}. {ch['name']} (ID: {ch['id']})\n"
            text += "\nRaqamini kiriting:"
            
            bot.send_message(
                message.chat.id,
                text,
                reply_markup=get_back_keyboard()
            )
        else:
            bot.send_message(
                message.chat.id,
                "❌ O'chirish uchun kanallar yo'q!",
                reply_markup=get_owner_main_keyboard()
            )
        return
    
    # Kanallarni export qilish
    if message.text == "📤 Kanallarni export":
        if channels:
            try:
                # JSON fayl yaratish
                with tempfile.NamedTemporaryFile(mode='w', suffix='.json', 
                                                delete=False, encoding='utf-8') as f:
                    json.dump(channels, f, ensure_ascii=False, indent=2)
                    temp_file_path = f.name
                
                # Faylni yuborish
                with open(temp_file_path, 'rb') as f:
                    bot.send_document(
                        message.chat.id,
                        f,
                        caption=f"📤 Kanallar ro'yxati ({len(channels)} ta kanal)\n\n"
                                f"Bu faylni saqlab qo'ying. Qayta import qilish uchun '📥 Kanallarni import' "
                                f"tugmasini bosing va shu faylni yuboring.",
                        reply_markup=get_owner_main_keyboard()
                    )
                
                # Vaqtinchalik faylni o'chirish
                os.unlink(temp_file_path)
                
            except Exception as e:
                bot.send_message(
                    message.chat.id,
                    f"❌ Export qilishda xatolik: {str(e)}",
                    reply_markup=get_owner_main_keyboard()
                )
        else:
            bot.send_message(
                message.chat.id,
                "❌ Export qilish uchun kanallar yo'q!",
                reply_markup=get_owner_main_keyboard()
            )
        return
    
    # Kanallarni import qilish
    if message.text == "📥 Kanallarni import":
        user_states[user_id] = "waiting_for_import"
        bot.send_message(
            message.chat.id,
            "📥 Kanallar JSON faylini yuboring:\n\n"
            "Oldin export qilingan faylni yuboring.",
            reply_markup=get_back_keyboard()
        )
        return
    
    # Tugma qo'shish
    if message.text == "🔗 Tugma qo'shish":
        user_states[user_id] = "waiting_for_button_name"
        bot.send_message(
            message.chat.id,
            "🔗 Tugma nomini kiriting:",
            reply_markup=get_back_keyboard()
        )
        return
    
    # Tugmalarni ko'rish
    if message.text == "📋 Tugmalarni ko'rish":
        if user_id in current_posts and current_posts[user_id]['buttons']:
            buttons = current_posts[user_id]['buttons']
            text = "📋 Post tugmalari:\n\n"
            for i, btn in enumerate(buttons, 1):
                text += f"{i}. {btn['name']} → {btn['url']}\n"
        else:
            text = "❌ Hali hech qanday tugma qo'shilmagan."
        
        bot.send_message(
            message.chat.id,
            text,
            reply_markup=get_post_management_keyboard()
        )
        return
    
    # Tugma o'chirish
    if message.text == "🗑 Tugma o'chirish":
        if user_id in current_posts and current_posts[user_id]['buttons']:
            user_states[user_id] = "deleting_button"
            buttons = current_posts[user_id]['buttons']
            text = "🗑 Qaysi tugmani o'chirmoqchisiz?\n\n"
            for i, btn in enumerate(buttons, 1):
                text += f"{i}. {btn['name']}\n"
            text += "\nRaqamini kiriting:"
            
            bot.send_message(
                message.chat.id,
                text,
                reply_markup=get_back_keyboard()
            )
        else:
            bot.send_message(
                message.chat.id,
                "❌ O'chirish uchun tugmalar yo'q!",
                reply_markup=get_post_management_keyboard()
            )
        return
    
    # Barcha tugmalarni tozalash
    if message.text == "🔄 Hammasini tozalash":
        if user_id in current_posts:
            current_posts[user_id]['buttons'] = []
            bot.send_message(
                message.chat.id,
                "✅ Barcha tugmalar tozalandi!",
                reply_markup=get_post_management_keyboard()
            )
        else:
            bot.send_message(
                message.chat.id,
                "❌ Avval post yarating!",
                reply_markup=get_owner_main_keyboard()
            )
        return
    
    # Post yuborish
    if message.text == "📤 Post yuborish":
        if user_id in current_posts and current_posts[user_id]['post_data']:
            user_states[user_id] = "sending_post"
            
            # Inline keyboard yaratish
            markup = types.InlineKeyboardMarkup(row_width=2)
            btn_select = types.InlineKeyboardButton("🎯 Tanlash", callback_data="select_channels")
            btn_all = types.InlineKeyboardButton("📢 Barchaga", callback_data="send_all")
            btn_back = types.InlineKeyboardButton("⬅️ Bekor qilish", callback_data="cancel_send")
            markup.add(btn_select, btn_all)
            markup.add(btn_back)
            
            # Post preview
            post_data = current_posts[user_id]['post_data']
            buttons = current_posts[user_id].get('buttons', [])
            
            preview_text = "📤 Yuborishga tayyormisiz?\n\n"
            preview_text += f"📝 Tugmalar soni: {len(buttons)}\n"
            if buttons:
                preview_text += "\nTugmalar:\n"
                for btn in buttons:
                    preview_text += f"• {btn['name']}\n"
            
            bot.send_message(
                message.chat.id,
                preview_text,
                reply_markup=markup
            )
        else:
            bot.send_message(
                message.chat.id,
                "❌ Avval post yarating!",
                reply_markup=get_owner_main_keyboard()
            )
        return
    
    # Bekor qilish
    if message.text == "❌ Bekor qilish":
        if user_id in user_states:
            del user_states[user_id]
        if user_id in current_posts:
            del current_posts[user_id]
        
        bot.send_message(
            message.chat.id,
            "❌ Post yaratish bekor qilindi.",
            reply_markup=get_owner_main_keyboard()
        )
        return
    
    # Kanal qo'shish - ID qabul qilish
    if user_states.get(user_id) == "waiting_for_channel":
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
                            f"✅ Kanal qo'shildi: {channel_info['name']}\n"
                            f"📊 Jami kanallar: {len(channels)}",
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
                f"❌ Xatolik: Kanal topilmadi yoki noto'g'ri ID.",
                reply_markup=get_owner_main_keyboard()
            )
        return
    
    # Kanal o'chirish - raqam qabul qilish
    if user_states.get(user_id) == "deleting_channel":
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
                bot.send_message(
                    message.chat.id,
                    "❌ Noto'g'ri raqam! Qaytadan urinib ko'ring.",
                    reply_markup=get_back_keyboard()
                )
        except ValueError:
            bot.send_message(
                message.chat.id,
                "❌ Iltimos, raqam kiriting!",
                reply_markup=get_back_keyboard()
            )
        return
    
    # Tugma nomi qabul qilish
    if user_states.get(user_id) == "waiting_for_button_name":
        user_states[user_id] = "waiting_for_button_url"
        user_states[f"{user_id}_btn_name"] = message.text
        bot.send_message(
            message.chat.id,
            "🔗 Tugma URL manzilini kiriting:",
            reply_markup=get_back_keyboard()
        )
        return
    
    # Tugma URL qabul qilish
    if user_states.get(user_id) == "waiting_for_button_url":
        btn_name = user_states.get(f"{user_id}_btn_name", "")
        btn_url = message.text
        
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
        
        buttons_count = len(current_posts[user_id]['buttons'])
        bot.send_message(
            message.chat.id,
            f"✅ Tugma qo'shildi!\n\n"
            f"📝 Nomi: {btn_name}\n"
            f"🔗 URL: {btn_url}\n"
            f"📊 Jami tugmalar: {buttons_count}",
            reply_markup=get_post_management_keyboard()
        )
        return
    
    # Tugma o'chirish - raqam qabul qilish
    if user_states.get(user_id) == "deleting_button":
        try:
            index = int(message.text) - 1
            if user_id in current_posts and 0 <= index < len(current_posts[user_id]['buttons']):
                deleted_btn = current_posts[user_id]['buttons'].pop(index)
                del user_states[user_id]
                
                if current_posts[user_id]['buttons']:
                    bot.send_message(
                        message.chat.id,
                        f"✅ '{deleted_btn['name']}' o'chirildi!\n"
                        f"Qolgan tugmalar: {len(current_posts[user_id]['buttons'])}",
                        reply_markup=get_post_management_keyboard()
                    )
                else:
                    bot.send_message(
                        message.chat.id,
                        "✅ Barcha tugmalar o'chirildi!",
                        reply_markup=get_post_management_keyboard()
                    )
            else:
                bot.send_message(
                    message.chat.id,
                    "❌ Noto'g'ri raqam! Qaytadan urinib ko'ring.",
                    reply_markup=get_back_keyboard()
                )
        except ValueError:
            bot.send_message(
                message.chat.id,
                "❌ Iltimos, raqam kiriting!",
                reply_markup=get_back_keyboard()
            )
        return

# Post kontentini qabul qilish
@bot.message_handler(content_types=['text', 'photo', 'video', 'animation', 'sticker', 
                                  'document', 'audio', 'voice', 'video_note'],
                     func=lambda message: is_owner(message.from_user.id) and 
                     user_states.get(message.from_user.id) == "waiting_for_post")
def receive_post(message):
    user_id = message.from_user.id
    
    # Agar matn bo'lsa va buyruq bo'lmasa
    if message.content_type == 'text' and message.text in [
        "📝 Post yaratish", "➕ Kanal qo'shish", "📋 Kanallar ro'yxati",
        "⬅️ Bosh menyu", "🔗 Tugma qo'shish", "📋 Tugmalarni ko'rish",
        "🗑 Tugma o'chirish", "🔄 Hammasini tozalash", "📤 Post yuborish",
        "❌ Bekor qilish", "🗑 Kanal o'chirish", "📤 Kanallarni export",
        "📥 Kanallarni import"
    ]:
        handle_messages(message)
        return
    
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
        reply_markup=get_post_management_keyboard()
    )

# Callback handler (faqat inline tugmalar uchun)
@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    if not is_owner(call.from_user.id):
        bot.answer_callback_query(call.id, "Siz bot egasi emassiz!")
        return
    
    user_id = call.from_user.id
    
    # Kanallarni tanlash
    if call.data == "select_channels":
        if not channels:
            bot.answer_callback_query(call.id, "❌ Avval kanal qo'shing!")
            return
            
        if user_id not in current_posts:
            current_posts[user_id] = {'post_data': {}, 'buttons': [], 'selected_channels': []}
        if 'selected_channels' not in current_posts[user_id]:
            current_posts[user_id]['selected_channels'] = []
        
        markup = types.InlineKeyboardMarkup(row_width=1)
        for channel in channels:
            check = "✅ " if channel['id'] in current_posts[user_id]['selected_channels'] else "⬜ "
            btn_text = f"{check}{channel['name']}"
            btn = types.InlineKeyboardButton(btn_text, callback_data=f"toggle_{channel['id']}")
            markup.add(btn)
        
        btn_done = types.InlineKeyboardButton("✅ Tayyor - Yuborish", callback_data="confirm_selected")
        btn_back = types.InlineKeyboardButton("⬅️ Bekor qilish", callback_data="cancel_send")
        markup.add(btn_done, btn_back)
        
        bot.edit_message_text(
            "🎯 Qaysi kanallarga yuboramiz?",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup
        )
    
    # Barchaga yuborish
    elif call.data == "send_all":
        if not channels:
            bot.answer_callback_query(call.id, "❌ Avval kanal qo'shing!")
            return
        send_to_channels(call.message, user_id, 'all')
    
    # Tanlanganlarga yuborish
    elif call.data == "confirm_selected":
        if user_id in current_posts and current_posts[user_id].get('selected_channels'):
            send_to_channels(call.message, user_id, 'selected')
        else:
            bot.answer_callback_query(call.id, "❌ Kamida bitta kanal tanlang!")
    
    # Bekor qilish
    elif call.data == "cancel_send":
        bot.edit_message_text(
            "❌ Yuborish bekor qilindi.",
            call.message.chat.id,
            call.message.message_id
        )
        bot.send_message(
            call.message.chat.id,
            "Postingiz saqlandi.",
            reply_markup=get_post_management_keyboard()
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
        
        markup = types.InlineKeyboardMarkup(row_width=1)
        for channel in channels:
            check = "✅ " if channel['id'] in selected else "⬜ "
            btn_text = f"{check}{channel['name']}"
            btn = types.InlineKeyboardButton(btn_text, callback_data=f"toggle_{channel['id']}")
            markup.add(btn)
        
        btn_done = types.InlineKeyboardButton("✅ Tayyor - Yuborish", callback_data="confirm_selected")
        btn_back = types.InlineKeyboardButton("⬅️ Bekor qilish", callback_data="cancel_send")
        markup.add(btn_done, btn_back)
        
        bot.edit_message_text(
            "🎯 Qaysi kanallarga yuboramiz?",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup
        )

# Kanallarga yuborish
def send_to_channels(message, user_id, send_type):
    if user_id not in current_posts or not current_posts[user_id]['post_data']:
        bot.send_message(message.chat.id, "❌ Post topilmadi!")
        return
    
    post_data = current_posts[user_id]['post_data']
    buttons = current_posts[user_id].get('buttons', [])
    
    # Inline keyboard yaratish (faqat post uchun)
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
        message.message_id
    )
    
    # Asosiy menyuga qaytish
    bot.send_message(
        message.chat.id,
        "👋 Asosiy menyu",
        reply_markup=get_owner_main_keyboard()
    )
    
    # Tozalash
    if user_id in current_posts:
        del current_posts[user_id]
    if user_id in user_states:
        del user_states[user_id]

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
