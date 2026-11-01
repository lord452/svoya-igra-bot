text\n{table_block}\n```\n"

        f"📊 Счет: {scores}\n"

        f"👉 СЕЙЧАС ХОДИТ: {cur_p['name']}\n"

        f"Выберите категорию и сумму на кнопках ниже:"

    )

    return header

def build_board_keyboard(g):

    kb = types.InlineKeyboardMarkup()

    # Строим 10 рядов по 5 кнопок

    for r in range(10):

        row = []

        for c in range(5):

            cat = CATEGORIES[c]

            used = g["board"][cat][r]

            price = PRICES[r]

            text = "✖️" if used else f"{price}"

            data = "none" if used else f"pick|{c}|{r}"

            row.append(types.InlineKeyboardButton(text, callback_data=data))

        kb.row(*row)

    return kb

def send_board(cid, g):

    text = generate_board_text(g)

    kb = build_board_keyboard(g)

    bot.send_message(cid, text, parse_mode="Markdown", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == "game_start")

def cb_start_game(c):

    cid = c.message.chat.id

    g = games.get(cid)

    if not g or g["status"] != "lobby":

        return bot.answer_callback_query(c.id, "Игра уже началась!")

g["status"] = "playing"
bot.delete_message(cid, c.message.message_id)
send_board(cid, g)


@bot.callback_query_handler(func=lambda c: c.data.startswith("pick|"))

def cb_pick_cell(c):

    cid = c.message.chat.id

    g = games.get(cid)

    if not g or g["status"] != "playing":

        return bot.answer_callback_query(c.id, "Игра не активна!")

cur_p = g["players"][g["turn"]]
if c.from_user.id != cur_p["id"]:
    return bot.answer_callback_query(c.id, f"⛔ Сейчас ход игрока: {cur_p['name']}!", show_alert=True)

_, col_s, row_s = c.data.split("|")
col, row = int(col_s), int(row_s)
cat = CATEGORIES[col]
price = PRICES[row]

if g["board"][cat][row]:
    return bot.answer_callback_query(c.id, "Эта ячейка уже сгорела!")

# Сжигаем ячейку
g["board"][cat][row] = True
q_data = QUESTIONS[cat][row]

# Перемешиваем ответы
answers = list(enumerate(q_data[1]))
random.shuffle(answers)

g["cur_q"] = {
    "cat": cat,
    "price": price,
    "q_text": q_data[0],
    "answers": answers,
    "correct_idx": q_data[2],
    "player": cur_p
}

kb = types.InlineKeyboardMarkup()
for orig_idx, a_text in answers:
    kb.row(types.InlineKeyboardButton(a_text, callback_data=f"ans|{orig_idx}"))

bot.delete_message(cid, c.message.message_id)
bot.send_message(
    cid,
    f"❓ **Вопрос для {cur_p['name']}**\n"
    f"Категория: *{cat}* | Цена: *{price} баллов*\n\n"
    f"*{q_data[0]}*",
    parse_mode="Markdown",
    reply_markup=kb
)

@bot.callback_query_handler(func=lambda c: c.data.startswith("ans|"))

def cb_answer(c):

    cid = c.message.chat.id

    g = games.get(cid)

    if not g or not g.get("cur_q"):

        return bot.answer_callback_query(c.id, "Вопрос устарел!")

cur_q = g["cur_q"]
cur_p = cur_q["player"]

if c.from_user.id != cur_p["id"]:
    return bot.answer_callback_query(c.id, f"⛔ Отвечает только {cur_p['name']}!", show_alert=True)

chosen_idx = int(c.data.split("|")[1])
is_correct = (chosen_idx == cur_q["correct_idx"])

bot.delete_message(cid, c.message.message_id)

if is_correct:
    cur_p["score"] += cur_q["price"]
    u = get_user(cur_p["id"], cur_p["name"])
    u["points"] += cur_q["price"]
    save_data(db)
    bot.send_message(cid, f"✅ **ВЕРНО!** {cur_p['name']} забирает *+{cur_q['price']}* баллов!", parse_mode="Markdown")
else:
    bot.send_message(cid, f"❌ **НЕВЕРНО!** {cur_p['name']} получает *0* баллов. Вопрос сгорел!", parse_mode="Markdown")

g["cur_q"] = None

# Проверяем, остались ли еще свободные ячейки
any_left = any(not g["board"][cat][r] for cat in CATEGORIES for r in range(10))
if not any_left:
    sorted_p = sorted(g["players"], key=lambda x: x["score"], reverse=True)
    winner = sorted_p[0]
    res = "🏁 **ИГРА ОКОНЧЕНА!** 🏁\n\n🏆 **Победитель:** " + winner["name"] + f" ({winner['score']} баллов)\n\nИтоги:\n"
    for i, p in enumerate(sorted_p, 1):
        res += f"{i}. {p['name']} — {p['score']} баллов\n"
    bot.send_message(cid, res, parse_mode="Markdown")
    del games[cid]
    return

# Переход хода к следующему игроку
g["turn"] = (g["turn"] + 1) % len(g["players"])
send_board(cid, g)


----------------- АПГРЕЙДЕР И ОБМЕН -----------------

@bot.message_handler(func=lambda m: m.text == "🚀 Апгрейдер")

def menu_upgrade(m):

    kb = types.InlineKeyboardMarkup()

    kb.row(types.InlineKeyboardButton("x1.5 (шанс 55%)", callback_data="upg|1.5"))

    kb.row(types.InlineKeyboardButton("x2.0 (шанс 40%)", callback_data="upg|2.0"))

    kb.row(types.InlineKeyboardButton("x3.0 (шанс 22%)", callback_data="upg|3.0"))

    kb.row(types.InlineKeyboardButton("x5.0 (шанс 8%)", callback_data="upg|5.0"))

    bot.send_message(m.chat.id, "🎲 Выбери множитель для апгрейда:", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("upg|"))

def cb_upg(c):

    mult = float(c.data.split("|")[1])

    pending_upgrade[c.from_user.id] = mult

    bot.send_message(c.message.chat.id, f"Выбран x{mult}. Теперь отправь в чат число баллов (ставку):", parse_mode="Markdown")

    bot.answer_callback_query(c.id)

@bot.message_handler(func=lambda m: m.from_user.id in pending_upgrade and m.text.isdigit())

def exec_upgrade(m):

    mult = pending_upgrade.pop(m.from_user.id)

    bet = int(m.text)

    u = get_user(m.from_user.id, m.from_user.username or m.from_user.first_name)

if bet <= 0:
    return bot.send_message(m.chat.id, "Ставка должна быть больше 0!")
if u["points"] < bet:
    return bot.send_message(m.chat.id, f"Недостаточно баллов!

Баланс: {u['points']}")

chances = {1.5: 55, 2.0: 40, 3.0: 22, 5.0: 8}
u["points"] -= bet

if random.uniform(0, 100) < chances[mult]:
    win = int(bet * mult)
    u["points"] += win
    save_data(db)
    bot.send_message(m.chat.id, f"🎉 **ПОБЕДА!** Ты выиграл *{win}* баллов! Новый баланс: {u['points']}", parse_mode="Markdown")
else:
    save_data(db)
    bot.send_message(m.chat.id, f"💥 **Не повезло!** {bet} баллов сгорели. Баланс: {u['points']}", parse_mode="Markdown")


@bot.message_handler(func=lambda m: m.text == "🎁 Обмен")

def menu_shop(m):

    kb = types.InlineKeyboardMarkup()

    items = [

        ("10 Telegram Stars", 3000), ("25 Telegram Stars", 7000), ("60 Telegram Stars", 15000),

        ("50 Robux", 4000), ("120 Robux", 9000), ("260 Robux", 18000)

    ]

    for name, cost in items:

        kb.row(types.InlineKeyboardButton(f"{name} — {cost} баллов", callback_data=f"buy|{cost}|{name}"))

    bot.send_message(m.chat.id, f"🎁 Магазин подарков\nВыдачу производит: {ADMIN_USERNAME}", parse_mode="Markdown", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("buy|"))

def cb_buy(c):

    _, cost_s, item_name = c.data.split("|")

    cost = int(cost_s)

    u = get_user(c.from_user.id, c.from_user.username or c.from_user.first_name)

if u["points"] < cost:
    return bot.answer_callback_query(c.id, "Недостаточно баллов!", show_alert=True)

u["points"] -= cost
code = f"Q{random.randint(10,99)}-RS"
db["orders"].append({
    "code": code,
    "user_id": c.from_user.id,
    "name": u["name"],
    "prize": item_name,
    "cost": cost
})
save_data(db)

bot.send_message(
    c.message.chat.id,
    f"✅ **Заявка оформлена!**\n\n"
    f"📦 Товар: *{item_name}*\n"
    f"🔑 Твой код: `{code}`\n\n"
    f"Скопируй этот код и напиши администратору: {ADMIN_USERNAME}",
    parse_mode="Markdown"
)

try:
    bot.send_message(
        ADMIN_ID,
        f"🔔 **Новая покупка!**\n"
        f"Код: `{code}`\n"
        f"Товар: {item_name}\n"
        f"Покупатель: @{u['name']} (ID: {c.from_user.id})",
        parse_mode="Markdown"
    )
except:
    pass
bot.answer_callback_query(c.id)


----------------- АДМИНКА -----------------

@bot.message_handler(func=lambda m: m.text == "👑 Админка")

def admin_cmd(m):

    if m.from_user.id in admin_sessions:

        return show_admin(m.chat.id)

    bot.send_message(m.chat.id, "Введи пароль администратора:")

@bot.message_handler(func=lambda m: m.text == ADMIN_PASSWORD)

def admin_login(m):

    admin_sessions.add(m.from_user.id)

    show_admin(m.chat.id)

def show_admin(cid):

    kb = types.InlineKeyboardMarkup()

    kb.row(types.InlineKeyboardButton("📦 Список заявок", callback_data="adm_orders"))

    kb.row(types.InlineKeyboardButton("🚪 Выйти", callback_data="adm_logout"))

    bot.send_message(cid, "👑 Панель Администратора", parse_mode="Markdown", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == "adm_orders")

def cb_admin_orders(c):

    if c.from_user.id not in admin_sessions:

        return bot.answer_callback_query(c.id, "Нет доступа")

    if not db["orders"]:

        return bot.send_message(c.message.chat.id, "Заявок пока нет.")

txt = "📦 **Активные заявки:**\n\n"
for o in db["orders"][-10:]:
    txt += f"• `{o['code']}` — {o['prize']} (от @{o['name']})\n"
bot.send_message(c.message.chat.id, txt, parse_mode="Markdown")


@bot.callback_query_handler(func=lambda c: c.data == "adm_logout")

def cb_admin_logout(c):

    admin_sessions.discard(c.from_user.id)

    bot.send_message(c.message.chat.id, "Вы вышли из админки.")

if name == "main":

    print("Бот 'Своя Игра 6.0' успешно запущен!")

    bot.infinity_polling()
