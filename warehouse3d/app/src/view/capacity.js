// Ёмкость и атрибуты в боковой панели (W-14, D-15): категория хранения, габариты и вес места, флаги, стратегия списания, min / max, функция и атрибуты зоны, сводка ёмкости.
// Формы — те же «Показати / Зберегти» с undo, что и остальные (панель вызывает model.ops.<op> по data-op: capacity, catAssign, flags, removal, zoneFn, minmax).
import { ZONE_ATTRS, ZONE_FUNCS, NONE } from "../core/attr.js";
import { esc, zoneHint } from "./util.js";

export function createCapacity({ model, i18n, btns, fv }) {
  const t = (k, p) => i18n.t(k, p), T = (k, p) => esc(i18n.t(k, p));
  const yn = (v) => t(v ? "cap.yes" : "cap.no");
  const sec = (key) => `<div class="sec">${T(key)}</div>`;
  const opt = (v, label, sel) => `<option value="${esc(v)}"${String(v) === String(sel) ? " selected" : ""}>${esc(label)}</option>`;
  const catLine = (c, n) => {
    if (!c.cat) return t(c.project ? "cap.catEffNone" : "cap.catEffNoneOdoo");
    const from = c.from && c.from !== n.id && model.tree.nodes.get(c.from) ? t("cap.catFrom", { name: i18n.node(model.tree.nodes.get(c.from)) }) : c.project ? "" : t("cap.catFromOdoo");
    return `${c.cat.name}${from}`;
  };

  // ---------- сводка ёмкости (E11): зона или склад
  function summaryHtml(n) {
    const s = model.cap.summary(n.id); if (!s || !s.places) return "";
    const row = (k, v, extra = "") => `<tr><td class="first">${T(`cap.sum.${k}`)}</td><td class="n" data-sum="${k}">${v}${extra}</td></tr>`;
    return `${sec("cap.sumTitle")}<table class="o_list cap-sum"><tbody>${row("places", i18n.int(s.places))}${row("pallets", i18n.int(s.pallets))}${row("area", i18n.m(s.area))}${row("volume", i18n.m(s.volume))}
      ${row("occupied", i18n.int(s.occupied))}${row("free", i18n.int(s.free))}${row("weight", i18n.int(s.weight), s.noWeight ? ` <span class="mut">(${T("cap.sum.noWeight", { n: s.noWeight })})</span>` : "")}${row("withCat", i18n.int(s.withCat))}${s.fill != null ? row("fill", i18n.pct(s.fill)) : ""}</tbody></table>`;
  }

  // ---------- формы
  function dimsForm(n, K, info, ro) {
    const k = K("capacity"), d = info.dims, w = info.maxw, vol = d.w * d.d * d.h;
    const inp = (name, key, own, base) => `<label>${T(key)}<input type="number" name="${name}" step="0.01" min="0" value="${esc(fv(k, name, own ?? ""))}" placeholder="${esc(base)}"></label>`;
    return `${sec("cap.dimsTitle")}<form class="ed-form" data-op="capacity">${inp("dw", "cap.dw", d.own.w, d.base.w)}${inp("dd", "cap.dd", d.own.d, d.base.d)}${inp("dh", "cap.dh", d.own.h, d.base.h)}
      <label>${T("cap.maxw")}<input type="number" name="maxw" step="1" min="0" value="${esc(fv(k, "maxw", info.own && info.own.maxw != null ? info.own.maxw : ""))}" placeholder="${esc(w.v ?? "")}"></label>${btns(ro)}</form>
      <p class="ed-note" data-dims-eff>${T("cap.dimsEff", { w: i18n.m(d.w), d: i18n.m(d.d), h: i18n.m(d.h), v: i18n.m(Math.round(vol * 1000) / 1000) })} · ${w.v != null ? T("cap.maxwEff", { kg: i18n.int(w.v), src: t(`cap.src.${w.src}`) }) : T("cap.maxwNone")}</p>
      <p class="ed-note">${T("cap.dimsNote", { w: i18n.m(d.base.w), d: i18n.m(d.base.d), h: i18n.m(d.base.h) })}</p>`;
  }
  function catForm(n, K, info, ro) {
    const k = K("catAssign"), own = info.own && info.own.cat, list = model.cap.categories().list, cur = fv(k, "cat", own || "inherit");
    return `${sec("cap.catTitle")}<form class="ed-form" data-op="catAssign"><label class="wide"><span class="sr">${T("cap.catTitle")}</span><select name="cat">${opt("inherit", t("cap.catInherit"), cur)}${opt(NONE, t("scat.none"), cur)}${list.map((c) => opt(c.key, c.name, cur)).join("")}</select></label>${btns(ro)}</form>
      <p class="ed-note" data-cat-eff>${T("cap.catEff", { name: catLine(info.cat, n) })}</p>
      <div class="acts" style="margin-top:6px"><button type="button" class="btn btn-secondary" data-cats>${T("cap.catManage")}</button></div><p class="ed-note">${T("cap.catNote")}</p>`;
  }
  function flagsForm(n, K, info, ro) {
    const k = K("flags"), f = info.flags, o = f.own, tri = (v) => (v === true ? "1" : v === false ? "0" : "");
    const sel = (name, own, eff) => `<select name="${name}">${opt("", `${t("cap.asOdoo")} (${yn(eff)})`, fv(k, name, tri(own)))}${opt("1", t("cap.yes"), fv(k, name, tri(own)))}${opt("0", t("cap.no"), fv(k, name, tri(own)))}</select>`;
    return `${sec("cap.flagsTitle")}<form class="ed-form" data-op="flags">
      ${n.loc ? `<label class="wide">${T("cap.usage")}<select name="usage">${opt("", `${t("cap.asOdoo")} (${t(`cap.usage.${f.rec ? f.usage : "internal"}`)})`, fv(k, "usage", o.usage || ""))}${opt("internal", t("cap.usage.internal"), fv(k, "usage", o.usage || ""))}${opt("view", t("cap.usage.view"), fv(k, "usage", o.usage || ""))}</select></label>` : ""}
      <label>${T("cap.repl")}${sel("repl", o.repl, f.repl)}</label>
      ${n.loc && f.scrapOk ? `<label>${T("cap.scrap")}${sel("scrap", o.scrap, f.scrap)}</label>` : ""}${btns(ro)}</form><p class="ed-note">${T(n.loc && !f.scrapOk ? "cap.flagsNote19" : "cap.flagsNote")}</p>`;
  }
  function removalForm(n, K, info, ro) {
    const k = K("removal"), list = model.cap.removalStrategies(), f = info.flags, cur = String(fv(k, "rs", f.own.rs ?? ""));
    return `${sec("cap.rsTitle")}<form class="ed-form" data-op="removal"><label class="wide"><span class="sr">${T("cap.rsTitle")}</span><select name="rs">${opt("", `${t("cap.asOdoo")}${f.rsName && f.own.rs == null ? ` (${f.rsName})` : ""}`, cur)}${list.map((x) => opt(x.id, x.name, cur)).join("")}</select></label>${btns(ro)}</form>
      <p class="ed-note">${T(list.length ? "cap.rsNote" : "cap.rsNoList")}</p>`;
  }
  function minmaxForm(n, K, info, ro) {
    const k = K("minmax"), mm = info.minmax, P = (c) => (model.data.products[c] || { name: c }).name;
    if (!mm.editable) return `${sec("cap.mmTitle")}<p class="ed-note">${T("cap.mmNone")}</p>`;
    const eff = mm.eff || { product: mm.products[0], min: "", max: "" }, cur = fv(k, "product", eff.product);
    return `${sec("cap.mmTitle")}<form class="ed-form" data-op="minmax"><label class="wide">${T("cap.mmProduct")}<select name="product">${mm.products.map((c) => opt(c, `${P(c)} · ${c}`, cur)).join("")}</select></label>
      <label>${T("cap.mmMin")}<input type="number" name="min" min="0" step="1" value="${esc(fv(k, "min", eff.min))}"></label><label>${T("cap.mmMax")}<input type="number" name="max" min="0" step="1" value="${esc(fv(k, "max", eff.max))}"></label>${btns(ro)}</form>
      <p class="ed-note">${mm.rules.length ? T("cap.mmRules", { list: mm.rules.map((r) => `${P(r.product)}: ${r.min} / ${r.max}`).join("; ") }) : T("cap.mmNoRule")} ${T("cap.mmNote")}</p>`;
  }
  function fnForm(n, K, info, ro) {
    const k = K("zoneFn"), z = info.zone, o = z.own, cur = fv(k, "fn", o.fn || "");
    const mem = fv(k, "fn", null) !== null; // форма уже показывалась: флажки берутся из неё (снятый флажок в данные формы не попадает)
    const chk = (a) => `<label class="chk"><input type="checkbox" name="at_${a}"${(mem ? fv(k, `at_${a}`, null) !== null : o.at.includes(a)) ? " checked" : ""}> ${T(`fnattr.${a}`)}</label>`;
    return `${sec("cap.fnTitle")}<form class="ed-form" data-op="zoneFn"><label class="wide"><span class="sr">${T("cap.fnTitle")}</span><select name="fn">${opt("", z.fn && !o.fn ? `${t("cap.fnInherit")}: ${t(`fn.${z.fn}`)}` : t("cap.fnInherit"), cur)}${ZONE_FUNCS.map((f) => opt(f.id, t(`fn.${f.id}`), cur)).join("")}</select></label>
      ${ZONE_ATTRS.map(chk).join("")}
      <label>${T("cap.tmin")}<input type="number" name="tmin" step="0.5" value="${esc(fv(k, "tmin", o.tmin ?? ""))}"></label><label>${T("cap.tmax")}<input type="number" name="tmax" step="0.5" value="${esc(fv(k, "tmax", o.tmax ?? ""))}"></label>${btns(ro)}</form>
      <p class="ed-note">${T("cap.fnNote")}</p><div class="fn-legend">${ZONE_FUNCS.map((f) => `<span><i class="sw" style="background:${f.color}"></i>${T(`fn.${f.id}`)}</span>`).join("")}</div>`;
  }
  // ---------- панель редактирования: всё для узла
  function editHtml(n, K, ro) {
    const info = model.cap.node(n.id); if (!info) return "";
    const isGroup = n.type === "group" || n.type === "rackset";
    let h = `<div class="sec cap-h">${T("cap.title")}</div>`;
    h += summaryHtml(n);
    if (n.loc) h += dimsForm(n, K, info, ro);
    h += catForm(n, K, info, ro) + flagsForm(n, K, info, ro) + removalForm(n, K, info, ro);
    if (n.loc) h += minmaxForm(n, K, info, ro);
    if (isGroup) h += fnForm(n, K, info, ro) + rulesHtml(n);
    return h;
  }

  // правила размещения, ведущие в узел (W-15, E3): цель правила — сам узел или место внутри; клик открывает окно правил на этом правиле
  function rulesHtml(n) {
    const rs = model.putaway.into(n.id);
    if (n.loc && !rs.length) return "";
    const list = rs.length ? `<ul class="o_rules" data-into>${rs.map((r) => `<li><button type="button" class="btn btn-link" data-parule="${esc(r.key)}">${esc(model.putaway.name(r))}</button>${r.sub === "closest_location" ? ` <span class="o_tag">${T("pa.inside")}</span>` : ""}</li>`).join("")}</ul>` : `<p class="mut">${T("cap.rulesNone")}</p>`;
    return `${sec("cap.rulesTitle")}${list}<div class="acts"><button type="button" class="btn btn-secondary" data-parules>${T("cap.rulesOpen")}</button></div>`;
  }

  // ---------- просмотр (без правки): коротко о месте и зоне
  function browseHtml(n) {
    const info = model.cap.node(n.id); if (!info) return "";
    const row = (k, v) => `<tr><td class="first">${T(k)}</td><td class="n">${v}</td></tr>`;
    const f = info.flags, z = info.zone;
    let h = "";
    if (n.loc) {
      const d = info.dims, w = info.maxw;
      h += `${sec("cap.title")}<table class="o_list cap-info"><tbody>${row("cap.dimsTitle", `${i18n.m(d.w)} × ${i18n.m(d.d)} × ${i18n.m(d.h)} ${T("unit.m")}`)}
        ${row("cap.maxw", w.v != null ? `${i18n.int(w.v)} (${T(`cap.src.${w.src}`)})` : "—")}${row("cap.repl", yn(f.repl))}${f.scrapOk ? row("cap.scrap", yn(f.scrap)) : ""}${row("cap.usage", T(`cap.usage.${f.usage}`))}${row("cap.rsTitle", esc(f.rsName || "—"))}</tbody></table>`;
    }
    const hint = zoneHint(i18n, z);
    if (hint) h += `${n.loc ? "" : sec("cap.fnTitle")}<p class="cap-fn" data-fn="${esc(z.fn || "")}">${z.fn ? `<i class="sw" style="background:${(ZONE_FUNCS.find((x) => x.id === z.fn) || {}).color}"></i>` : ""}${esc(hint)}</p>`;
    if (!n.loc || n.kids.length) h += summaryHtml(n);
    h += rulesHtml(n);
    if (n.id === "WH") h += `<div class="acts" style="margin-top:8px"><button type="button" class="btn btn-secondary" data-cats>${T("cap.catManage")}</button></div>`;
    return h;
  }

  // карточка места W-17 показывает действующие значения: категорию (с наследованием и правками проекта) и правило min / max (правка проекта поверх Odoo) — одна карточка, без дублей
  function cardOf(card, n) {
    if (!card || !n) return card;
    const info = model.cap.node(n.id); if (!info) return card;
    const c = info.cat.cat, mm = info.minmax && info.minmax.eff;
    return { ...card, category: c ? { id: c.id, name: c.name, maxWeight: c.maxw || 0, allowNew: c.policy } : null, orderpoint: mm ? { min: mm.min, max: mm.max, product: mm.product } : card.orderpoint, orderpointOwn: !!(info.minmax && info.minmax.own) };
  }

  // кнопки «Категорії зберігання…» открывают окно (грузится лениво)
  function bind(root) {
    const openPa = (rule) => import("./putaway.js").then((m) => m.openPutaway({ model, i18n, rule })).catch((e) => { console.error(e); model.notify("bad", "n.fileFail"); });
    root.querySelectorAll("[data-parule]").forEach((b) => b.onclick = () => openPa(b.dataset.parule));
    root.querySelectorAll("[data-parules]").forEach((b) => b.onclick = () => openPa(null));
    root.querySelectorAll("[data-cats]").forEach((b) => b.onclick = () => import("./storage.js").then((m) => m.openCategories({ model, i18n })));
  }
  return { editHtml, browseHtml, summaryHtml, cardOf, bind };
}
