import json
import os
import re
import telebot
from telebot import types

TOKEN = '8203511461:AAE2f_pUaAcbbwnCZSqqjOo_5fLkVEmoE80'
ADMIN_ID = 7589362160

bot = telebot.TeleBot(TOKEN)

DATA_FILE = 'ankety.json'
PAGE_SIZE = 5
user_creation_state = {}

TEMPLATE_PLAYER = (
    "📝 Заполни анкету одним сообщением по шаблону:\n\n"
    "Часы: 1500\n"
    "О себе: 22 года, прайм 20–24, ищу активный клан"
)

TEMPLATE_CLAN = (
    "📝 Отправь объявление о наборе в клан одним сообщением.\n\n"
    "Можно писать в любом формате."
)

PARSE_ERROR = (
    "❌ Не смог прочитать анкету. Убедись, что отправил её в таком формате:\n\n"
    "Часы: 1500\n"
    "О себе: (описание)"
)


def load_ankety():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []


def save_ankety(ankety):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(ankety, f, ensure_ascii=False, indent=2)


def get_kind(a):
    return a.get('kind', 'player')


def kind_badge(a):
    return "🏰 Клан" if get_kind(a) == 'clan' else "👤 Игрок"


def parse_form(text):
    hours_match = re.search(r'(?i)часы\s*:\s*(.+)', text)
    desc_match = re.search(r'(?i)о себе\s*:\s*(.+)', text)
    if not hours_match or not desc_match:
        return None, None
    return hours_match.group(1).strip(), desc_match.group(1).strip()


def main_menu(chat_id=None):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton('📝 Создать анкету'), types.KeyboardButton('🔍 Найти тиммейта/клан'))
    markup.add(types.KeyboardButton('👤 Моя анкета'), types.KeyboardButton('❌ Удалить мою анкету'))
    if chat_id == ADMIN_ID:
        markup.add(types.KeyboardButton('📊 Статистика'))
    return markup


def my_anketa_markup():
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("✏️ Изменить анкету", callback_data="edit_anketa"))
    markup.add(types.InlineKeyboardButton("🗑 Удалить анкету", callback_data="delete_my_anketa"))
    return markup


def type_select_markup():
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("👤 Ищу команду", callback_data="settype:player"),
        types.InlineKeyboardButton("🏰 Набор в клан", callback_data="settype:clan"),
    )
    return markup


def filter_markup():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🌐 Все",           callback_data="filter:0:all"),
        types.InlineKeyboardButton("👤 Только игроки", callback_data="filter:0:player"),
        types.InlineKeyboardButton("🏰 Только кланы",  callback_data="filter:0:clan"),
    )
    markup.add(
        types.InlineKeyboardButton("⚔️ 500+ часов",  callback_data="filter:500:all"),
        types.InlineKeyboardButton("🔥 1000+ часов", callback_data="filter:1000:all"),
        types.InlineKeyboardButton("💀 2000+ часов", callback_data="filter:2000:all"),
    )
    return markup


def apply_filter(ankety, min_hours, kind='all'):
    result = ankety if min_hours == 0 else []
    if min_hours > 0:
        for a in ankety:
            try:
                h = int(re.sub(r'[^\d]', '', a['hours']))
                if h >= min_hours:
                    result.append(a)
            except (ValueError, TypeError):
                pass
    if kind != 'all':
        result = [a for a in result if get_kind(a) == kind]
    return result


def page_text(ankety, page, min_hours, kind='all'):
    total = len(ankety)
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    start = page * PAGE_SIZE
    chunk = ankety[start:start + PAGE_SIZE]
    parts = []
    if min_hours:
        parts.append(f"{min_hours}+ ч")
    if kind != 'all':
        parts.append("только кланы" if kind == 'clan' else "только игроки")
    filter_label = f" ({', '.join(parts)})" if parts else ""
    lines = [f"📋 Всего: {total}{filter_label} | Стр. {page + 1}/{total_pages}\n"]
    for i, a in enumerate(chunk, start=start + 1):
        badge = kind_badge(a)
        lines.append(f"#{i} {badge}\n⏱ Часы: {a['hours']}\nℹ️ О себе: {a['desc']}\n💬 Связь: {a['contact']}")
    return "\n\n".join(lines), total_pages, chunk


