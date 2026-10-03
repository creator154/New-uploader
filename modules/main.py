import os
import telebot
from googletrans import Translator
from PyPDF2 import PdfReader

# Heroku Environment Variable से टोकन उठाएगा (सुरक्षित तरीका)
BOT_TOKEN = os.environ.get('BOT_TOKEN')
bot = telebot.TeleBot(BOT_TOKEN)
translator = Translator()

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(message, "👋 नमस्ते! मैं इंग्लिश टू हिंदी PDF ट्रांसलेटर बॉट हूँ। मुझे कोई भी English PDF फाइल भेजें, मैं उसका हिंदी अनुवाद करके आपको टेक्स्ट में भेज दूँगा।")

@bot.message_handler(content_types=['document'])
def handle_docs(message):
    if message.document.mime_type == 'application/pdf':
        chat_id = message.chat.id
        bot.reply_to(message, "⏳ आपकी PDF मिल गई है। अनुवाद शुरू हो रहा है, कृपया थोड़ा इंतज़ार करें...")

        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        input_pdf_path = f"input_{chat_id}.pdf"

        with open(input_pdf_path, 'wb') as new_file:
            new_file.write(downloaded_file)

        try:
            reader = PdfReader(input_pdf_path)
            extracted_text = ""
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    extracted_text += text + "\n"

            if not extracted_text.strip():
                bot.reply_to(message, "❌ इस PDF में कोई टेक्स्ट नहीं मिला (शायद यह स्कैन की हुई इमेज है)।")
                return

            # 3000 कैरेक्टर के टुकड़ों में अनुवाद ताकि API ब्लॉक न हो
            chunks = [extracted_text[i:i+3000] for i in range(0, len(extracted_text), 3000)]
            
            bot.send_message(chat_id, "📖 अनुवादित हिंदी टेक्स्ट नीचे है:")
            for chunk in chunks:
                translation = translator.translate(chunk, src='en', dest='hi')
                bot.send_message(chat_id, translation.text)

        except Exception as e:
            bot.reply_to(message, f"❌ अनुवाद में कोई त्रुटि आई।")
            print(f"Error: {e}")
        finally:
            if os.path.exists(input_pdf_path):
                os.remove(input_pdf_path)
    else:
        bot.reply_to(message, "❌ कृपया केवल PDF फ़ाइल ही भेजें।")

if __name__ == "__main__":
    print("Bot is running on Heroku...")
    bot.infinity_polling()
