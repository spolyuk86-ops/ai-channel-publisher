"""
Публікує пост у Telegram-канал відповідно до поточного дня тижня та часу (UTC).
Токен бота і назва каналу беруться з змінних середовища (GitHub Secrets) —
ніде в коді вони не зберігаються.

Змінні середовища:
  TELEGRAM_BOT_TOKEN   — токен бота від @BotFather
  CHANNEL_USERNAME     — @AI_NA_KAGDIY_DEN (або числовий chat_id)
"""

import json
import os
import sys
import urllib.request
import urllib.parse
from datetime import datetime, timezone

# Відповідність UTC-години слоту публікації.
# 08:00 / 11:00 / 15:00 за Києвом (EEST, UTC+3) = 05:00 / 08:00 / 12:00 UTC.
# Якщо в Україні діє зимовий час (UTC+2), зсуньте ці значення на -1 годину
# або поправте cron-розклад у .github/workflows/publish.yml.
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

    weekday, slot = get_current_slot()
    if not slot:
        print(f"Поточна UTC-година не відповідає жодному слоту публікації. Нічого не робимо.")
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
