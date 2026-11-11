// ПРИКЛАД кроків (замінити на кроки SALES §6 цієї галузі у файлі scenario.steps.mjs; цей файл — лише для перевірки каркаса).
export const STEPS = [
    { n: 1, role: 'manager', url: '/odoo', name: 'start', facts: [] },
];
export const PASS1 = [];   // номери кроків, що змінюють дані (створення/підтвердження)
export const PASS2 = [1];  // лише читання: дашборд, звіти
