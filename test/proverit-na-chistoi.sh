#!/bin/bash
# Тест пакета на чистой домашней папке (Mac/Linux; Windows так не проверить).
# Запуск: bash test/proverit-na-chistoi.sh <пустая-папка-для-теста>
# Ставит пакет из этой папки в поддельный HOME и проверяет: установку, повтор, чужие настройки,
# автообновление, удаление из пакета, свой навык, работу без сети, сохранность личного, испорченный settings.json.
set -u
PAKET="$(cd "$(dirname "$0")/.." && pwd)"
BAZA="${1:?укажи пустую папку для теста}"
mkdir -p "$BAZA"; BAZA="$(cd "$BAZA" && pwd)"
ok=0; fail=0
pass() { echo "✓ $1"; ok=$((ok+1)); }
nope() { echo "✗ $1"; fail=$((fail+1)); }
py() { sh "$HOME/.claude/umnyi/bin/py" "$@"; }
GIT="git -c user.name=test -c user.email=test@example.com"

novyi_home() {  # $1 — имя; создаёт HOME и «GitHub» (bare-репозиторий) с текущим пакетом
  export HOME="$BAZA/$1/home"; R="$BAZA/$1/remote.git"; mkdir -p "$HOME"
  git clone -q --bare "$PAKET" "$R"
  git clone -q "$R" "$HOME/.claude/umnyi"
}

# 1. Чистая установка
novyi_home a
py "$HOME/.claude/umnyi/install.py" >/dev/null && pass "установка на чистую папку" || nope "установка"
py "$HOME/.claude/umnyi/proverka.py" > "$BAZA/a/p1.txt"; [ $? = 0 ] && grep -q "ВСЁ РАБОТАЕТ" "$BAZA/a/p1.txt" \
  && pass "проверка: ВСЁ РАБОТАЕТ" || { nope "проверка после установки"; cat "$BAZA/a/p1.txt"; }
grep -q "заполнено: пока ни одного" "$BAZA/a/p1.txt" && pass "пустые ключи не считаются заполненными" || nope "счёт ключей"
for d in "Projects/мозг/бренд" "Projects/материалы/входящие" "Projects/материалы/расшифровки" "Projects/завод" "Projects/проекты"; do
  [ -d "$HOME/$d" ] || nope "нет папки $d"; done
[ -f "$HOME/.claude/rules/umnyi-1-kak-rabotat.md" ] && [ -f "$HOME/.claude/skills/proverka/SKILL.md" ] && \
  [ -f "$HOME/.claude/agents/kritik.md" ] && pass "правила, навыки и помощники на месте" || nope "файлы пакета"

# 2. Повторная установка ничего не дублирует
cp "$HOME/.claude/settings.json" "$BAZA/a/s1.json"
py "$HOME/.claude/umnyi/install.py" --tiho >/dev/null
cmp -s "$HOME/.claude/settings.json" "$BAZA/a/s1.json" && pass "повторная установка: настройки те же, без дублей" || nope "повтор меняет настройки"

# 3. Чужие настройки и свой навык сохраняются
novyi_home b
mkdir -p "$HOME/.claude/skills/github"; echo "мой навык" > "$HOME/.claude/skills/github/SKILL.md"
cat > "$HOME/.claude/settings.json" <<'EOF'
{"model": "sonnet", "permissions": {"allow": ["Bash(npm test)"], "defaultMode": "plan"},
 "hooks": {"Stop": [{"hooks": [{"type": "command", "command": "echo moi"}]}]}, "enabledPlugins": {"x@y": true}}
EOF
py "$HOME/.claude/umnyi/install.py" > "$BAZA/b/i.txt"
S="$HOME/.claude/settings.json"
grep -q '"Bash(npm test)"' "$S" && grep -q '"echo moi"' "$S" && grep -q '"x@y"' "$S" && grep -q '"sonnet"' "$S" \
  && pass "чужие настройки на месте" || nope "чужие настройки потерялись"
grep -q '"defaultMode": "plan"' "$S" && pass "сознательно выбранный режим plan не перезаписан" || nope "режим перезаписан"
grep -q "мой навык" "$HOME/.claude/skills/github/SKILL.md" && grep -q "уже есть свой" "$BAZA/b/i.txt" \
  && pass "свой навык с тем же именем не тронут" || nope "свой навык перезаписан"
[ -f "$HOME/.claude/settings.json.umnyi-kopiya" ] && pass "копия settings.json до правки" || nope "нет копии настроек"

