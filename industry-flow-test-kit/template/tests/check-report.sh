#!/usr/bin/env bash
# Перевірка звіту кроку ПЕРЕД комітом (0.4.1; закриває «E2 flow_position не перевіряється в тестовому режимі»):
#   bash tests/check-report.sh tests/reports/<ім'я наряду>[-<спроба>].md [tests/naryad/<наряд>.yaml]
# 1) у звіті один рядок flow_position у форматі «етап N з 6 «назва»: зроблено … / далі … / до гейта …»;
# 2) якщо в наряді є блок review: — у звіті є review_rounds (число кругів); для A-16b — також 3 кути незалежного аудиту.
# Autocheck з --head на коміті результату звіт не бачить (його комітять пізніше), тому цей скрипт обов'язковий у ТЕСТОВОМУ РЕЖИМІ.
set -u
rep="${1:?звіт tests/reports/….md}"; nar="${2:-}"; rc=0
[ -f "$rep" ] || { echo "ERROR: немає звіту $rep"; exit 2; }
n=$(grep -c '^flow_position:' "$rep" || true)
[ "$n" = 1 ] || { echo "FAIL flow_position: рядків $n (потрібен рівно 1)"; rc=1; }
grep -E '^flow_position:.*етап [0-9] з 6 .*зроблено.*/ *далі.*/ *до гейта' "$rep" >/dev/null || { echo "FAIL flow_position: формат «етап N з 6 «назва»: зроблено … / далі … / до гейта …»"; rc=1; }
if [ -n "$nar" ] && grep -q '^review:' "$nar"; then
  grep -E '^review_rounds:' "$rep" >/dev/null || { echo "FAIL review_rounds: у наряді є review:, у звіті немає"; rc=1; }
  case "$nar" in *A-16b*) for k in 'адмін' 'ролі|роль' 'код|переліки'; do grep -Eiq "$k" "$rep" || { echo "WARN аудит A-16b: у звіті не видно кута «$k» (3 кути: адміністратор / ролі / переліки з коду)"; }; done;; esac
fi
[ $rc = 0 ] && echo "OK $rep"
exit $rc
