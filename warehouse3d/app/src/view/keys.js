// Горячие клавиши режима редактирования: Ctrl/⌘ + C, V, D, Z (Shift+Z или Y — вернуть); R — повернуть ряд; Esc — снять выделение.
// ev.code — работает и в украинской раскладке.
export function bindKeys({ model, isActive, doc = document }) {
  const onKey = (ev) => {
    const ui = model.ui;
    if (!ui.edit || !isActive() || doc.getElementById("types-dlg") || /INPUT|SELECT|TEXTAREA/.test(doc.activeElement?.tagName || "") || doc.activeElement?.isContentEditable) return;
    const c = ev.code;
    if ((ev.ctrlKey || ev.metaKey) && !ev.altKey) {
      if (c === "KeyZ" && !ev.shiftKey) { ev.preventDefault(); model.undo(true); }
      else if ((c === "KeyZ" && ev.shiftKey) || c === "KeyY") { ev.preventDefault(); model.redo(); }
      else if (c === "KeyC") { if (String(globalThis.getSelection?.() || "").trim()) return; ev.preventDefault(); model.copy(); }
      else if (c === "KeyV") { ev.preventDefault(); model.paste(); }
      else if (c === "KeyD") { ev.preventDefault(); const S = model.selIds(); if (S.length) model.ops.dup(S); }
      return;
    }
    if (ev.altKey || ev.ctrlKey || ev.metaKey) return;
    if (ev.key === "Escape") { if (model.escape()) ev.preventDefault(); return; }
    if (c === "KeyR") {
      const S = model.selIds(), rs = (S.length ? S : [ui.esel]).map((id) => id && model.rackOf(id)?.id).filter(Boolean);
      if (rs.length && !model.readonly) { ev.preventDefault(); model.ops.rotate(rs); }
    }
  };
  doc.addEventListener("keydown", onKey);
  return () => doc.removeEventListener("keydown", onKey);
}
