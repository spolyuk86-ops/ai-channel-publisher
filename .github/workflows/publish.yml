"""
Публікує пост у Telegram-канал відповідно до поточного дня тижня та часу (UTC),
або примусово — якщо задано змінну середовища FORCE_SLOT (для ручного тесту).
"""

import json
import os
import sys
import urllib.request
import urllib.parse
from datetime import datetime, timezone

UTC_HOUR_TO_SLOT = {
    5: "08:00",
    8: "11:00",
    12: "15:00",
}

WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def load_schedule():
    with open(os.path.join(os.path.dirname(__file__), "schedule.json"), "r", encoding="utf-8") as f:
        return json.load(f)


def get_current_slot():
    now = datetime.now(timezone.utc)
    weekday = WEEKDAYS[now.weekday()]
    slot = UTC_HOUR_TO_SLOT.get(now.hour)
    return weekday, slot


def send_message(token: str, chat_id: str, text: str):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = urllib.parse.urlencode({
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
    }).encode()
    req = urllib.request.Request(url, data=data)
    with urllib.request.urlopen(req) as resp:
        result = resp.read().decode()
        print(result)


def main():
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    channel = os.environ.get("CHANNEL_USERNAME")
    if not token or not channel:
        print("Помилка: не задано TELEGRAM_BOT_TOKEN або CHANNEL_USERNAME")
        sys.exit(1)

    force_slot = os.environ.get("FORCE_SLOT", "").strip()
    now = datetime.now(timezone.utc)
    weekday = WEEKDAYS[now.weekday()]

    if force_slot:
        slot = force_slot
        print(f"Тестовий режим: примусово беремо слот {slot} для {weekday}")
    else:
        weekday, slot = get_current_slot()
        if not slot:
            print("Поточна UTC-година не відповідає жодному слоту публікації. Нічого не робимо.")
            return

    schedule = load_schedule()
    text = schedule.get(weekday, {}).get(slot)
    if not text:
        print(f"Немає поста для {weekday} / {slot}")
        return

    send_message(token, channel, text)
    print(f"Опубліковано: {weekday} {slot}")


if __name__ == "__main__":
    main()