def page_markup(page, total_pages, min_hours, kind='all', chunk=None, is_admin=False):
    markup = types.InlineKeyboardMarkup()
    if is_admin and chunk:
        for i, a in enumerate(chunk):
            contact = a['contact']
            badge = "🏰" if get_kind(a) == 'clan' else "👤"
            label = f"🗑 {badge} #{page * PAGE_SIZE + i + 1} ({contact})"
            markup.add(types.InlineKeyboardButton(
                label, callback_data=f"adel:{page}:{min_hours}:{kind}:{contact}"
            ))
    nav = []
    if page > 0:
        nav.append(types.InlineKeyboardButton("← Назад", callback_data=f"page:{page - 1}:{min_hours}:{kind}"))
    if page < total_pages - 1:
        nav.append(types.InlineKeyboardButton("Вперёд →", callback_data=f"page:{page + 1}:{min_hours}:{kind}"))
    if nav:
        markup.add(*nav)
    markup.add(types.InlineKeyboardButton("🔎 Изменить фильтр", callback_data="show_filter"))
    return markup


def stats_text():
    ankety = load_ankety()
    total = len(ankety)
    if total == 0:
        return "📊 Статистика\n\nАнкет пока нет."

    players = sum(1 for a in ankety if get_kind(a) == 'player')
    clans = sum(1 for a in ankety if get_kind(a) == 'clan')

    buckets = {'< 500': 0, '500–999': 0, '1000–1999': 0, '2000+': 0, 'не указано': 0}
    for a in ankety:
        try:
            h = int(re.sub(r'[^\d]', '', a['hours']))
            if h < 500:
                buckets['< 500'] += 1
            elif h < 1000:
                buckets['500–999'] += 1
            elif h < 2000:
                buckets['1000–1999'] += 1
            else:
                buckets['2000+'] += 1
        except (ValueError, TypeError):
            buckets['не указано'] += 1

    lines = [
        f"📊 Статистика\n",
        f"Всего анкет: {total}",
        f"👤 Игроки: {players}",
        f"🏰 Кланы: {clans}\n",
        "По часам:",
    ]
    for label, count in buckets.items():
        if count:
            lines.append(f"  {label} ч — {count} чел.")
    return "\n".join(lines)


@bot.message_handler(commands=['start'])
def start_cmd(message):
    bot.send_message(message.chat.id, "Привет! Я бот для поиска тимы в Rust 🎮", reply_markup=main_menu(message.chat.id))


@bot.message_handler(commands=['stats'])
def stats_cmd(message):
    if message.chat.id != ADMIN_ID:
        return
    bot.send_message(message.chat.id, stats_text(), reply_markup=main_menu(message.chat.id))


@bot.callback_query_handler(func=lambda call: call.data == "edit_anketa")
def handle_edit_anketa(call):
    chat_id = call.message.chat.id
    username = call.from_user.username or f"id{chat_id}"
    tg_link = f"@{username}" if call.from_user.username else f"id{chat_id}"
    ankety = load_ankety()
    my = next((a for a in ankety if a['contact'] == tg_link), None)
    if not my:
        bot.answer_callback_query(call.id, "Анкета не найдена.")
        return
    kind = get_kind(my)
    user_creation_state[chat_id] = {'step': 'form', 'kind': kind, 'editing': True}
    if kind == 'clan':
        prefilled = my['desc']
    else:
        prefilled = f"Часы: {my['hours']}\nО себе: {my['desc']}"
    bot.send_message(
        chat_id,
        f"✏️ Отредактируй и отправь заново:\n\n{prefilled}"
    )
    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda call: call.data == "delete_my_anketa")
