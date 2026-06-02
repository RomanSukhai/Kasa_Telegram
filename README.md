# privat_kasa_bot

Автоматичний щоденний звіт по ПРРО Checkbox у Telegram.

Скрипт підключається до Checkbox API, отримує фіскальні чеки за поточний день, рахує продажі по категоріях товарів і формах оплати, після чого надсилає підсумок у Telegram.

## Що робить проєкт

Скрипт автоматично:

1. авторизується в Checkbox через `CHECKBOX_LICENSE_KEY` і `CHECKBOX_PIN`;
2. отримує список чеків через Checkbox API;
3. фільтрує тільки фіскальні продажі за сьогодні;
4. розкладає товари по категоріях:
   - Вата;
   - Попкорн;
   - Фото;
   - Інше;
5. рахує продажі окремо по формах оплати:
   - Готівка;
   - Карта;
6. формує текстовий звіт;
7. надсилає звіт у Telegram;
8. може запускатися автоматично щодня через GitHub Actions.

## Приклад звіту

```text
📊 ЗВІТ ПО КАСІ ЗА 02.06.2026

Оплата          Вата     Попкорн      Фото    Всього
----------------------------------------------------
Готівка        70.00       70.00    150.00    290.00
Карта          70.00      400.00    150.00    620.00
----------------------------------------------------
РАЗОМ         140.00      470.00    300.00    910.00

🧾 Чеків продажу: 8
💰 Всього: 910.00 грн
```

## Структура проєкту

```text
privat_kasa_bot/
├── main2.py
├── requirements.txt
├── .gitignore
├── README.md
└── .github/
    └── workflows/
        └── daily_kasa_report.yml
```

## Встановлення локально

```bash
python3 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt
```

Файл `requirements.txt`:

```txt
requests
```

## Змінні середовища

Для роботи скрипта потрібні секретні змінні:

```env
CHECKBOX_LICENSE_KEY=ключ_ліцензії_Checkbox
CHECKBOX_PIN=pin_касира
TELEGRAM_BOT_TOKEN=токен_telegram_бота
TELEGRAM_CHAT_ID=id_telegram_чату
```

Локально їх можна задати так:

```bash
export CHECKBOX_LICENSE_KEY="твій_checkbox_license_key"
export CHECKBOX_PIN="твій_pin"
export TELEGRAM_BOT_TOKEN="твій_telegram_bot_token"
export TELEGRAM_CHAT_ID="telegram_chat_id"
```

## Запуск локально

```bash
python main2.py
```

Після запуску скрипт:

1. авторизується в Checkbox;
2. завантажить чеки;
3. сформує звіт;
4. виведе його в консоль;
5. надішле його в Telegram.

## Як отримати TELEGRAM_CHAT_ID

1. Створи Telegram-бота через [@BotFather](https://t.me/BotFather).
2. Отримай токен бота.
3. Людина, якій треба надсилати звіт, має відкрити бота і натиснути `/start`.
4. Виконай команду:

```bash
curl "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/getUpdates"
```

5. У відповіді знайди:

```json
"chat": {
  "id": 123456789
}
```

Це число і є `TELEGRAM_CHAT_ID`.

## Автоматичний запуск через GitHub Actions

Проєкт може запускатися автоматично через GitHub Actions.

Файл workflow:

```text
.github/workflows/daily_kasa_report.yml
```

Приклад налаштування:

```yaml
name: Daily Kasa Telegram Report

on:
  schedule:
    # 21:30 по Україні влітку = 18:30 UTC
    - cron: "30 18 * * *"

  workflow_dispatch:

env:
  FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: true

jobs:
  send-report:
    runs-on: ubuntu-latest

    steps:
      - name: Download repository
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install dependencies
        run: |
          pip install -r requirements.txt

      - name: Run Checkbox report
        env:
          CHECKBOX_LICENSE_KEY: ${{ secrets.CHECKBOX_LICENSE_KEY }}
          CHECKBOX_PIN: ${{ secrets.CHECKBOX_PIN }}
          TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
          TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}
          CHECKBOX_CLIENT_NAME: roman-kasa-report
          CHECKBOX_CLIENT_VERSION: 1.0.0
        run: |
          python main2.py
```

## GitHub Secrets

У репозиторії потрібно додати секрети:

```text
Settings → Secrets and variables → Actions → New repository secret
```

Додати:

```env
CHECKBOX_LICENSE_KEY
CHECKBOX_PIN
TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID
```

Значення мають бути реальними, але вони не зберігаються у коді.

## Ручний запуск на GitHub

Щоб перевірити роботу без очікування cron:

1. відкрити репозиторій на GitHub;
2. перейти у вкладку `Actions`;
3. вибрати `Daily Kasa Telegram Report`;
4. натиснути `Run workflow`.

Якщо все налаштовано правильно, звіт прийде в Telegram.

## Налаштування часу запуску

GitHub Actions використовує UTC.

Приклади для України влітку, коли Київ має UTC+3:

```yaml
# 20:00 по Києву
- cron: "0 17 * * *"

# 21:00 по Києву
- cron: "0 18 * * *"

# 21:30 по Києву
- cron: "30 18 * * *"

# 22:00 по Києву
- cron: "0 19 * * *"

# 23:00 по Києву
- cron: "0 20 * * *"
```

Взимку Україна має UTC+2, тому час у cron треба буде змістити на одну годину.

## Безпека

У коді не повинно бути:

- Checkbox license key;
- PIN касира;
- Telegram bot token;
- Telegram chat id, якщо не хочеш світити отримувача.

Секрети треба зберігати тільки в:

- локальних змінних середовища;
- GitHub Actions Secrets.

Файл `.env`, віртуальне середовище `.venv/` і службові кеші мають бути додані в `.gitignore`.

## `.gitignore`

Рекомендований `.gitignore`:

```gitignore
venv/
.venv/
env/
ENV/

__pycache__/
*.pyc
*.pyo

.env
*.env

.DS_Store
.idea/
.vscode/

*.log
```

## Статус

Проєкт працює як автоматичний щоденний Telegram-звіт по Checkbox-касі.