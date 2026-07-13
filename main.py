import os
from flask import Flask, request
import telebot
from dotenv import load_dotenv
import time

load_dotenv()

TOKEN = os.getenv('BOT_TOKEN')
WEBHOOK_URL = os.getenv('WEBHOOK_URL')

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# Hamma uchun ochiq test bot
@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, f"✅ Bot ishlamoqda!\nSizning ID: {message.from_user.id}")

@bot.message_handler(func=lambda message: True)
def echo(message):
    bot.reply_to(message, f"ID: {message.from_user.id}\nXabar: {message.text}")

@app.route('/' + TOKEN, methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return ''
    return 'error', 403

@app.route('/')
def index():
    return 'Bot ishlamoqda!', 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    
    # Webhook o'rnatish
    bot.remove_webhook()
    time.sleep(1)
    bot.set_webhook(url=f"{WEBHOOK_URL}/{TOKEN}")
    print("✅ Bot ishga tushdi!")
    
    app.run(host='0.0.0.0', port=port)
