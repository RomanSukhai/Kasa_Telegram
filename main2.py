import os
import requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from collections import defaultdict


BASE_URL = "https://api.checkbox.ua/api/v1"

TZ = ZoneInfo("Europe/Kyiv")

CLIENT_NAME = os.getenv("CHECKBOX_CLIENT_NAME", "roman-kasa-report")
CLIENT_VERSION = os.getenv("CHECKBOX_CLIENT_VERSION", "1.0.0")

LICENSE_KEY = os.getenv("CHECKBOX_LICENSE_KEY")
PIN_CODE = os.getenv("CHECKBOX_PIN")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


def die(message: str):
    print(f"\n❌ {message}")
    raise SystemExit(1)


def request_json(method, url, headers=None, params=None, json_body=None):
    try:
        r = requests.request(
            method,
            url,
            headers=headers,
            params=params,
            json=json_body,
            timeout=30,
        )
    except requests.RequestException as e:
        die(f"Помилка HTTP-запиту: {e}")

    try:
        body = r.json()
    except Exception:
        body = None

    return {
        "ok": 200 <= r.status_code < 300,
        "status": r.status_code,
        "json": body,
        "text": r.text,
        "url": r.url,
    }


def signin_by_pin():
    if not LICENSE_KEY:
        die("Немає CHECKBOX_LICENSE_KEY")

    if not PIN_CODE:
        die("Немає CHECKBOX_PIN")

    url = f"{BASE_URL}/cashier/signinPinCode"

    headers = {
        "accept": "application/json",
        "X-Client-Name": CLIENT_NAME,
        "X-Client-Version": CLIENT_VERSION,
        "X-License-Key": LICENSE_KEY,
        "Content-Type": "application/json",
    }

    result = request_json(
        "POST",
        url,
        headers=headers,
        json_body={"pin_code": PIN_CODE},
    )

    if not result["ok"]:
        print(result["text"])
        die(f"Не вдалося авторизуватись у Checkbox. HTTP {result['status']}")

    token = result["json"].get("access_token")

    if not token:
        print(result["json"])
        die("У відповіді Checkbox немає access_token")

    return token


def get_today_range():
    now = datetime.now(TZ)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)
    return start, end


def parse_dt(raw):
    if not raw:
        return None

    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(TZ)
    except Exception:
        return None


def is_today_receipt(receipt, start, end):
    raw = receipt.get("created_at") or receipt.get("fiscal_date")
    dt = parse_dt(raw)

    if not dt:
        return False

    return start <= dt < end


def get_goods(receipt):
    goods = receipt.get("goods") or receipt.get("items") or []

    if not isinstance(goods, list):
        return []

    return goods


def is_fiscal_sale(receipt):
    fiscal_code = receipt.get("fiscal_code") or receipt.get("fiscal_number")
    goods = get_goods(receipt)

    return (
        receipt.get("status") == "DONE"
        and bool(fiscal_code)
        and bool(goods)
    )


def extract_receipts(data):
    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        for key in ["items", "results", "data", "receipts"]:
            if isinstance(data.get(key), list):
                return data[key]

    return []


def get_receipts_page(token, offset=0, limit=100):
    start, end = get_today_range()

    headers = {
        "accept": "application/json",
        "X-Client-Name": CLIENT_NAME,
        "X-Client-Version": CLIENT_VERSION,
        "Authorization": f"Bearer {token}",
    }

    params = {
        "from_date": start.isoformat(),
        "to_date": end.isoformat(),
        "limit": limit,
        "offset": offset,
    }

    result = request_json(
        "GET",
        f"{BASE_URL}/receipts",
        headers=headers,
        params=params,
    )

    if not result["ok"]:
        print(result["text"])
        die(f"Не вдалося отримати список чеків. HTTP {result['status']}")

    return extract_receipts(result["json"])


def get_all_receipts(token):
    all_receipts = []
    offset = 0
    limit = 100

    while True:
        page = get_receipts_page(token, offset=offset, limit=limit)

        if not page:
            break

        all_receipts.extend(page)

        if len(page) < limit:
            break

        offset += limit

    return all_receipts


