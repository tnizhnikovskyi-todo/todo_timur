/** @odoo-module */
// Діалоги редактора (власні, без alert/confirm/prompt — AC-65): підтвердження, нова площадка, історія версій, перевірка на сервері,
// конфлікт запису. Публікація — майстер Odoo (OdooStore.publishPreview); картки варіантів/типів — штатні форми Odoo в діалозі.
import { canManage } from "./roles";
import { CHECKS } from "./data";
import { E, S } from "./state";
import { $, K, fmtDate, h, ic, toast } from "./util";

export function openDialog(o) {
    const dlg = h("dialog", { class: o.cls || "" });
    const close = (r) => {
        dlg.returnValue = r || "";
        dlg.close();
    };
    dlg.append(
        ...K(
            h("div", { class: "dh" }, h("h2", null, o.title), h("button", { class: "xbtn", type: "button", "aria-label": "Закрити", onclick: () => close("") }, ic("x"))),
            h("div", { class: "db" }, o.body),
            o.actions && o.actions.length
                ? h(
                      "div",
                      { class: "df" },
                      o.actions.map((a) =>
                          h(
                              "button",
                              {
                                  class: "fbtn " + (a.cls || ""),
                                  type: "button",
                                  disabled: a.disabled,
                                  id: a.id,
                                  onclick: async () => {
                                      const r = a.onClick ? await a.onClick(dlg) : undefined;
                                      if (r !== false) {
                                          close(a.value || "ok");
                                      }
                                  },
                              },
                              a.label
                          )
                      )
                  )
                : null
        )
    );
    dlg.addEventListener("close", () => {
        if (o.onClose) {
            o.onClose(dlg.returnValue);
        }
        dlg.remove();
    });
    dlg.addEventListener("click", (e) => {
        if (e.target === dlg && o.light) {
            close("");
        }
    });
    ($("#app") || document.body).append(dlg);
    dlg.showModal();
    dlg.close2 = close;
    return dlg;
}

export function confirmBox(o) {
    return new Promise((res) => {
        let done = false;
        openDialog({
            title: o.title,
            cls: "narrow",
            body: h("p", { style: { margin: 0 } }, o.text),
            actions: [
                { label: o.cancel || "Скасувати", value: "no" },
                { label: o.ok || "Так", cls: o.danger ? "danger" : "primary", value: "yes", id: "dlgYes", onClick: () => { done = true; } },
            ],
            onClose: () => res(done),
        });
    });
}

/* ===== нова площадка (CD-22, CD-24; API-02) ===== */
export function openNewSite() {
    const name = h("input", { type: "text", value: "Нова площадка", "aria-label": "Назва", id: "newSiteName" });
    const code = h("input", { type: "text", value: "", maxlength: 16, "aria-label": "Код", id: "newSiteCode", placeholder: "напр. MAIN" });
    code.addEventListener("input", () => { code.value = code.value.toUpperCase().replace(/[^A-Z0-9]/g, ""); });
    const dim = (v, label, id) => h("input", { type: "number", value: v, min: 5, step: 1, "aria-label": label, id });
    const l = dim(60, "Довжина", "newSiteL");
    const w = dim(30, "Ширина", "newSiteW");
    const hh = dim(8, "Висота", "newSiteH");
    const lab = (t, el) => h("label", { class: "fld" }, h("span", null, t), el);
    openDialog({
        title: "Нова площадка",
        cls: "narrow",
        body: h(
            "div",
            { class: "fcol" },
            lab("Назва", name),
            lab("Код (великі латинські літери й цифри, до 16)", code),
            h("div", { class: "grid3" }, lab("Довжина, м", l), lab("Ширина, м", w), lab("Висота, м", hh)),
            h("div", { class: "small muted" }, "Створюється порожня площадка: п’ять базових шарів і каталог типових варіантів.")
        ),
        actions: [
            { label: "Скасувати" },
            {
                label: "Створити",
                cls: "primary",
                id: "dlgCreateSite",
                onClick: async () => {
                    if (!name.value.trim() || !code.value) {
                        toast("Вкажіть назву й код площадки.", "warn");
                        return false;
                    }
                    const ok = await E.createSite({ name: name.value.trim(), code: code.value, building: { l: +l.value, w: +w.value, h: +hh.value } });
                    return ok ? undefined : false;
                },
            },
        ],
    });
}

