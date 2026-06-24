
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
import json
import os
import logging
from datetime import datetime, timedelta
from slotmap import RAW_SLOT_COMBINATIONS  

# --- логи ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    filename="bot.log",
    encoding="utf-8"
)
logger = logging.getLogger(__name__)

# --- настройки бота ---
import os
BOT_TOKEN = os.environ.get("BOT_TOKEN")  
START_BALANCE = 500
SPIN_COST = 50

# --- МНОЖИТЕЛИ ---

SYMBOL_MULTIPLIERS = {
    "seven": 5,    
    "bar": 4,     
    "lemon": 3,    
    "cherry": 2   
}

# Множители для джекпота 
JACKPOT_MULTIPLIERS = {
    "seven": 5,    
    "bar": 4,      
    "lemon": 3,    
    "cherry": 2   
}

COOLDOWN_SECONDS = 5

# Пути к файлам данных
BALANCES_FILE = "balances.json"
STATS_FILE = "stats.json"
DODEP_FILE = "dodep_usage.json"

# --- Загрузка и сохранение файлов ---
def load_json_file(filename, default={}):
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    return default

def save_json_file(filename, data):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

# Загружаем данные
balances = load_json_file(BALANCES_FILE, {})
stats = load_json_file(STATS_FILE, {"spins": {}, "losses": {}, "wins": {}})
dodep_usage = load_json_file(DODEP_FILE, {})

# --- создание бота ---
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# --- получение имени пользователя ---
async def get_username(user_id):
    try:
        user = await bot.get_chat(user_id)
        return user.username or user.first_name or f"User {user_id}"
    except:
        return f"User {user_id}"

# --- /start ---
@dp.message(Command("start"))
async def start_command(message: types.Message):
    user_id = str(message.from_user.id)
    username = await get_username(user_id)
    logger.info(f"Пользователь {user_id} ({username}) запустил /start")

    if user_id not in balances:
        balances[user_id] = START_BALANCE
        stats["spins"][user_id] = 0
        stats["losses"][user_id] = 0
        stats["wins"][user_id] = 0
        save_json_file(BALANCES_FILE, balances)
        save_json_file(STATS_FILE, stats)
        logger.info(f"Новый пользователь {user_id}: баланс={START_BALANCE}")

    await message.answer(
        f"🎰 Добро пожаловать в Slot Bot, {username}!\n"
        f"💰 Ваш баланс: {balances[user_id]} монет.\n"
        f"🎲 Стоимость рола: {SPIN_COST} монет.\n\n"
        f"Отправьте стикер 🎰, чтобы крутить слот!",
        parse_mode="Markdown"
    )

# --- /balance ---
@dp.message(Command("balance"))
async def balance_command(message: types.Message):
    user_id = str(message.from_user.id)
    balance = balances.get(user_id, 0)
    logger.info(f"Пользователь {user_id} запросил баланс: {balance}")
    await message.answer(f"💰 Ваш баланс: {balance} монет.", parse_mode="Markdown")

# --- /dodep ---
@dp.message(Command("dodep"))
async def dodep_command(message: types.Message):
    user_id = str(message.from_user.id)
    username = await get_username(user_id)
    today = datetime.now().date()
    logger.info(f"Пользователь {user_id} запросил /dodep")

    if user_id not in dodep_usage:
        dodep_usage[user_id] = {}

    phone_used = dodep_usage[user_id].get("phone") == str(today)
    house_used = dodep_usage[user_id].get("house") == str(today)
    kidney_used = dodep_usage[user_id].get("kidney") == str(today)

    if phone_used and house_used and kidney_used:
        logger.warning(f"Пользователь {user_id} уже использовал все dodep сегодня")
        await message.answer("❌ Вы уже использовали все варианты dodep сегодня!", parse_mode="Markdown")
        return

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[]])

    if not phone_used:
        keyboard.inline_keyboard[0].append(
            InlineKeyboardButton(text=f"📱 Телефон в ломбард (+{SPIN_COST * 2} монет)", callback_data="dodep_phone")
        )
    if not house_used:
        keyboard.inline_keyboard[0].append(
            InlineKeyboardButton(text=f"🏠 Продать хату деда (+{SPIN_COST * 4} монет)", callback_data="dodep_house")
        )
    if not kidney_used:
        keyboard.inline_keyboard[0].append(
            InlineKeyboardButton(text=f"🏥 Продать почку (+{SPIN_COST * 6} монет)", callback_data="dodep_kidney")
        )

    await message.answer("💸 Выберите способ пополнения:", reply_markup=keyboard, parse_mode="Markdown")

