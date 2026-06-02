# privat_kasa_bot

Автоматизація для Приват24 Бізнес / ПРРО «Каса»:

1. відкриває браузер;
2. ти сам входиш через QR-код;
3. ти відкриваєш сторінку операцій за потрібну зміну/дату;
4. бот скачує PDF чеків через меню `Показати більше дій -> Завантажити PDF`;
5. окремий PDF-парсер читає папку `downloads/`;
6. створюється Excel-звіт у `output/`.

## Встановлення на Ubuntu

```bash
sudo apt update
sudo apt install -y python3-venv python3-pip poppler-utils tesseract-ocr tesseract-ocr-ukr tesseract-ocr-eng

python3 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt
playwright install chromium
```

## Запуск повного сценарію

```bash
python main.py
```

## Тільки скачати PDF

```bash
python download_pdfs.py
```

## Тільки розпарсити вже скачані PDF

Поклади PDF у папку `downloads/`, потім:

```bash
python parse_receipts.py
```

Результат буде у папці `output/`.

## Безпека

Скрипт не зберігає логін, пароль, cookies чи токени.
Ти входиш у Приват24 сам через QR-код, після чого скрипт працює тільки з уже відкритою сторінкою.