def delete_my_anketa(call):
    chat_id = call.message.chat.id
    tg_link = f"@{call.from_user.username}" if call.from_user.username else f"id{chat_id}"
    ankety = load_ankety()
    new_ankety = [a for a in ankety if a['contact'] != tg_link]

    if len(new_ankety) == len(ankety):
        bot.answer_callback_query(call.id, "Анкета не найдена.")
        return

    save_ankety(new_ankety)
    bot.edit_message_text("🗑 Анкета удалена.", chat_id, call.message.message_id)
    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda call: call.data.startswith("settype:"))
def handle_set_type(call):
    chat_id = call.message.chat.id
    kind = call.data.split(":")[1]
    if chat_id not in user_creation_state:
        bot.answer_callback_query(call.id)
        return
    user_creation_state[chat_id]['kind'] = kind
    user_creation_state[chat_id]['step'] = 'form'
    template = TEMPLATE_CLAN if kind == 'clan' else TEMPLATE_PLAYER
    bot.edit_message_text(
        chat_id=chat_id,
        message_id=call.message.message_id,
        text=template
    )
    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda call: call.data == "show_filter")
def handle_show_filter(call):
    bot.edit_message_reply_markup(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        reply_markup=filter_markup()
    )
    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda call: call.data.startswith("filter:"))
def handle_filter(call):
    is_admin = call.message.chat.id == ADMIN_ID
    parts = call.data.split(":")
    min_hours = int(parts[1])
    kind = parts[2] if len(parts) > 2 else 'all'
    ankety = apply_filter(load_ankety(), min_hours, kind)
    if not ankety:
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="😔 Анкет с таким фильтром нет.",
            reply_markup=filter_markup()
        )
    else:
        text, total_pages, chunk = page_text(ankety, 0, min_hours, kind)
        markup = page_markup(0, total_pages, min_hours, kind, chunk, is_admin)
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=text,
            reply_markup=markup
        )
    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda call: call.data.startswith("page:"))
def handle_page(call):
    is_admin = call.message.chat.id == ADMIN_ID
    parts = call.data.split(":")
    page = int(parts[1])
    min_hours = int(parts[2]) if len(parts) > 2 else 0
    kind = parts[3] if len(parts) > 3 else 'all'
    ankety = apply_filter(load_ankety(), min_hours, kind)
    if not ankety:
        bot.answer_callback_query(call.id, "Анкет больше нет.")
        return
    text, total_pages, chunk = page_text(ankety, page, min_hours, kind)
    markup = page_markup(page, total_pages, min_hours, kind, chunk, is_admin)
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=text,
        reply_markup=markup
    )
    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda call: call.data.startswith("adel:"))
def handle_admin_delete(call):
    if call.message.chat.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "Нет доступа.")
        return
    parts = call.data.split(":", 4)
    page = int(parts[1])
    min_hours = int(parts[2])
    kind = parts[3]
    contact = parts[4]
    ankety = load_ankety()
    new_ankety = [a for a in ankety if a['contact'] != contact]
    if len(new_ankety) == len(ankety):
        bot.answer_callback_query(call.id, "Анкета уже удалена.")
    else:
        save_ankety(new_ankety)
        bot.answer_callback_query(call.id, f"✅ Анкета {contact} удалена.")
    filtered = apply_filter(load_ankety(), min_hours, kind)
    safe_page = min(page, max(0, (len(filtered) - 1) // PAGE_SIZE)) if filtered else 0
    if not filtered:
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="😔 Анкет с таким фильтром больше нет.",
            reply_markup=filter_markup()
        )
    else:
        text, total_pages, chunk = page_text(filtered, safe_page, min_hours, kind)
        markup = page_markup(safe_page, total_pages, min_hours, kind, chunk, is_admin=True)
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=text,
            reply_markup=markup
        )


