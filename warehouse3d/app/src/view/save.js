// Сохранение файла пользователю (W-23). В артефакте claude.ai скачивание через ссылку не работает: файл отдаётся через возможность `downloads`
// (пользователь видит подтверждение и может отказаться). Вне артефакта или если возможности нет — прежний способ: Blob + ссылка.
// Возвращает "saved" (отдан) или "declined" (пользователь отказался — не ошибка). Остальные сбои — исключение: вызывающий показывает уведомление.
const LIFECYCLE = new Set(["unavailable", "not_granted", "capability_disabled", "capability_removed"]);

async function capability() {
  const c = globalThis.window?.claude;
  if (typeof c?.use !== "function") return null;
  try { return (await c.use("downloads")) || null; } catch { return null; }
}

function viaLink(name, data, mime) {
  const url = URL.createObjectURL(new Blob([data], { type: mime })), a = document.createElement("a");
  a.href = url; a.download = name; document.body.append(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 4000);
}

export async function saveFile(name, data, mime) {
  const d = await capability();
  if (d && typeof d.save === "function") {
    const blob = new Blob([data], { type: mime });
    try { await d.save({ filename: name, data: blob }); return "saved"; }
    catch (e) {
      const code = e?.code;
      if (code === "declined") return "declined";
      if (code === "rejected_extension" && !/\.txt$/i.test(name)) {   // формат вне списка платформы (например .zpl): текстовый файл с суффиксом .txt
        try { await d.save({ filename: `${name}.txt`, data: blob }); return "saved"; }
        catch (e2) { if (e2?.code === "declined") return "declined"; throw e2; }
      }
      if (!LIFECYCLE.has(code)) throw e instanceof Error ? e : Object.assign(new Error(e?.message || String(code || e)), { code });
    }
  }
  viaLink(name, data, mime);
  return "saved";
}
