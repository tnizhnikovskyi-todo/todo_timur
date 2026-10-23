from odoo import _, api, fields, models
from odoo.exceptions import UserError

INSTRUCTION = """\
Ти працюєш над проєктом Odoo «{name}» (id {id}), база {db}, адреса {base_url}.
Джерело правди — Odoo. Усе читай і записуй через конектор odoo-mcp, а не зі спогадів чи з цього чату.

Підключення
- Виклич list_odoo_connections і обери з'єднання, де url == {base_url} і db == {db}.
  Людина працює через власне з'єднання; з'єднання інших користувачів і агентів не використовуй.
- У кожному виклику odoo_* передавай connection_id і перевіряй, що в результаті connection.db == {db}.

Що робити на початку розмови
1. Виклич odoo_execute: model project.project, method td_claude_project_brief, ids [{id}].
   Він поверне репозиторій, гілку, контекст проєкту та перелік скілів (корпоративні й проєкту) без текстів.
2. За потреби прочитай потрібні скіли за кодами.
3. Задачі: odoo_search_read по project.task з domain [["project_id","=",{id}]], стадії й виконавці — в тих самих полях.
4. Чатер: mail.message за res_model project.task / project.project і res_id; обговорення — це контекст рішень.
5. Поле td_claude_context проєкту (project.project, id {id}) — накопичений контекст: цілі, правила, рішення.

Запис результатів
- Важливі рішення, домовленості й обмеження дописуй через odoo_execute: project.project, метод
  td_claude_append_context, ids [{id}], args [текст одним-двома реченнями].
- Інші зміни в Odoo роби лише на прохання людини й коротко звітуй, що саме змінено і в якій базі.

Межі
- Нічого не видаляй в Odoo і нічого не надсилай назовні (пошта, месенджери, зовнішні API) без явного «так» людини.
- Не вигадуй код, поля й номери задач: якщо даних немає в Odoo, скажи про це.
- Відповідай українською, стисло, з посиланнями на задачі ({base_url}/odoo/project.task/<id>).
"""


class TdClaudeProjectWizard(models.TransientModel):
    _name = "td.claude.project.wizard"
    _description = "Інструкція для проєкту Claude"

    project_id = fields.Many2one("project.project", string="Проєкт", required=True, readonly=True)
    instruction = fields.Text(string="Інструкція для claude.ai Project", compute="_compute_instruction")
    claude_url = fields.Char(string="Посилання на проєкт claude.ai")

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        project = self.env["project.project"].browse(res.get("project_id") or 0).exists()
        if project and "claude_url" in fields_list:
            res["claude_url"] = project.td_claude_project_url
        return res

    @api.depends("project_id")
    def _compute_instruction(self):
        base_url = (self.env["ir.config_parameter"].sudo().get_param("web.base.url") or "").rstrip("/")
        for wizard in self:
            project = wizard.project_id
            wizard.instruction = (
                INSTRUCTION.format(name=project.display_name, id=project.id, db=self.env.cr.dbname, base_url=base_url)
                if project
                else False
            )

    def action_save_url(self):
        self.ensure_one()
        url = (self.claude_url or "").strip()
        if url and not url.lower().startswith(("https://", "http://")):
            raise UserError(_("Посилання на проєкт claude.ai має починатися з https://"))
        self.project_id.check_access("read")
        # проєкт доступний звичайному користувачу лише на читання: збереження посилання робимо від імені системи
        self.project_id.sudo().td_claude_project_url = url or False
        return {"type": "ir.actions.act_window_close"}
