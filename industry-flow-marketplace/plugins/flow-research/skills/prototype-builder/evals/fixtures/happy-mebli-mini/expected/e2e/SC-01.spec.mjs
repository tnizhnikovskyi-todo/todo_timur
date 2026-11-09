export default async ({ goto, step, click, seeTitle, seeState, pause }) => {
  await goto('S-01');
  await step('SC-01.1', 'Відкриває перелік замовлень'); await seeTitle('Замовлення'); await pause();
  await click('row-o1'); // відкриття запису зі списку веде на форму S-02
  await step('SC-01.2', 'Відкриває картку замовлення'); await seeTitle('Картка замовлення'); await pause();
  await step('SC-01.3', 'Підтверджує замовлення'); await click('order-confirm'); await seeTitle('Завдання цеху'); await pause();
};
