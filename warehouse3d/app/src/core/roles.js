// Роли конструктора (D-19, I4): права берёт хранилище (модуль Odoo: группы «перегляд» ⊂ «проєктування» ⊂ «застосування»); вне Odoo права полные.
// Чистые функции без DOM. Что доступно роли — таблица ACTIONS (действие → минимальная роль); интерфейс прячет или отключает недоступное с подсказкой.
export const ROLES = ["view", "design", "apply"];
// comment — писать комментарии; edit / save / variant / restore / resolve / lock — править проект, варианты, версии, решать комментарии, занимать зоны; apply — «План змін → Застосувати»
export const ACTIONS = { comment: "view", edit: "design", save: "design", variant: "design", restore: "design", resolve: "design", lock: "design", apply: "apply" };

export const normRights = (r) => ({ view: !r || r.view !== false, design: !r || r.design !== false, apply: !r || r.apply !== false });

// права хранилища: только чтение (readonly) отнимает проектирование и применение; без поля rights — полные
export function rightsOf(storage) {
  const r = normRights(storage && storage.rights);
  if (storage && storage.readonly) { r.design = false; r.apply = false; }
  if (!r.design) r.apply = false;
  return r;
}
export const roleOf = (rights) => (rights.apply ? "apply" : rights.design ? "design" : "view");
export const canDo = (rights, action) => !!rights[ACTIONS[action]];