# 4. Автообновление: новая версия на «GitHub»
export HOME="$BAZA/a/home"; R="$BAZA/a/remote.git"
echo "моё правило" >> "$HOME/.claude/rules/moi-pravila.md"
echo "- Имя: Тест" >> "$HOME/.claude/CLAUDE.md"
echo "моя заметка" > "$HOME/Projects/мозг/кто-я.md"
W="$BAZA/a/work"; git clone -q "$R" "$W"
echo "1.0.1" > "$W/VERSIYA"
printf '# Новое правило\nМетка теста: НОВОЕ-ПРАВИЛО\n' > "$W/rules/umnyi-9-test.md"
git -C "$W" rm -q -r skills/peredacha
python3 - "$W/ЧТО-НОВОГО.md" <<'EOF'
import sys; p=sys.argv[1]; t=open(p,encoding='utf-8').read()
t=t.replace("## 1.0.0", "## 1.0.1 — тест\n- Тестовое правило.\n\n## 1.0.0",1); open(p,'w',encoding='utf-8').write(t)
EOF
(cd "$W" && $GIT add -A && $GIT commit -qm "1.0.1" && git push -q origin main)
echo '{}' | py "$HOME/.claude/umnyi/obnovlenie.py" > "$BAZA/a/hook1.txt"
[ ! -s "$BAZA/a/hook1.txt" ] && pass "хук молчит, если проверял меньше 6 часов назад" || nope "хук не держит паузу"
python3 -c "import json,sys;p=sys.argv[1];s=json.load(open(p));s['posl_proverka']=0;json.dump(s,open(p,'w'))" "$HOME/.claude/umnyi-sostoyanie.json"
echo '{}' | py "$HOME/.claude/umnyi/obnovlenie.py" > "$BAZA/a/hook2.txt"
python3 -c "import json,sys;d=json.load(open(sys.argv[1]));c=d['hookSpecificOutput']['additionalContext'];assert '1.0.0 → 1.0.1' in c and 'Тестовое правило' in c" "$BAZA/a/hook2.txt" \
  && pass "хук обновил и передал Claude «что нового»" || { nope "автообновление"; cat "$BAZA/a/hook2.txt"; }
[ -f "$HOME/.claude/rules/umnyi-9-test.md" ] && pass "новое правило пришло" || nope "новое правило не пришло"
[ ! -e "$HOME/.claude/skills/peredacha" ] && pass "убранный из пакета навык убран и у ученика" || nope "старый навык остался"
grep -q "моё правило" "$HOME/.claude/rules/moi-pravila.md" && grep -q "Имя: Тест" "$HOME/.claude/CLAUDE.md" \
  && grep -q "моя заметка" "$HOME/Projects/мозг/кто-я.md" && pass "свои правила, паспорт и мозг после обновления целы" || nope "личное пострадало"
py "$HOME/.claude/umnyi/proverka.py" > "$BAZA/a/p2.txt" && grep -q "1.0.1" "$BAZA/a/p2.txt" && pass "проверка после обновления: ВСЁ РАБОТАЕТ" \
  || { nope "проверка после обновления"; cat "$BAZA/a/p2.txt"; }

# 5. Без сети: хук молчит и быстро выходит
git -C "$HOME/.claude/umnyi" remote set-url origin "https://example.invalid/net.git"
python3 -c "import json,sys;p=sys.argv[1];s=json.load(open(p));s['posl_proverka']=0;json.dump(s,open(p,'w'))" "$HOME/.claude/umnyi-sostoyanie.json"
t0=$(date +%s); echo '{}' | py "$HOME/.claude/umnyi/obnovlenie.py" > "$BAZA/a/hook3.txt"; kod=$?; t1=$(date +%s)
[ $kod = 0 ] && [ ! -s "$BAZA/a/hook3.txt" ] && [ $((t1-t0)) -le 25 ] && pass "без сети: молча, $((t1-t0)) с" || nope "без сети: код $kod, $((t1-t0)) с"
t0=$(date +%s); echo '{}' | py "$HOME/.claude/umnyi/obnovlenie.py" >/dev/null; t1=$(date +%s)
[ $((t1-t0)) -le 2 ] && pass "без сети следующий чат не тормозит (пауза час)" || nope "без сети тормозит каждый чат"

# 6. Выключенное обновление
echo "UMNYI_BEZ_OBNOVLENIY=1" >> "$HOME/.claude/.env"
python3 -c "import json,sys;p=sys.argv[1];s=json.load(open(p));s['posl_proverka']=0;json.dump(s,open(p,'w'))" "$HOME/.claude/umnyi-sostoyanie.json"
t0=$(date +%s); echo '{}' | py "$HOME/.claude/umnyi/obnovlenie.py" >/dev/null; t1=$(date +%s)
[ $((t1-t0)) -le 2 ] && pass "UMNYI_BEZ_OBNOVLENIY=1 выключает обновление" || nope "выключатель не работает"

# 7. Испорченный settings.json не перезаписывается
novyi_home c
echo '{ сломано' > "$HOME/.claude/settings.json"
py "$HOME/.claude/umnyi/install.py" > "$BAZA/c/i.txt"; kod=$?
[ $kod != 0 ] && grep -q "испорчен" "$BAZA/c/i.txt" && grep -q "сломано" "$HOME/.claude/settings.json" \
  && pass "испорченный settings.json: остановка, файл не тронут" || nope "испорченный settings.json"

# 8. Мозг в Git: .env не попадает
export HOME="$BAZA/a/home"
(cd "$HOME/Projects" && git init -q -b main && echo "K=1" > .env && $GIT add -A && $GIT commit -qm t)
[ -z "$(git -C "$HOME/Projects" ls-files .env)" ] && pass ".gitignore мозга не пускает .env в Git" || nope ".env попал в Git"
mv "$HOME/Projects/.env" "$BAZA/a/env-lishnii"

echo; echo "Итог: ✓ $ok, ✗ $fail"
[ $fail = 0 ]
