"""
Публікує пост у Telegram-канал відповідно до дня 30-денного циклу та поточного
часу (UTC), або примусово — якщо задано FORCE_SLOT (для ручного тесту).

День циклу обчислюється детерміновано від start_date у schedule.json:
    day_index = (сьогодні - start_date) % кількість_днів_у_schedule

Це дозволяє мати послідовний контент на 30 днів наперед без повторів,
і при цьому НЕ вимагає жодного персистентного стану між запусками —
GitHub Actions stateless, а ми просто рахуємо зсув від фіксованої дати.
Після 30-го дня цикл починається знову з дня 0.
"""

import json
import os
import sys
import time
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime, date, timezone

UTC_HOUR_TO_SLOT_INDEX = {
    5: 0,   # 08:00 Europe/Kyiv (літній час, UTC+3)
    8: 1,   # 11:00 Europe/Kyiv
    12: 2,  # 15:00 Europe/Kyiv
}
SLOT_LABELS = ["08:00", "11:00", "15:00"]

MAX_RETRIES = 3
RETRY_DELAY_SEC = 5


def load_schedule():
    path = os.path.join(os.path.dirname(__file__), "schedule.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_day_index(schedule: dict) -> int:
    start = date.fromisoformat(schedule["start_date"])
    today = datetime.now(timezone.utc).date()
    delta_days = (today - start).days
    cycle_len = len(schedule["days"])
    return delta_days % cycle_len


def get_slot_index():
    now = datetime.now(timezone.utc)
    return UTC_HOUR_TO_SLOT_INDEX.get(now.hour)


def build_payload(chat_id: str, post) -> dict:
    """post — або рядок (простий текст), або dict {"text":..., "button": {"text":..., "url":...}}."""
    if isinstance(post, str):
        text, button = post, None
    else:
        text, button = post.get("text", ""), post.get("button")

    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
    }
    if button:
        payload["reply_markup"] = json.dumps({
            "inline_keyboard": [[{"text": button["text"], "url": button["url"]}]]
        })
    return payload


def send_message(token: str, payload: dict):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = urllib.parse.urlencode(payload).encode()

    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            req = urllib.request.Request(url, data=data)
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = json.loads(resp.read().decode())
            if not body.get("ok"):
                # Telegram відповів 200, але позначив запит як неуспішний —
                # трапляється рідко, але без цієї перевірки помилка проходить непоміченою.
                raise RuntimeError(f"Telegram API повернув ok=false: {body}")
            print("Успіх:", body.get("result", {}).get("message_id"))
            return
        except (urllib.error.URLError, urllib.error.HTTPError, RuntimeError) as e:
            last_error = e
            body_detail = ""
            if isinstance(e, urllib.error.HTTPError):
                try:
                    body_detail = e.read().decode()
                except Exception:
                    pass
            print(f"Спроба {attempt}/{MAX_RETRIES} не вдалась: {e} {body_detail}")
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY_SEC)

    raise SystemExit(f"Усі {MAX_RETRIES} спроби публікації провалились. Остання помилка: {last_error}")


def main():
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    channel = os.environ.get("CHANNEL_USERNAME")
    if not token or not channel:
        print("Помилка: не задано TELEGRAM_BOT_TOKEN або CHANNEL_USERNAME")
        sys.exit(1)

    schedule = load_schedule()

    force_slot = os.environ.get("FORCE_SLOT", "").strip()
    force_day = os.environ.get("FORCE_DAY_INDEX", "").strip()

    if force_day:
        day_index = int(force_day) % len(schedule["days"])
    else:
        day_index = get_day_index(schedule)

    if force_slot:
        if force_slot not in SLOT_LABELS:
            print(f"Помилка: FORCE_SLOT має бути одним з {SLOT_LABELS}, отримано {force_slot!r}")
            sys.exit(1)
        slot_index = SLOT_LABELS.index(force_slot)
        print(f"Тестовий режим: примусово день {day_index}, слот {force_slot}")
    else:
        slot_index = get_slot_index()
        if slot_index is None:
            print("Поточна UTC-година не відповідає жодному слоту публікації. Нічого не робимо.")
            return

    try:
        post = schedule["days"][day_index][slot_index]
    except (IndexError, KeyError):
        print(f"Немає поста для day_index={day_index}, slot_index={slot_index}")
        return

    payload = build_payload(channel, post)
    send_message(token, payload)
    print(f"Опубліковано: день циклу {day_index + 1}/{len(schedule['days'])}, слот {SLOT_LABELS[slot_index]}")


if __name__ == "__main__":
    main()
