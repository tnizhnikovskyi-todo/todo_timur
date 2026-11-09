export default async ({ goto, step, seeTitle, pause }) => {
  await goto('S-03');
  await step('SC-02.1', 'Відкриває дошку завдань'); await seeTitle('Завдання цеху'); await pause();
};
