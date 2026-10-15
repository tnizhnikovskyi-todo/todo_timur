// Окно «Розбір кодів» (W-12, A3): правила «маска → уровни» склада, сводка «з N місць розібрано M» (пересчитывается по черновым правилам до «Показати»),
// нераспознанные коды с примерами и подсказка маски по выбранным образцам. Сама логика — core/parse.js; правила применяет model.ops.parse
// («Показати» → изменение, «Зберегти» → в проект; Ctrl+Z отменяет).
import { esc } from "./util.js";

const MAX_BAD = 120;

export function closeParse() { document.getElementById("parse-dlg")?.remove(); }

export function openParse({ model, i18n }) {
  closeParse();
  const t = (k, p) => i18n.t(k, p), T = (k, p) => esc(i18n.t(k, p)), ro = model.readonly;
  const st = { rules: model.parse.rules(), pick: new Set(), msg: "" };
  const dlg = document.createElement("div"); dlg.className = "o_modal_bg"; dlg.id = "parse-dlg";
  dlg.innerHTML = `<div class="o_modal o_modal_wide" role="dialog" aria-modal="true" aria-labelledby="parse-h"><header><h3 id="parse-h">${T("parse.title")}</h3><button class="x" data-close aria-label="${T("common.close")}">×</button></header>
    <div class="body" data-body></div>
    <footer><span class="mut" data-pst style="font-size:13px"></span><span class="sp"></span>
      <button class="btn btn-secondary" data-pdisc>${T("parse.discard")}</button><button class="btn btn-secondary" data-pshow>${T("parse.show")}</button><button class="btn btn-primary" data-psave>${T("parse.saveBtn")}</button></footer></div>`;
  document.body.append(dlg);
  const body = dlg.querySelector("[data-body]");
  const close = () => { dlg.remove(); off(); document.removeEventListener("keydown", onKey, true); };
  const onKey = (e) => { if (e.key === "Escape") { e.stopPropagation(); close(); } };
  document.addEventListener("keydown", onKey, true);
  const off = model.on((ev) => { if (ev.type === "rebuild" || ev.type === "warehouse") foot(); });
  dlg.addEventListener("mousedown", (e) => { if (e.target === dlg) close(); });
  dlg.querySelector("[data-close]").onclick = close;

  const draft = () => ({ rules: st.rules.map((r) => ({ ...r })) });
  const nextId = () => `r${1 + Math.max(0, ...st.rules.map((r) => +String(r.id).replace(/\D/g, "") || 0))}`;
  const tpOpts = (cur) => `<option value="">${T("parse.tpAuto")}</option>${model.types.list().map((x) => `<option value="${esc(x.id)}"${x.id === cur ? " selected" : ""}>${esc(x.id)} · ${esc(i18n.typeName(x))}</option>`).join("")}`;

  // сводка и список нераспознанных зависят только от правил: обновляются при вводе без перерисовки полей
  function live() {
    const s = model.parse.stats(st.rules);
    body.querySelector("#parse-sum").textContent = t("parse.summary", { n: s.total, m: s.parsed });
    body.querySelector("#parse-tray").textContent = t("parse.summaryTray", { k: s.tray.length });
    body.querySelectorAll("[data-hits]").forEach((el) => { const i = +el.dataset.hits, r = st.rules[i], e = s.errs[r.id]; el.textContent = e ? t(`parse.err.${e}`) : t("parse.hits", { n: s.hits[r.id] || 0 }); el.classList.toggle("err", !!e); });
    const trayed = new Set(s.tray), shown = s.bad.slice(0, MAX_BAD);
    body.querySelector("#parse-bad").innerHTML = s.bad.length ? `<div class="sec">${T("parse.bad", { n: s.bad.length })}</div><ul class="plist parse-bad">${shown.map((c) => `<li><label class="tray-row"><input type="checkbox" data-pick="${esc(c)}"${st.pick.has(c) ? " checked" : ""}> <span class="code">${esc(c)}</span> <span class="mut">${T(trayed.has(c) ? "parse.badTray" : "parse.badFloor")}</span></label></li>`).join("")}</ul>${s.bad.length > MAX_BAD ? `<p class="ed-note">${T("parse.more", { n: MAX_BAD, m: s.bad.length })}</p>` : ""}` : `<p class="ed-note" id="parse-ok">${T("parse.allOk")}</p>`;
    body.querySelectorAll("[data-pick]").forEach((c) => c.onchange = () => { if (c.checked) st.pick.add(c.dataset.pick); else st.pick.delete(c.dataset.pick); });
  }
  function foot() {
    const dirty = JSON.stringify(st.rules.map((r) => [r.mask, !!r.re, r.tp || "", !!r.off])) !== JSON.stringify(model.parse.rules().map((r) => [r.mask, !!r.re, r.tp || "", !!r.off]));
    const k = model.pendFor("WH").some((p) => p.label && p.label.k === "op.parse");
    dlg.querySelector("[data-pst]").textContent = st.msg || (dirty ? t("parse.unsaved") : k ? t("parse.unsaved") : "");
    dlg.querySelector("[data-pshow]").disabled = !dirty || ro; dlg.querySelector("[data-pdisc]").disabled = !dirty;
    dlg.querySelector("[data-psave]").disabled = ro || (!dirty && !k); dlg.querySelector("[data-psave]").hidden = ro;
  }
  function render() {
    body.innerHTML = `<div class="parse-top"><b id="parse-sum"></b> · <span id="parse-tray" class="mut"></span></div>
      <div class="sec">${T("parse.rules")}</div>
      <table class="o_tbl parse-rules"><thead><tr><th>#</th><th>${T("parse.mask")}</th><th>${T("parse.regex")}</th><th>${T("parse.tp")}</th><th>${T("parse.off")}</th><th></th><th></th></tr></thead><tbody>
      ${st.rules.map((r, i) => `<tr data-row="${i}"><td>${i + 1}</td><td><input data-mask="${i}" value="${esc(r.mask)}" spellcheck="false" aria-label="${T("parse.mask")} ${i + 1}"${ro ? " readonly" : ""}></td>
        <td><input type="checkbox" data-re="${i}"${r.re ? " checked" : ""}${ro ? " disabled" : ""}></td><td><select data-tp="${i}"${ro ? " disabled" : ""}>${tpOpts(r.tp)}</select></td>
        <td><input type="checkbox" data-off="${i}"${r.off ? " checked" : ""}${ro ? " disabled" : ""}></td>
        <td class="mut" data-hits="${i}"></td>
        <td class="nw"><button class="x" data-up="${i}" title="${T("parse.up")}" aria-label="${T("parse.up")} ${i + 1}"${i === 0 || ro ? " disabled" : ""}>↑</button><button class="x" data-down="${i}" title="${T("parse.down")}" aria-label="${T("parse.down")} ${i + 1}"${i === st.rules.length - 1 || ro ? " disabled" : ""}>↓</button><button class="x" data-del="${i}" title="${T("parse.del")}" aria-label="${T("parse.del")} ${i + 1}"${ro ? " disabled" : ""}>×</button></td></tr>`).join("")}</tbody></table>
      <p class="ed-note">${T("parse.help")}</p>
      <div class="acts"><button class="btn btn-secondary" data-add${ro ? " disabled" : ""}>${T("parse.add")}</button><button class="btn btn-secondary" data-suggest${ro ? " disabled" : ""}>${T("parse.suggest")}</button><button class="btn btn-link" data-defaults${ro ? " disabled" : ""}>${T("parse.defaults")}</button></div>
      <p class="ed-note">${T("parse.suggestNote")}</p><div id="parse-bad"></div>`;
    live(); foot();
    const row = (el, k) => st.rules[+el.dataset[k]];
    body.querySelectorAll("[data-mask]").forEach((el) => el.oninput = () => { row(el, "mask").mask = el.value; st.msg = ""; live(); foot(); });
    body.querySelectorAll("[data-re]").forEach((el) => el.onchange = () => { row(el, "re").re = el.checked; st.msg = ""; live(); foot(); });
    body.querySelectorAll("[data-tp]").forEach((el) => el.onchange = () => { row(el, "tp").tp = el.value; st.msg = ""; foot(); });
    body.querySelectorAll("[data-off]").forEach((el) => el.onchange = () => { row(el, "off").off = el.checked; st.msg = ""; live(); foot(); });
    const move = (i, d) => { const r = st.rules.splice(i, 1)[0]; st.rules.splice(i + d, 0, r); st.msg = ""; render(); };
    body.querySelectorAll("[data-up]").forEach((el) => el.onclick = () => move(+el.dataset.up, -1));
    body.querySelectorAll("[data-down]").forEach((el) => el.onclick = () => move(+el.dataset.down, 1));
    body.querySelectorAll("[data-del]").forEach((el) => el.onclick = () => { st.rules.splice(+el.dataset.del, 1); st.msg = ""; render(); });
    body.querySelector("[data-add]").onclick = () => { st.rules.push({ id: nextId(), mask: "", re: false, tp: "", off: false }); st.msg = ""; render(); body.querySelector(`[data-mask="${st.rules.length - 1}"]`)?.focus(); };
    body.querySelector("[data-defaults]").onclick = () => { st.rules = model.parse.defaults(); st.msg = ""; render(); };
    body.querySelector("[data-suggest]").onclick = () => {
      const bad = model.parse.stats(st.rules).bad, picked = [...st.pick].filter((c) => bad.includes(c)), samples = picked.length ? picked : bad.slice(0, 3);
      if (!samples.length) { st.msg = t("parse.suggestNone"); foot(); return; }
      const r = model.parse.suggest(samples);
      if (r.err) { st.msg = t(r.err === "shape" ? "parse.suggestShape" : "parse.suggestNone"); foot(); return; }
      st.rules.push({ id: nextId(), mask: r.mask, re: false, tp: r.mask.includes("{префікс}") || r.shape === "floor" ? "" : "FUR", off: false });
      st.pick.clear(); st.msg = t("parse.suggested", { mask: r.mask }); render();
    };
  }
  dlg.querySelector("[data-pshow]").onclick = () => { if (model.ops.parse(draft())) { st.rules = model.parse.rules(); st.msg = ""; } render(); };
  dlg.querySelector("[data-pdisc]").onclick = () => { st.rules = model.parse.rules(); st.pick.clear(); st.msg = ""; render(); };
  dlg.querySelector("[data-psave]").onclick = () => {
    if (JSON.stringify(draft().rules.map((r) => [r.mask, !!r.re, r.tp || "", !!r.off])) !== JSON.stringify(model.parse.rules().map((r) => [r.mask, !!r.re, r.tp || "", !!r.off]))) model.ops.parse(draft());
    st.rules = model.parse.rules(); st.msg = ""; render();
    model.save("WH").then((r) => { if (r && r !== "fail" && r !== "stale") { st.msg = t("parse.saved"); foot(); } });
  };
  render();
  return { close };
}
