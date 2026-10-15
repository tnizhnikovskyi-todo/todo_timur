// Уведомления в углу экрана. Ядро шлёт событие { kind, key, params, sub }, текст собирает i18n.
import { esc } from "./util.js";

export function createNotifier({ i18n, root = document.body }) {
  const box = document.createElement("div");
  box.id = "o_notifs"; box.setAttribute("aria-live", "polite"); root.append(box);

  // act — { label, run }: кнопка в уведомлении («Поставити все одно»); такое уведомление не скрывается по таймеру и закрывается после нажатия
  function show(text, kind = "ok", sub = "", act = null) {
    const n = document.createElement("div"); n.className = `o_notif ${kind}`; n.setAttribute("role", "status");
    n.innerHTML = `<span class="ic" aria-hidden="true">${kind === "ok" ? "✓" : kind === "bad" ? "!" : "i"}</span><div><b>${esc(text)}</b>${sub ? `<span>${esc(sub)}</span>` : ""}${act ? `<button class="btn btn-secondary act" data-force>${esc(act.label)}</button>` : ""}</div><button class="x" aria-label="${esc(i18n.t("common.close"))}">×</button>`;
    n.querySelector(".x").onclick = () => n.remove();
    if (act) { n.dataset.force = "1"; n.querySelector("[data-force]").onclick = () => { n.remove(); act.run(); }; }
    box.append(n);
    // уведомление с действием не гаснет само: его закрывают нажатием, крестиком или следующей правкой (dropForce)
    if (!act) setTimeout(() => { n.classList.add("out"); setTimeout(() => n.remove(), 300); }, kind === "bad" ? 6000 : 3200);
    return n;
  }
  // событие ядра { type: "notify", kind, key, params, sub: { key, params } | null, force }; force — есть что повторить без проверок (onForce)
  const fromEvent = (ev, onForce = null) => {
    box.querySelectorAll("[data-force]").length && dropForce();
    return show(i18n.t(ev.key, ev.params), ev.kind, ev.sub ? i18n.t(ev.sub.key, ev.sub.params) : "", ev.force && onForce ? { label: i18n.t("n.chkForce"), run: onForce } : null);
  };
  // следующая правка делает прежнее «Поставити все одно» недействительным
  const dropForce = () => box.querySelectorAll(".o_notif[data-force]").forEach((n) => n.remove());
  return { show, fromEvent, dropForce, box };
}