def get_full_receipt(token, receipt_id):
    headers = {
        "accept": "application/json",
        "X-Client-Name": CLIENT_NAME,
        "X-Client-Version": CLIENT_VERSION,
        "Authorization": f"Bearer {token}",
    }

    result = request_json(
        "GET",
        f"{BASE_URL}/receipts/{receipt_id}",
        headers=headers,
    )

    if result["ok"] and isinstance(result["json"], dict):
        return result["json"]

    return None


def money_to_kop(value):
    if value is None:
        return 0

    if isinstance(value, int):
        return value

    if isinstance(value, float):
        return int(round(value * 100))

    if isinstance(value, str):
        value = value.replace(",", ".").strip()

        try:
            return int(round(float(value) * 100))
        except Exception:
            return 0

    return 0


def kop_to_uah(value):
    return value / 100


def get_receipt_total(receipt):
    for key in ["total_sum", "sum", "total", "payments_sum"]:
        value = receipt.get(key)

        if value is not None:
            return money_to_kop(value)

    return 0


def get_good_name(item):
    good = item.get("good", {})

    if not isinstance(good, dict):
        good = {}

    return good.get("name") or item.get("name") or "Невідомий товар"


def get_line_sum(item):
    for key in ["sum", "total_sum", "line_sum"]:
        value = item.get(key)

        if value is not None:
            return money_to_kop(value)

    good = item.get("good", {})

    if not isinstance(good, dict):
        good = {}

    price = good.get("price") or item.get("price")
    qty = item.get("quantity", 1000)

    price_kop = money_to_kop(price)

    if isinstance(qty, int):
        return int(round(price_kop * qty / 1000))

    try:
        return int(round(price_kop * float(qty)))
    except Exception:
        return price_kop


def detect_category(name):
    name = name.lower()

    if "вата" in name:
        return "Вата"

    if "попкорн" in name or "popcorn" in name:
        return "Попкорн"

    if "фото" in name:
        return "Фото"

    return "Інше"


def get_payments(receipt):
    payments = receipt.get("payments") or receipt.get("payment") or []

    if isinstance(payments, dict):
        payments = [payments]

    if not isinstance(payments, list):
        payments = []

    return payments


def get_payment_sum(payment):
    for key in ["value", "sum", "amount", "payment_sum"]:
        value = payment.get(key)

        if value is not None:
            return money_to_kop(value)

    return 0


def detect_payment_type(payment):
    raw_values = []

    for key in ["type", "label", "payment_system", "provider_type", "code"]:
        value = payment.get(key)

        if value is not None:
            raw_values.append(str(value).lower())

    text = " ".join(raw_values)

    if (
        "cashless" in text
        or "card" in text
        or "карт" in text
        or "безгот" in text
        or "terminal" in text
    ):
        return "Карта"

    if "cash" in text or "гот" in text:
        return "Готівка"

    return "Невідомо"


def aggregate_receipts(receipts):
    result = {
        "Готівка": defaultdict(int),
        "Карта": defaultdict(int),
        "Невідомо": defaultdict(int),
    }

    receipt_count = 0
    receipt_total = 0

    for receipt in receipts:
        goods = get_goods(receipt)
        payments = get_payments(receipt)

        total = get_receipt_total(receipt)

        receipt_total += total
        receipt_count += 1

        category_sums = defaultdict(int)

        for item in goods:
            name = get_good_name(item)
            category = detect_category(name)
            category_sums[category] += get_line_sum(item)

        payment_parts = []

        for payment in payments:
            payment_type = detect_payment_type(payment)
            payment_sum = get_payment_sum(payment)

            if payment_sum > 0:
                payment_parts.append((payment_type, payment_sum))

        if not payment_parts:
            for category, amount in category_sums.items():
                result["Невідомо"][category] += amount
            continue

        if len(payment_parts) == 1:
            payment_type = payment_parts[0][0]

            for category, amount in category_sums.items():
                result[payment_type][category] += amount

            continue

        payments_sum = sum(item[1] for item in payment_parts)

        if payments_sum <= 0:
            for category, amount in category_sums.items():
                result["Невідомо"][category] += amount
            continue

        for payment_type, payment_sum in payment_parts:
            ratio = payment_sum / payments_sum

            for category, amount in category_sums.items():
                result[payment_type][category] += int(round(amount * ratio))

    return result, receipt_count, receipt_total


