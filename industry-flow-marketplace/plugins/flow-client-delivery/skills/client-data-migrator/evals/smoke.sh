#!/usr/bin/env bash
# Smoke-тест скриптів скіла на фікстурах. Запуск: bash evals/smoke.sh (з теки скіла). Код виходу 0 = усе очікувано.
set -u
cd "$(dirname "$0")/.." || exit 2
F=evals/fixtures; rc=0
chk() { if [ "$2" = "$3" ]; then echo "ok   $1"; else echo "FAIL $1: очікувано $2, отримано $3"; rc=1; fi; }
python3 -I scripts/check_pii.py --path $F/sample >/dev/null; chk "pii: замаскована вибірка чиста" 0 $?
python3 -I scripts/check_pii.py --path $F/client/migration-plan.md >/dev/null; chk "pii: план зі сумою/кількістю чистий" 0 $?
python3 -I scripts/check_pii.py --path $F/sample_bad >/dev/null; chk "pii: незамасковане дає FAIL" 1 $?
python3 -I scripts/check_pii.py --path $F/pii_bad2_fop --allow-columns "Кількість,Артикул" >/dev/null; chk "pii: ФОП у назві дає FAIL" 1 $?
python3 -I scripts/check_pii.py --path $F/pii_code >/dev/null; chk "pii: код/артикул у Кількість без allow -> FAIL (phone)" 1 $?
python3 -I scripts/check_pii.py --path $F/pii_code --allow-columns "Кількість,Артикул" >/dev/null; chk "pii: allow-columns знімає хибний збіг" 0 $?
mig() { python3 -I scripts/check_migration.py --client-dir $F/$1 --tag package/v0.1 --readme $F/client/README.md --templates $F/templates "${@:3}" | python3 -I -c "import json,sys;print({x['id']:x['status'] for x in json.load(sys.stdin)}.get('$2'))"; }
chk "mig: MIG-required збіг -> PASS" PASS "$(mig client_ok MIG-required)"
chk "mig: MIG-required розбіжність -> FAIL" FAIL "$(mig client_bad MIG-required)"
chk "mig: MIG-recon збіг -> PASS" PASS "$(mig client_ok MIG-recon)"
chk "mig: MIG-recon розбіжність -> FAIL" FAIL "$(mig client_bad MIG-recon)"
chk "mig: MIG-coverage -> PASS" PASS "$(mig client_ok MIG-coverage)"
chk "mig: режим reconcile" PASS "$(mig client_ok MIG-recon --mode reconcile)"
chk "mig: режим return без виправлень -> FAIL" FAIL "$(mig client_ok MIG-return --mode return)"
out=$(python3 -I scripts/check_migration.py --client-dir $F/client --tag package/v0.1 --readme $F/client/README.md)
echo "$out" | python3 -I -c "
import json,sys
r={x['id']:x['status'] for x in json.load(sys.stdin)}
for i,e in (('MIG-tag','PASS'),('MIG-order','PASS'),('MIG-headings','PASS'),('MIG-registry','PASS'),('MIG-source','waiting_human')):
    print('ok  ' if r.get(i)==e else 'FAIL', i, r.get(i), '(очікувано %s)'%e)
sys.exit(0 if all(r.get(i)==e for i,e in (('MIG-tag','PASS'),('MIG-order','PASS'),('MIG-headings','PASS'),('MIG-registry','PASS'),('MIG-source','waiting_human'))) else 1)
"; rc=$((rc|$?))
exit $rc