# --- обработка кнопок DODEP ---
@dp.callback_query(lambda c: c.data.startswith("dodep_"))
async def process_dodep(callback_query: types.CallbackQuery):
    user_id = str(callback_query.from_user.id)
    today = datetime.now().date()
    action = callback_query.data.split("_")[1]
    logger.info(f"Пользователь {user_id} использовал dodep: {action}")

    roll_multipliers = {"phone": 2, "house": 4, "kidney": 6}
    amount = SPIN_COST * roll_multipliers[action]

    if user_id not in balances:
        balances[user_id] = START_BALANCE

    old_balance = balances[user_id]
    balances[user_id] += amount
    logger.info(f"Пользователь {user_id}: баланс {old_balance} -> {balances[user_id]} (+{amount})")

    if user_id not in dodep_usage:
        dodep_usage[user_id] = {}
    dodep_usage[user_id][action] = str(today)
    save_json_file(BALANCES_FILE, balances)
    save_json_file(DODEP_FILE, dodep_usage)

    username = await get_username(user_id)
    await callback_query.message.edit_text(
        f"✅ Успех, {username}! +{amount} монет.\n💰 Баланс: {balances[user_id]}",
        parse_mode="Markdown"
    )

# --- /top ---
@dp.message(Command("top"))
async def top_command(message: types.Message):
    username = await get_username(str(message.from_user.id))
    logger.info(f"Пользователь {message.from_user.id} запросил /top")

    richest = sorted(balances.items(), key=lambda x: x[1], reverse=True)[:10]
    richest_text = "**🏆 Самый богатый Лудик:**\n"
    for i, (user_id, balance) in enumerate(richest, 1):
        user_name = await get_username(user_id)
        richest_text += f"{i}. {user_name}: {balance} монет\n"

    spins = sorted(stats["spins"].items(), key=lambda x: x[1], reverse=True)[:10]
    spins_text = "\n**🎰 Казино - моя жизнь:**\n"
    for i, (user_id, count) in enumerate(spins, 1):
        user_name = await get_username(user_id)
        spins_text += f"{i}. {user_name}: {count} прокрутов\n"

    losses = sorted(stats["losses"].items(), key=lambda x: x[1], reverse=True)[:10]
    losses_text = "\n**😢 Жизнь в нищете:**\n"
    for i, (user_id, amount) in enumerate(losses, 1):
        user_name = await get_username(user_id)
        losses_text += f"{i}. {user_name}: -{amount} монет\n"

    await message.answer(
        f"{username}, вот текущие топы:\n\n{richest_text}{spins_text}{losses_text}",
        parse_mode="Markdown"
    )

# --- обработка эмодзи (Dice) ---
cooldowns = {}

