// Интерфейс хранения; реализацию передаёт хост.
//   storage.read(name)         → сохранённое значение (уже разобранное) или null
//   storage.write(name, value) → "local" | "shared" | "fail" (или Promise с тем же); значения — JSON-совместимые
//   storage.readonly           → true: сохранять нельзя (кнопки «Зберегти» скрываются)
// Имена: "edit" (сохранённые правки), "pending" (несохранённые), "pick" (что выделяет клик), "mode" (2d/3d), "lang".

// Хранилище в памяти — для тестов и как запасной вариант
export function createMemoryStorage(initial = {}, { readonly = false } = {}) {
  const m = new Map(Object.entries(initial).map(([k, v]) => [k, JSON.stringify(v)]));
  return {
    readonly,
    read: (name) => (m.has(name) ? JSON.parse(m.get(name)) : null),
    write(name, value) { m.set(name, JSON.stringify(value)); return "local"; },
    dump: () => Object.fromEntries([...m].map(([k, v]) => [k, JSON.parse(v)])),
  };
}
