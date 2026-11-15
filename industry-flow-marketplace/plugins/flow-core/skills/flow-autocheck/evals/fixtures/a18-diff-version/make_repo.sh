#!/usr/bin/env bash
# A-18: між SHA ACCEPTANCE і кандидатом змінено README, CHANGELOG (дозволені) і package/questionnaire.md (заборонений, поза переліком versioning.md); td_x має 19.0.1.1, ACCEPTANCE каже 1.2.
set -e; D=${1:?dest}; mkdir -p "$D/repo"; cd "$D/repo"
git init -q -b main; git config user.email t@example.test; git config user.name t
mkdir -p package/addons/td_x package/demo package/templates
echo "{'name':'x','version':'19.0.1.1'}" > package/addons/td_x/__manifest__.py
echo "v1" > package/demo/README.md; echo v1 > package/questionnaire.md
printf '# Журнал\n## Версія package/v1.2\n## Зміни анкети\n## Несумісні зміни\n## Міграція з попереднього тегу\n' > package/CHANGELOG.md
printf '# Шаблон\n\n```markdown\n## Версія <тег>\n### Сумісність з Odoo <- лише odoo-upgrade\n### Виправлено (hotfix) <- лише patch\n```\n' > package/templates/changelog-template.md
echo x > package/templates/migration-plan.md; echo x > package/templates/training.md
git add -A; git commit -qm accepted; ACC=$(git rev-parse HEAD)
printf '# Приймання\nВерсія 1.2\nSHA: %s\n' "$ACC" > package/ACCEPTANCE.md
echo v2 > package/demo/README.md; echo "#!/bin/sh" > package/demo/up.sh; echo v2 > package/questionnaire.md; echo "# 1.2 нове" >> package/CHANGELOG.md
git add -A; git commit -qm candidate; HEAD=$(git rev-parse HEAD)
cat > "$D/naryad.json" <<X
{"step":"A-18","scope":{"kind":"package","id":"demo-1"},"inputs":[],"where":"package/","template":"package/templates/changelog-template.md","attempt":1,"client_data":"none",
 "done":"перелік versioning.md: package/demo/README.md, package/demo/scenarios.md, package/ACCEPTANCE.md, package/CHANGELOG.md, package/templates/migration-plan.md, package/templates/training.md, package/templates/CHANGELOG.md",
 "check":{"mode":"both","how":"diff"},"params":{"version":"1.2"},"repo":{"url":"x","base_branch":"main","branch":"flow/a18"},"git":{"base":"$ACC","head":"$HEAD"}}
X
