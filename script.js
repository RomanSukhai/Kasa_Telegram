async function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

function visibleTextNodesInSameRow(button) {
  const btnRect = button.getBoundingClientRect();
  const yCenter = btnRect.top + btnRect.height / 2;

  const candidates = Array.from(document.querySelectorAll("td, div, span, a"))
    .map(el => {
      const r = el.getBoundingClientRect();
      const text = (el.innerText || el.textContent || "").trim();
      return { el, r, text };
    })
    .filter(x => {
      if (!x.text) return false;
      if (x.r.width <= 0 || x.r.height <= 0) return false;

      const sameY = yCenter >= x.r.top - 3 && yCenter <= x.r.bottom + 3;
      const leftOfButton = x.r.left < btnRect.left;

      return sameY && leftOfButton;
    })
    .sort((a, b) => a.r.left - b.r.left);

  const texts = [];

  for (const x of candidates) {
    const t = x.text.replace(/\s+/g, " ").trim();

    if (!t || t.length > 80) continue;
    if (texts.includes(t)) continue;

    texts.push(t);
  }

  return texts.join(" | ");
}

async function downloadOnlySalesByRowGeometry() {
  const buttons = Array.from(
    document.querySelectorAll('button[aria-label="Показати більше дій"]')
  ).filter(btn => {
    const rect = btn.getBoundingClientRect();
    return rect.width > 0 && rect.height > 0;
  });

  console.log("Знайдено кнопок більше дій:", buttons.length);

  let downloaded = 0;
  let skipped = 0;

  for (let i = 0; i < buttons.length; i++) {
    const rowText = visibleTextNodesInSameRow(buttons[i]);

    console.log(`\nКнопка ${i + 1}/${buttons.length}`);
    console.log("Рядок:", rowText || "[не вдалося прочитати рядок]");

    const isSale = rowText.includes("Продаж");
    const hasAmount = /\b\d+[.,]\d{2}\b/.test(rowText);
    const isService =
      rowText.includes("Z - звіт") ||
      rowText.includes("Закриття зміни") ||
      rowText.includes("Відкриття зміни");

    if (!isSale || !hasAmount || isService) {
      console.log("  - Пропускаю: не продаж або службовий рядок");
      skipped++;
      continue;
    }

    buttons[i].scrollIntoView({ block: "center" });
    await sleep(500);

    buttons[i].click();
    await sleep(700);

    const downloadItem = document.querySelector('li[aria-label="Завантажити PDF"]');

    if (!downloadItem) {
      console.warn("  - Немає пункту Завантажити PDF, пропускаю");
      document.body.click();
      await sleep(300);
      skipped++;
      continue;
    }

    console.log("  + Клікаю Завантажити PDF");
    downloadItem.click();
    downloaded++;

    await sleep(6000);
  }

  console.log("\nГотово.");
  console.log("Скачано продажів:", downloaded);
  console.log("Пропущено:", skipped);
}

downloadOnlySalesByRowGeometry();