"""Publish a scheduled post to Telegram."""

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone

# GitHub event.schedule tells us which cron entry triggered the run.
# The schedule is deliberately defined in UTC to represent Kyiv local time:
# winter: 08:00/11:00/15:00 = 06:00/09:00/13:00 UTC.
CRON_TO_SLOT_INDEX = {
    "0 6 * * *": 0,
    "0 9 * * *": 1,
    "0 13 * * *": 2,
    # Keep compatibility with an old queued run created by the previous workflow.
    "0 5 * * *": 0,
    "0 8 * * *": 1,
    "0 12 * * *": 2,
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
    return (today - start).days % len(schedule["days"])


def get_slot_index():
    cron_expr = os.environ.get("GITHUB_EVENT_SCHEDULE", "").strip()
    if cron_expr in CRON_TO_SLOT_INDEX:
        return CRON_TO_SLOT_INDEX[cron_expr]
    print(f"Попередження: невідомий cron {cron_expr!r}; запуск без публікації.")
    return None


def build_payload(chat_id: str, post) -> dict:
    if isinstance(post, str):
        text, button = post, None
    else:
        text, button = post.get("text", ""), post.get("button")

    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
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
                raise RuntimeError(f"Telegram API ok=false: {body}")
            print("Успіх, message_id:", body.get("result", {}).get("message_id"))
            return
        except (urllib.error.URLError, urllib.error.HTTPError, RuntimeError) as e:
            last_error = e
            print(f"Спроба {attempt}/{MAX_RETRIES} не вдалась: {e}")
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY_SEC)

    raise SystemExit(f"Усі {MAX_RETRIES} спроби публікації провалились: {last_error}")


def main():
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    channel = os.environ.get("CHANNEL_USERNAME")
    if not token or not channel:
        print("Помилка: не задано TELEGRAM_BOT_TOKEN або CHANNEL_USERNAME")
        sys.exit(1)

    schedule = load_schedule()
    force_slot = os.environ.get("FORCE_SLOT", "").strip()
    force_day = os.environ.get("FORCE_DAY_INDEX", "").strip()

    day_index = int(force_day) % len(schedule["days"]) if force_day else get_day_index(schedule)

    if force_slot:
        if force_slot not in SLOT_LABELS:
            print(f"Помилка: FORCE_SLOT має бути одним з {SLOT_LABELS}")
            sys.exit(1)
        slot_index = SLOT_LABELS.index(force_slot)
        print(f"Тестовий режим: день {day_index}, слот {force_slot}")
    else:
        slot_index = get_slot_index()
        if slot_index is None:
            return

    try:
        post = schedule["days"][day_index][slot_index]
    except (IndexError, KeyError):
        raise SystemExit(f"Немає поста для day_index={day_index}, slot_index={slot_index}")

    send_message(token, build_payload(channel, post))
    print(f"Опубліковано: день {day_index + 1}/{len(schedule['days'])}, слот {SLOT_LABELS[slot_index]}")


if __name__ == "__main__":
    main()
