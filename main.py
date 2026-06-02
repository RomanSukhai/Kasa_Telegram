import os
import requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from collections import defaultdict
BASE_URL = "https://api.checkbox.ua/api/v1"

LICENSE_KEY = os.getenv("CHECKBOX_LICENSE_KEY")
PIN_CODE = os.getenv("CHECKBOX_PIN")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

CLIENT_NAME = os.getenv("CHECKBOX_CLIENT_NAME", "roman-kasa-report")
CLIENT_VERSION = os.getenv("CHECKBOX_CLIENT_VERSION", "1.0.0")

LICENSE_KEY ="640ee0a7e53a990f7af7d0b0"
PIN_CODE = "1059504895"
TELEGRAM_BOT_TOKEN="8954572345:AAEpzGOt4407ijr4hXTzeGj1dN2fghn4Km8"
TELEGRAM_CHAT_ID="https://t.me/javeresw"
# Або залишити через env:
# LICENSE_KEY = os.getenv("CHECKBOX_LICENSE_KEY")
# PIN_CODE = os.getenv("CHECKBOX_PIN")

TZ = ZoneInfo("Europe/Kyiv")


def die(message: str):
    print(f"\n❌ {message}")
    raise SystemExit(1)


def request_json(method, url, headers=None, params=None, json_body=None):
    r = requests.request(
        method,
        url,
        headers=headers,
        params=params,
        json=json_body,
        timeout=30,
    )

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
        die("Немає LICENSE_KEY")
    if not PIN_CODE:
        die("Немає PIN_CODE")

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
        die(f"Не вдалося авторизуватись. HTTP {result['status']}")

    token = result["json"].get("access_token")
    if not token:
        die("У відповіді немає access_token")

    return token


def get_today_range():
    now = datetime.now(TZ)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)
    return start, end


def parse_dt(raw):
    if not raw:
        return None
    return datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(TZ)


def is_today_receipt(receipt, start, end):
    raw = receipt.get("created_at") or receipt.get("fiscal_date")
    dt = parse_dt(raw)
    if not dt:
        return False
    return start <= dt < end


def has_goods(receipt):
    goods = receipt.get("goods") or receipt.get("items") or []
    return bool(goods)


def is_fiscal_sale(receipt):
    fiscal_code = receipt.get("fiscal_code") or receipt.get("fiscal_number")
    return (
        receipt.get("status") == "DONE"
        and fiscal_code is not None
        and has_goods(receipt)
    )


def get_receipts_page(token, offset=0, limit=100):
    headers = {
        "accept": "application/json",
        "X-Client-Name": CLIENT_NAME,
        "X-Client-Version": CLIENT_VERSION,
        "Authorization": f"Bearer {token}",
    }

    start, end = get_today_range()

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
        die(f"Не вдалося отримати чеки. HTTP {result['status']}")

    data = result["json"]

    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        for key in ["items", "results", "data", "receipts"]:
            if isinstance(data.get(key), list):
                return data[key]

    return []


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
    """
    Checkbox зазвичай дає суми в копійках як int.
    Якщо раптом прийде float/str у гривнях — теж обробимо.
    """
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


def get_receipt_total(receipt):
    for key in ["total_sum", "sum", "total", "payments_sum"]:
        if key in receipt and receipt[key] is not None:
            return money_to_kop(receipt[key])
    return 0


def get_line_sum(item):
    for key in ["sum", "total_sum", "line_sum"]:
        if key in item and item[key] is not None:
            return money_to_kop(item[key])

    good = item.get("good", {})
    price = good.get("price") or item.get("price")
    qty = item.get("quantity", 1000)

    price_kop = money_to_kop(price)

    if isinstance(qty, int):
        # Checkbox часто дає quantity як 1000 = 1 штука
        return int(round(price_kop * qty / 1000))

    try:
        return int(round(price_kop * float(qty)))
    except Exception:
        return price_kop


def get_good_name(item):
    good = item.get("good", {})
    return good.get("name") or item.get("name") or "Невідомий товар"


def detect_category(name):
    name = name.lower()

    if "вата" in name:
        return "Вата"

    if "попкорн" in name or "popcorn" in name:
        return "Попкорн"

    if "фото" in name:
        return "Фото"

    return "Інше"


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


def get_payment_sum(payment):
    for key in ["value", "sum", "amount", "payment_sum"]:
        if key in payment and payment[key] is not None:
            return money_to_kop(payment[key])
    return 0


def get_payments(receipt):
    payments = receipt.get("payments") or receipt.get("payment") or []

    if isinstance(payments, dict):
        payments = [payments]

    if not isinstance(payments, list):
        payments = []

    return payments


