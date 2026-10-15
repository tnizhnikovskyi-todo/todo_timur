// Уведомления в углу экрана. Ядро шлёт событие { kind, key, params, sub }, текст собирает i18n.
import { esc } from "./util.js";

export function createNotifier({ i18n, root = document.body }) {
  const box = document.createElement("div");
  box.id = "o_notifs"; box.setAttribute("aria-live", "polite"); root.append(box);

  function show(text, kind = "ok", sub = "") {
    const n = document.createElement("div"); n.className = `o_notif ${kind}`; n.setAttribute("role", "status");
    n.innerHTML = `<span class="ic" aria-hidden="true">${kind === "ok" ? "✓" : kind === "bad" ? "!" : "i"}</span><div><b>${esc(text)}</b>${sub ? `<span>${esc(sub)}</span>` : ""}</div><button class="x" aria-label="${esc(i18n.t("common.close"))}">×</button>`;
    n.querySelector(".x").onclick = () => n.remove();
    box.append(n);
    setTimeout(() => { n.classList.add("out"); setTimeout(() => n.remove(), 300); }, kind === "bad" ? 6000 : 3200);
    return n;
  }
  // событие ядра { type: "notify", kind, key, params, sub: { key, params } | null }
  const fromEvent = (ev) => show(i18n.t(ev.key, ev.params), ev.kind, ev.sub ? i18n.t(ev.sub.key, ev.sub.params) : "");
  return { show, fromEvent, box };
}