def build_report_message(aggregated, receipt_count, receipt_total):
    today_str = datetime.now(TZ).strftime("%d.%m.%Y")

    lines = []

    lines.append(f"📊 <b>ЗВІТ ПО КАСІ ЗА {today_str}</b>")
    lines.append("")
    lines.append("<pre>")
    lines.append(
        f"{'Оплата':<10}"
        f"{'Вата':>10}"
        f"{'Попкорн':>12}"
        f"{'Фото':>10}"
        f"{'Всього':>10}"
    )
    lines.append("-" * 52)

    grand_vata = 0
    grand_popcorn = 0
    grand_photo = 0
    grand_total = 0

    for payment_type in ["Готівка", "Карта", "Невідомо"]:
        vata = aggregated[payment_type]["Вата"]
        popcorn = aggregated[payment_type]["Попкорн"]
        photo = aggregated[payment_type]["Фото"]
        other = aggregated[payment_type]["Інше"]

        row_total = vata + popcorn + photo + other

        if payment_type == "Невідомо" and row_total == 0:
            continue

        grand_vata += vata
        grand_popcorn += popcorn
        grand_photo += photo
        grand_total += row_total

        row = (
            f"{payment_type:<10}"
            f"{kop_to_uah(vata):>10.2f}"
            f"{kop_to_uah(popcorn):>12.2f}"
            f"{kop_to_uah(photo):>10.2f}"
            f"{kop_to_uah(row_total):>10.2f}"
        )

        lines.append(row)

    lines.append("-" * 52)

    total_row = (
        f"{'РАЗОМ':<10}"
        f"{kop_to_uah(grand_vata):>10.2f}"
        f"{kop_to_uah(grand_popcorn):>12.2f}"
        f"{kop_to_uah(grand_photo):>10.2f}"
        f"{kop_to_uah(grand_total):>10.2f}"
    )

    lines.append(total_row)
    lines.append("</pre>")
    lines.append("")
    lines.append(f"🧾 Чеків продажу: <b>{receipt_count}</b>")
    lines.append(f"💰 Всього: <b>{kop_to_uah(receipt_total):.2f} грн</b>")

    return "\n".join(lines)


def send_telegram_message(text):
    if not TELEGRAM_BOT_TOKEN:
        die("Немає TELEGRAM_BOT_TOKEN")

    if not TELEGRAM_CHAT_ID:
        die("Немає TELEGRAM_CHAT_ID")

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
    }

    r = requests.post(url, json=payload, timeout=30)

    if not r.ok:
        print(r.text)
        die(f"Не вдалося надіслати Telegram-повідомлення. HTTP {r.status_code}")

    print("✅ Звіт надіслано в Telegram")


def print_console_report(message):
    console_text = (
        message
        .replace("<b>", "")
        .replace("</b>", "")
        .replace("<pre>", "")
        .replace("</pre>", "")
    )

    print("\n" + console_text)


def main():
    print("🔐 Авторизація в Checkbox...")
    token = signin_by_pin()
    print("✅ Авторизація успішна")

    start, end = get_today_range()

    print("\n📅 Беру тільки сьогодні:")
    print(f"Від: {start.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"До:  {end.strftime('%Y-%m-%d %H:%M:%S')}")

    print("\n📥 Завантажую чеки...")
    raw_receipts = get_all_receipts(token)

    today_short = [
        receipt for receipt in raw_receipts
        if is_today_receipt(receipt, start, end) and is_fiscal_sale(receipt)
    ]

    print(f"✅ Знайдено сьогоднішніх фіскальних чеків: {len(today_short)}")

    today_full = []

    for receipt in today_short:
        receipt_id = receipt.get("id") or receipt.get("receipt_id") or receipt.get("uuid")

        if not receipt_id:
            today_full.append(receipt)
            continue

        full_receipt = get_full_receipt(token, receipt_id)
        today_full.append(full_receipt or receipt)

    aggregated, receipt_count, receipt_total = aggregate_receipts(today_full)

    message = build_report_message(aggregated, receipt_count, receipt_total)

    print_console_report(message)

    send_telegram_message(message)


if __name__ == "__main__":
    main()