// Учебная копия склада для туров, которые меняют данные (W-24): временный вариант планировки (W-18, variants.js). Тур работает в нём, в конце
// пользователь выбирает: «Залишити зміни» (вариант остаётся или сливается в исходный) либо «Скасувати зміни туру» (вариант удаляется, исходный слой не тронут).
// Запись о копии лежит в настройках модели (pref «tourcopy»): прерванный тур при следующем открытии предлагает копию убрать. Без DOM.
export const COPY_KEY = "tourcopy";

const readRec = (model) => { try { const r = JSON.parse(model.pref.read(COPY_KEY) || "null"); return r && r.v === 1 && r.copy ? r : null; } catch (e) { return null; } };
const writeRec = (model, rec) => { try { model.pref.write(COPY_KEY, rec ? JSON.stringify(rec) : ""); } catch (e) { /* без хранилища запись не сохранится */ } };
export const copyRec = readRec;

// копия возможна: роль «проєктування», не режим «перегляд»; возвращает ключ уведомления о причине отказа или null
export function copyDenied(model) {
  if (model.readonly || !model.can("variant")) return "tour.needDesign";
  if (model.variants.list().length >= model.variants.max) return "tour.varMax";
  return null;
}

// создать учебную копию активного склада; name — имя варианта. Возвращает запись или null
export function beginCopy(model, { tour, name }) {
  if (copyDenied(model)) return null;
  const orig = model.variants.active, vars0 = model.variants.list().map((v) => v.id), cm0 = model.comments.list().map((c) => c.id);
  let nm = name, i = 2; while (model.variants.list().some((v) => (v.name || "").toLowerCase() === nm.toLowerCase())) nm = `${name} (${i++})`;
  const id = model.variants.create(nm);
  if (!id) return null;
  const rec = { v: 1, tour, proj: model.project.id, wh: model.warehouse.id, orig, copy: id, vars0, cm0 };
  writeRec(model, rec);
  return rec;
}

// копия ещё есть в проекте (после перезагрузки или в другом склада)
export function copyAlive(model, rec) {
  const w = model.project.warehouses.find((x) => x.id === rec.wh);
  return !!w && rec.proj === model.project.id && (w.variant === rec.copy || w.variants.some((v) => v.id === rec.copy));
}
export const tourVariants = (model, rec) => model.variants.list().filter((v) => !rec.vars0.includes(v.id)).map((v) => v.id);

const toWh = (model, rec) => { if (model.warehouse.id !== rec.wh) model.setWarehouse(rec.wh); };

// «Скасувати зміни туру»: вернуться к исходному варианту, убрать варианты и комментарии, созданные туром. Исходный слой не трогается
export async function cancelCopy(model, rec) {
  toWh(model, rec);
  if (model.variants.active !== rec.orig && model.variants.list().some((v) => v.id === rec.orig)) model.variants.switch(rec.orig);
  for (const id of tourVariants(model, rec)) if (id !== model.variants.active) model.variants.remove(id);
  for (const c of model.comments.list()) if (!rec.cm0.includes(c.id)) await model.comments.remove(c.id);
  writeRec(model, null);
  return model.variants.list().length === rec.vars0.length;
}

// «Залишити зміни»: how = "variant" — вариант остаётся (и активен), "merge" — сливается в исходный; возвращает, что сделано ("variant" | "merge")
export async function keepCopy(model, rec, how) {
  toWh(model, rec);
  if (model.pending.length) await model.save("WH");
  let done = "variant";
  if (how === "merge" && model.variants.list().some((v) => v.id === rec.orig)) {
    const src = tourVariants(model, rec).includes(model.variants.active) ? model.variants.active : rec.copy;
    if (model.variants.active !== rec.orig) model.variants.switch(rec.orig);
    if (model.variants.merge(src)) { done = "merge"; for (const id of tourVariants(model, rec)) model.variants.remove(id); }
    else if (model.variants.active !== src) model.variants.switch(src); // у исходного есть несохранённое: слить нельзя, остаётся вариантом
  }
  writeRec(model, null);
  return done;
}