/* ===== історія версій (CD-21; API-08) ===== */
export function openHistory() {
    const body = h("div");
    const dlg = openDialog({ title: "Історія версій", cls: "narrow", body, actions: [{ label: "Закрити" }] });
    const render = () => {
        const vs = [...S.versions].sort((a, b) => b.n - a.n);
        const act = S.site.active_version ? S.site.active_version.n : null;
        body.replaceChildren(
            ...K(
                h("div", { class: "small muted", style: { marginBottom: "6px" } }, "Повернення змінює чернетку; записи Odoo (локації, обладнання) не змінюються, доки ви не опублікуєте нову версію."),
                vs.length
                    ? vs.map((v) =>
                          h(
                              "div",
                              { class: "ver" },
                              h("div", { class: "vn" }, "v" + v.n),
                              h(
                                  "div",
                                  { class: "vi" },
                                  h("div", null, fmtDate(v.published_at) + " · " + v.by, v.n === act ? h("span", { class: "fbadge ok", style: { marginLeft: "8px" } }, "активна") : null),
                                  h("div", { class: "small" }, v.note || "без нотатки"),
                                  v.counts ? h("div", { class: "small muted mono" }, `${v.counts.layers} шарів · ${v.counts.slots} місць · ${v.counts.cells} комірок · ${v.counts.placements} обл.`) : null
                              ),
                              h(
                                  "button",
                                  {
                                      class: "fbtn sm",
                                      type: "button",
                                      "data-version": v.id,
                                      disabled: !canManage(),
                                      title: canManage() ? "" : "Повертає Менеджер у режимі редагування",
                                      onclick: async () => {
                                          const ok = await confirmBox({ title: `Повернути чернетку до v${v.n}?`, text: "Поточна чернетка буде замінена знімком версії. Незбережені зміни пропадуть.", ok: "Повернути", danger: true });
                                          if (!ok) {
                                              return;
                                          }
                                          await E.restoreVersion(v.id, v.n);
                                          dlg.close2("");
                                      },
                                  },
                                  "Повернути чернетку"
                              )
                          )
                      )
                    : h("div", { class: "empty" }, "Версій ще немає. Натисніть «Опублікувати».")
            )
        );
    };
    render();
}

/* ===== перевірка на сервері (API-05) ===== */
export function openServerIssues(res) {
    const issues = res.issues || [];
    const name = (c) => (CHECKS.find((x) => x.id === c) || {}).name || c;
    openDialog({
        title: "Перевірка на сервері",
        cls: "narrow",
        body: h(
            "div",
            { class: "fcol" },
            h("div", { class: "frow" }, res.summary.block ? h("span", { class: "fbadge b" }, res.summary.block + " заборон") : null, res.summary.warn ? h("span", { class: "fbadge w" }, res.summary.warn + " попер.") : null, !issues.length ? h("span", { class: "fbadge ok" }, "усе гаразд") : null),
            h(
                "div",
                { class: "issues", id: "serverIssues" },
                issues.map((i) => h("div", { class: "issue " + i.severity }, h("div", { class: "im" }, i.message, h("div", { class: "io" }, (i.severity === "block" ? "ЗАБОРОНА" : "ПОПЕРЕДЖЕННЯ") + " · " + name(i.check)))))
            )
        ),
        actions: [{ label: "Закрити" }],
    });
}

/* ===== конфлікт запису (R-21): «залишити моє» / «взяти серверне» ===== */
export function askConflict() {
    return new Promise((res) => {
        let choice = "theirs";
        openDialog({
            title: "Запис змінив інший користувач",
            cls: "narrow",
            body: h("p", { style: { margin: 0 } }, "Об’єкт на сервері новіший за ваш. Залишити вашу версію чи взяти серверну (ваші зміни цього об’єкта буде втрачено)?"),
            actions: [
                { label: "Взяти серверне", value: "theirs", id: "dlgTheirs" },
                { label: "Залишити моє", cls: "primary", value: "mine", id: "dlgMine", onClick: () => { choice = "mine"; } },
            ],
            onClose: () => res(choice),
        });
    });
}

Object.assign(E, { openDialog, confirmBox, openNewSite, openHistory, openServerIssues, askConflict });