@dp.message(lambda message: message.dice is not None)
async def handle_dice(message: types.Message):
    user_id = str(message.from_user.id)
    username = await get_username(user_id)
    dice_emoji = message.dice.emoji
    dice_value = message.dice.value

    logger.info(f"Пользователь {user_id} отправил dice: emoji={dice_emoji}, value={dice_value}")

    if dice_emoji != "🎰":
        logger.warning(f"Игнорируем dice с emoji={dice_emoji}")
        return

    # кулдаун
    now = datetime.now()
    if user_id in cooldowns:
        last_spin = cooldowns[user_id]
        if now - last_spin < timedelta(seconds=COOLDOWN_SECONDS):
            remaining = (last_spin + timedelta(seconds=COOLDOWN_SECONDS) - now).seconds
            logger.info(f"Пользователь {user_id} на кулдауне: {remaining}с")
            await message.answer(f"⏳ {username}, подождите ещё {remaining} секунд!", parse_mode="Markdown")
            return
    cooldowns[user_id] = now

    # проверка баланса
    if user_id not in balances:
        balances[user_id] = START_BALANCE
        stats["spins"][user_id] = 0
        stats["losses"][user_id] = 0
        stats["wins"][user_id] = 0
        logger.info(f"Новый пользователь {user_id}: инициализируем баланс={START_BALANCE}")

    if balances[user_id] < SPIN_COST:
        logger.warning(f"Пользователь {user_id} недостаточно средств: баланс={balances[user_id]}, нужно={SPIN_COST}")
        await message.answer(
            f"❌ {username}, недостаточно средств!\n💰 Ваш баланс: {balances[user_id]} монет.\n\n"
            f"Можно пополнить через /dodep",
            parse_mode="Markdown"
        )
        return

    # стоимость ролла
    old_balance = balances[user_id]
    balances[user_id] -= SPIN_COST
    stats["spins"][user_id] = stats["spins"].get(user_id, 0) + 1
    logger.info(f"Пользователь {user_id}: списание {SPIN_COST} монет. Баланс: {old_balance} -> {balances[user_id]}")

    # --- ПОЛУЧАЕМ КОМБИНАЦИЮ ИЗ RAW_SLOT_COMBINATIONS ---
    combination = RAW_SLOT_COMBINATIONS[str(dice_value)]
    logger.info(f"Комбинация для value={dice_value}: {combination}")

    # проверка 3 символа
    if len(combination) != 3:
        logger.error(f"Некорректная длина комбинации: {len(combination)} символов. Дополняем до 3.")
        while len(combination) < 3:
            combination.append("cherry")
        logger.warning(f"Дополнена комбинация: {combination}")

    # --- выйгрыш/проигрыш ---
    unique_symbols = set(combination)
    logger.info(f"Уникальные символы: {unique_symbols}, количество: {len(unique_symbols)}")

    win_amount = 0
    message_text = f"⚠️ {username}, что-то пошло не так."

    if len(unique_symbols) == 3:
        # Все символы разные → ПРОИГРЫШ
        stats["losses"][user_id] = stats["losses"].get(user_id, 0) + SPIN_COST
        message_text = f"😢 {username}, вы проиграли -{SPIN_COST} монет.\n💰 Ваш баланс: {balances[user_id]}"
        logger.info(f"Пользователь {user_id}: ПРОИГРЫШ. Баланс: {balances[user_id]}")

    elif len(unique_symbols) == 2:
        # 2 одинаковых символа → ВЫИГРЫШ (умножаем на множитель символа)
        for symbol in unique_symbols:
            if combination.count(symbol) == 2:
                multiplier = SYMBOL_MULTIPLIERS.get(symbol, 1)
                logger.info(f"Множитель для '{symbol}': {multiplier} (из словаря: {SYMBOL_MULTIPLIERS})")
                win_amount = SPIN_COST * multiplier
                balances[user_id] += win_amount
                stats["wins"][user_id] = stats["wins"].get(user_id, 0) + win_amount
                message_text = f"🎉 {username}, вы выиграли +{win_amount} монет!\n💰 Ваш баланс: {balances[user_id]}"
                logger.info(f"Пользователь {user_id}: ВЫИГРЫШ (2 {symbol}). Множитель: {multiplier}. Выигрыш: +{win_amount}. Баланс: {balances[user_id]}")
                break

    elif len(unique_symbols) == 1:
        # 3 одинаковых символа → ДЖЕКПОТ (умножаем на множитель в квадрате)
        symbol = combination[0]
        multiplier = JACKPOT_MULTIPLIERS.get(symbol, 1)
        win_amount = SPIN_COST * (multiplier ** 2)  # Множитель в квадрате
        balances[user_id] += win_amount
        stats["wins"][user_id] = stats["wins"].get(user_id, 0) + win_amount
        message_text = f"🎉 {username}, ДЖЕКПОТ! +{win_amount} монет!\n💰 Ваш баланс: {balances[user_id]}"
        logger.info(f"Пользователь {user_id}: ДЖЕКПОТ (3 {symbol}). Множитель: {multiplier}² = {multiplier ** 2}. Выигрыш: +{win_amount}. Баланс: {balances[user_id]}")

    else:
        logger.error(f"Некорректная комбинация: {combination}. Уникальных символов: {len(unique_symbols)}")
        message_text = f"⚠️ {username}, ошибка в комбинации. Баланс возвращён."
        balances[user_id] += SPIN_COST

    await message.answer(message_text, parse_mode="Markdown")
    logger.info(f"Отправлено сообщение пользователю {user_id}: {message_text}")

    # Сохраняем данные
    save_json_file(BALANCES_FILE, balances)
    save_json_file(STATS_FILE, stats)

# --- ЗАПУСК БОТА ---
async def main():
    logger.info("Запуск бота...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())