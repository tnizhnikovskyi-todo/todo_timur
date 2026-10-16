// Тур для новичков (W-20, K3): шаги данными, без DOM. sel — элемент, который подсвечивается; fb — запасной, если sel сейчас не виден
// (кнопки режима «Редагувати» и «План змін» видны не всегда). Тексты — i18n/tour.js: tour.<id>.t (заголовок) и tour.<id>.d (подсказка).
export const TOUR_STEPS = [
  { id: "mode", sel: "#seg-mode" },
  { id: "levels", sel: "#lvlbar" },
  { id: "select", sel: "#vp" },
  { id: "minimap", sel: "#minimap" },
  { id: "goto", sel: "#go-box" },
  { id: "menu", sel: "#menu-btn" }, // только на узком экране: там остальные кнопки спрятаны в меню
  { id: "edit", sel: "#ed-tg" },
  { id: "catalog", sel: "#ed-types", fb: "#ed-tg" },
  { id: "checks", sel: "#pr-btn" },
  { id: "plan", sel: "#plan-btn", fb: "#file-btn" },
  { id: "help", sel: "#help-btn" },
];
export const TOUR_KEY = "wh-app-tour"; // отметка «тур пройден» (done) или «пропущен» (skipped) — только в этом браузере

// шаги, чьи элементы видны сейчас: isVisible(селектор) → boolean; у каждого — выбранный селектор
export function pickSteps(isVisible, steps = TOUR_STEPS) {
  const out = [];
  for (const s of steps) { const sel = isVisible(s.sel) ? s.sel : s.fb && isVisible(s.fb) ? s.fb : null; if (sel) out.push({ id: s.id, sel }); }
  return out;
}