def aggregate_receipts(receipts):
    result = {
        "Готівка": defaultdict(int),
        "Карта": defaultdict(int),
        "Невідомо": defaultdict(int),
    }

    receipt_count = 0
    receipt_total = 0

    for receipt in receipts:
        goods = receipt.get("goods") or receipt.get("items") or []
        payments = get_payments(receipt)

        total = get_receipt_total(receipt)
        receipt_total += total
        receipt_count += 1

        category_sums = defaultdict(int)

        for item in goods:
            name = get_good_name(item)
            category = detect_category(name)
            category_sums[category] += get_line_sum(item)

        if not payments:
            # Якщо в короткому списку чеків нема payments,
            # тоді цей чек піде в "Невідомо".
            for category, amount in category_sums.items():
                result["Невідомо"][category] += amount
            continue

        payment_parts = []

        for payment in payments:
            p_type = detect_payment_type(payment)
            p_sum = get_payment_sum(payment)

            if p_sum > 0:
                payment_parts.append((p_type, p_sum))

        if not payment_parts:
            for category, amount in category_sums.items():
                result["Невідомо"][category] += amount
            continue

        # Якщо чек оплачено одним способом — все просто.
        if len(payment_parts) == 1:
            p_type = payment_parts[0][0]
            for category, amount in category_sums.items():
                result[p_type][category] += amount
            continue

        # Якщо змішана оплата — розкидаємо товари пропорційно оплатам.
        payments_sum = sum(x[1] for x in payment_parts)

        if payments_sum <= 0:
            for category, amount in category_sums.items():
                result["Невідомо"][category] += amount
            continue

        for p_type, p_sum in payment_parts:
            ratio = p_sum / payments_sum
            for category, amount in category_sums.items():
                result[p_type][category] += int(round(amount * ratio))

    return result, receipt_count, receipt_total


def kop_to_uah(value):
    return value / 100


def print_report(aggregated, receipt_count, receipt_total):
    categories = ["Вата", "Попкорн", "Фото", "Інше"]

    print("\n" + "=" * 74)
    print("📊 ЗВІТ ПО ЧЕКАХ ЗА СЬОГОДНІ")
    print("=" * 74)

    header = f"{'Оплата':<12}"
    for category in categories:
        header += f"{category:>14}"
    header += f"{'Всього':>14}"
    print(header)
    print("-" * 74)

    grand_by_category = defaultdict(int)
    grand_total = 0

    for payment_type in ["Готівка", "Карта", "Невідомо"]:
        row_total = 0

        row = f"{payment_type:<12}"

        for category in categories:
            value = aggregated[payment_type][category]
            row_total += value
            grand_by_category[category] += value
            row += f"{kop_to_uah(value):>14.2f}"

        grand_total += row_total
        row += f"{kop_to_uah(row_total):>14.2f}"

        # Не друкуємо "Невідомо", якщо там нулі
        if payment_type == "Невідомо" and row_total == 0:
            continue

        print(row)

    print("-" * 74)

    total_row = f"{'РАЗОМ':<12}"
    for category in categories:
        total_row += f"{kop_to_uah(grand_by_category[category]):>14.2f}"
    total_row += f"{kop_to_uah(grand_total):>14.2f}"
    print(total_row)

    print("=" * 74)
    print(f"🧾 Кількість чеків продажу: {receipt_count}")
    print(f"💰 Сума продажів: {kop_to_uah(receipt_total):.2f} грн")
    print("=" * 74)


def main():
    print("🔐 Авторизація в Checkbox...")
    token = signin_by_pin()
    print("✅ Авторизація успішна")

    start, end = get_today_range()

    print(f"\n📅 Беру тільки сьогодні:")
    print(f"Від: {start.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"До:  {end.strftime('%Y-%m-%d %H:%M:%S')}")

    print("\n📥 Завантажую чеки...")
    raw_receipts = get_all_receipts(token)

    today_short = [
        r for r in raw_receipts
        if is_today_receipt(r, start, end) and is_fiscal_sale(r)
    ]

    print(f"✅ Знайдено сьогоднішніх фіскальних чеків: {len(today_short)}")

    # Дотягуємо повну інформацію по кожному чеку,
    # щоб точно мати payments.
    today_full = []

    for r in today_short:
        receipt_id = r.get("id") or r.get("receipt_id") or r.get("uuid")

        if not receipt_id:
            today_full.append(r)
            continue

        full = get_full_receipt(token, receipt_id)
        today_full.append(full or r)

    aggregated, receipt_count, receipt_total = aggregate_receipts(today_full)
    print_report(aggregated, receipt_count, receipt_total)


if __name__ == "__main__":
    main()