@bot.message_handler(func=lambda message: True)
def handle_text(message):
    chat_id = message.chat.id
    username = message.from_user.username or f"id{chat_id}"

    # 1. Проверяем, находится ли пользователь в процессе создания/редактирования анкеты
    if chat_id in user_creation_state:
        state = user_creation_state[chat_id]

        if state.get('step') == 'form':
            kind = state.get('kind', 'player')

            if kind == 'clan':
                hours = "-"
                desc = message.text.strip()
                if not desc:
                    bot.send_message(chat_id, "❌ Текст анкеты не может быть пустым.")
                    return
            else:
                hours, desc = parse_form(message.text)
                if not hours or not desc:
                    bot.send_message(chat_id, PARSE_ERROR)
                    return

            tg_link = f"@{username}" if message.from_user.username else f"id{chat_id}"

            ankety = load_ankety()
            ankety = [a for a in ankety if a['contact'] != tg_link]
            ankety.append({
                'kind': kind,
                'hours': hours,
                'desc': desc,
                'contact': tg_link
            })
            save_ankety(ankety)

            editing = state.get('editing', False)
            del user_creation_state[chat_id]

            badge = "🏰 Клановая анкета" if kind == 'clan' else "👤 Анкета игрока"
            verb = "обновлена" if editing else "опубликована"

            bot.send_message(chat_id, f"✅ {badge} {verb}!", reply_markup=main_menu(chat_id))
            return

    # 2. Обработка обычных текстовых кнопок меню
    if message.text == '📝 Создать анкету':
        if not message.from_user.username:
            bot.send_message(chat_id, "❌ Установи Username в настройках Telegram!")
            return

        user_creation_state[chat_id] = {'step': 'type'}
        bot.send_message(chat_id, "Выбери тип анкеты:", reply_markup=type_select_markup())

    elif message.text == '🔍 Найти тиммейта/клан':
        ankety = load_ankety()
        if not ankety:
            bot.send_message(chat_id, "Пока анкет нет.")
        else:
            bot.send_message(
                chat_id,
                f"🔎 Выбери фильтр (всего анкет: {len(ankety)}):",
                reply_markup=filter_markup()
            )

    elif message.text == '👤 Моя анкета':
        tg_link = f"@{message.from_user.username}" if message.from_user.username else f"id{chat_id}"
        ankety = load_ankety()
        my = next((a for a in ankety if a['contact'] == tg_link), None)

        if my:
            if get_kind(my) == 'clan':
                bot.send_message(
                    chat_id,
                    f"🏰 Клан\n\n{my['desc']}\n\n💬 Связь: {my['contact']}",
                    reply_markup=my_anketa_markup()
                )
            else:
                bot.send_message(
                    chat_id,
                    f"👤 Игрок\n\n⏱ Часы: {my['hours']}\nℹ️ О себе: {my['desc']}\n💬 Связь: {my['contact']}",
                    reply_markup=my_anketa_markup()
                )
        else:
            bot.send_message(
                chat_id,
                "У тебя пока нет анкеты. Нажми «📝 Создать анкету».",
                reply_markup=main_menu(chat_id)
            )

    elif message.text == '❌ Удалить мою анкету':
        tg_link = f"@{message.from_user.username}" if message.from_user.username else f"id{chat_id}"
        ankety = load_ankety()
        new_ankety = [a for a in ankety if a['contact'] != tg_link]

        if len(new_ankety) == len(ankety):
            bot.send_message(chat_id, "У тебя нет активной анкеты.", reply_markup=main_menu(chat_id))
        else:
            save_ankety(new_ankety)
            bot.send_message(chat_id, "🗑 Твоя анкета удалена.", reply_markup=main_menu(chat_id))

    elif message.text == '📊 Статистика':
        if chat_id == ADMIN_ID:
            bot.send_message(chat_id, stats_text(), reply_markup=main_menu(chat_id))


bot.infinity_polling()
