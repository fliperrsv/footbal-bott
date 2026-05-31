import telebot
import requests
from telebot import types

TOKEN = "8762448804:AAH2-aQ91H724KhHEOLvtQKphs1BCKmZM68"
API_URL = "https://football-api-1-1owo.onrender.com"

bot = telebot.TeleBot(TOKEN)
user_bank = {}
last_predict = {}

# Список матчей для кнопок
matches = [
    ("Манчестер Сити", "Ливерпуль"),
    ("Реал Мадрид", "Барселона"),
    ("Бавария", "Боруссия Дортмунд"),
    ("ПСЖ", "Марсель"),
    ("Ювентус", "Интер"),
    ("Арсенал", "Челси"),
    ("Наполи", "Милан"),
    ("Атлетико Мадрид", "Севилья"),
]

def matches_keyboard():
    kb = types.InlineKeyboardMarkup(row_width=1)
    for h, a in matches:
        kb.add(types.InlineKeyboardButton(f"⚽ {h} vs {a}", callback_data=f"match_{h}||{a}"))
    return kb

@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id,
        "🏟 **SmartBet Analyst**\n\n"
        "Выбери матч — получишь вероятности и точный счёт.\n"
        "Затем установи банк и рассчитай оптимальную ставку по Келли.\n\n"
        "Или введи вручную: `/predict Команда1 - Команда2`",
        parse_mode="Markdown")
    bot.send_message(message.chat.id, "📅 Доступные матчи:", reply_markup=matches_keyboard())

@bot.callback_query_handler(func=lambda call: call.data.startswith('match_'))
def match_chosen(call):
    _, home, away = call.data.split('_')
    bot.answer_callback_query(call.id, f"Загружаю прогноз на {home} vs {away}...")
    try:
        r = requests.post(f"{API_URL}/predict", json={"home": home, "away": away}, timeout=10)
        if r.status_code == 200:
            data = r.json()
            last_predict[call.message.chat.id] = data
            p = data['probabilities']
            text = (
                f"🏟 *{home} vs {away}*\n\n"
                f"📊 Прогноз: *{data['prediction']}* (уверенность {data['confidence']}%)\n"
                f"⚽ Ожидаемый счёт: {data['expected_score']}\n\n"
                f"📈 *Вероятности:*\n"
                f"П1: {p['П1']:.1%} → кф {1/p['П1']:.2f}\n"
                f"Х: {p['Х']:.1%} → кф {1/p['Х']:.2f}\n"
                f"П2: {p['П2']:.1%} → кф {1/p['П2']:.2f}\n\n"
                f"💰 Установи банк: `/bank 10000`\n"
                f"🎯 Расчёт Келли: `/kelly П1 2.10`"
            )
            bot.send_message(call.message.chat.id, text, parse_mode="Markdown")
        else:
            bot.send_message(call.message.chat.id, "❌ Ошибка API")
    except:
        bot.send_message(call.message.chat.id, "❌ API недоступно")

@bot.message_handler(commands=['predict'])
def manual_predict(message):
    try:
        _, teams = message.text.split(' ', 1)
        home, away = teams.split(' - ')
        home, away = home.strip(), away.strip()
    except:
        bot.reply_to(message, "Формат: `/predict Манчестер Сити - Ливерпуль`", parse_mode="Markdown")
        return
    try:
        r = requests.post(f"{API_URL}/predict", json={"home": home, "away": away}, timeout=10)
        if r.status_code == 200:
            data = r.json()
            last_predict[message.chat.id] = data
            p = data['probabilities']
            text = (
                f"🏟 *{home} vs {away}*\n"
                f"📊 Прогноз: *{data['prediction']}* ({data['confidence']}%)\n"
                f"📈 П1: {p['П1']:.1%} | Х: {p['Х']:.1%} | П2: {p['П2']:.1%}\n"
                f"💰 `/bank 10000` → `/kelly П1 2.10`"
            )
            bot.reply_to(message, text, parse_mode="Markdown")
        else:
            bot.reply_to(message, "❌ Ошибка API")
    except:
        bot.reply_to(message, "❌ API недоступно")

@bot.message_handler(commands=['bank'])
def set_bank(message):
    try:
        bank = float(message.text.split()[1])
        user_bank[message.chat.id] = bank
        bot.reply_to(message, f"✅ Банк установлен: *{bank:,.0f} руб.*", parse_mode="Markdown")
    except:
        bot.reply_to(message, "Формат: `/bank 10000`", parse_mode="Markdown")

@bot.message_handler(commands=['kelly'])
def kelly_calc(message):
    chat_id = message.chat.id
    if chat_id not in user_bank:
        bot.reply_to(message, "❌ Сначала установи банк: `/bank 10000`", parse_mode="Markdown")
        return
    if chat_id not in last_predict:
        bot.reply_to(message, "❌ Сначала получи прогноз (кнопка или `/predict`)", parse_mode="Markdown")
        return
    try:
        parts = message.text.split()
        outcome = parts[1]
        odd = float(parts[2])
    except:
        bot.reply_to(message, "Формат: `/kelly П1 2.10`", parse_mode="Markdown")
        return
    probs = last_predict[chat_id]['probabilities']
    if outcome not in probs:
        bot.reply_to(message, "❌ Исход должен быть П1, Х или П2")
        return
    p = probs[outcome]
    q = 1 - p
    fraction = (p * odd - q) / odd
    if fraction <= 0:
        bot.reply_to(message, "❌ Ставка невыгодна (отрицательное ожидание)")
        return
    fraction = min(fraction, 0.25)
    stake = user_bank[chat_id] * fraction
    text = (
        f"🎯 *Расчёт по Келли*\n\n"
        f"Исход: *{outcome}*\n"
        f"Наша вероятность: *{p:.1%}*\n"
        f"Коэффициент БК: *{odd}*\n"
        f"Доля Келли: *{fraction:.1%}*\n"
        f"💰 Сумма ставки: *{stake:,.0f} руб.*"
    )
    bot.reply_to(message, text, parse_mode="Markdown")

@bot.message_handler(commands=['update'])
def update_matches(message):
    bot.send_message(message.chat.id, "📅 Матчи:", reply_markup=matches_keyboard())

print("Бот запущен...")
bot.infinity_polling()
