"""Проверка «всё работает» для пакета «Умный Claude». Mac и Windows, Python 3.8+.

Запуск: sh "$HOME/.claude/umnyi/bin/py" "$HOME/.claude/umnyi/proverka.py"   (--json — вывод для программ)
✓ работает · ✗ сломано (строка «как починить» — для Claude) · ! подсказка, не поломка.
Ничего не меняет и в интернет не ходит, кроме быстрой проверки обновления.
"""
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
HOME = Path.home()
CLAUDE = HOME / ".claude"
itog = []


def ok(t):
    itog.append(("✓", t, ""))


def bad(t, kak):
    itog.append(("✗", t, kak))


def tip(t):
    itog.append(("!", t, ""))


def md5(p):
    return hashlib.md5(p.read_bytes()).hexdigest()


def run(cmd, timeout=10):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
        return r.returncode, (r.stdout or "") + (r.stderr or "")
    except Exception as e:
        return 1, str(e)


def sistema():
    win = os.name == "nt"
    ok(f"система: {'Windows' if win else platform.system()} {platform.release()}, Python {platform.python_version()}")
    k, out = run(["git", "--version"])
    if k == 0:
        ok(f"git: {out.strip().replace('git version ', '')}")
    else:
        bad("git не установлен", "Windows: winget install --id Git.Git -e --source winget, потом перезапустить Claude. Mac: xcode-select --install")
    k, out = run(["claude", "--version"])
    if k == 0:
        ok(f"Claude Code: {out.strip().split()[0]}")
    else:
        tip("команда claude не найдена в терминале — это нормально, если работаешь в приложении Claude")
    doma = str(HOME)
    if win and (not doma.isascii() or " " in doma):
        tip(f"в пути домашней папки есть русские буквы или пробел ({doma}) — если какая-то программа споткнётся, скажи Claude")


def paket():
    if not (ROOT / ".git").exists():
        bad("пакет поставлен не из Git — не будет обновляться", "переустановить: git clone <ссылка пакета> ~/.claude/umnyi")
    if os.path.normcase(str(ROOT)) != os.path.normcase(str((CLAUDE / "umnyi").resolve())):
        bad(f"пакет лежит не там ({ROOT})", "перенести в ~/.claude/umnyi и запустить install.py ещё раз")
    try:
        s = json.loads((CLAUDE / "umnyi-sostoyanie.json").read_text(encoding="utf-8"))
        ok(f"пакет «Умный Claude» {s.get('versiya')} установлен")
        return s
    except Exception:
        bad("пакет не установлен до конца (нет ~/.claude/umnyi-sostoyanie.json)", "запустить install.py")
        return {}


def pravila():
    nashi = sorted((ROOT / "rules").glob("umnyi-*.md"))
    ne_te = [p.name for p in nashi if not (CLAUDE / "rules" / p.name).exists()
             or md5(p) != md5(CLAUDE / "rules" / p.name)]
    if ne_te:
        bad(f"правила не те или нет: {', '.join(ne_te)}", "запустить install.py")
    else:
        ok(f"правила работы на месте ({len(nashi)} файла)")
    if not (CLAUDE / "rules" / "moi-pravila.md").exists():
        bad("нет файла своих правил moi-pravila.md", "запустить install.py")


def pasport():
    p = CLAUDE / "CLAUDE.md"
    if not p.exists():
        bad("нет паспорта ~/.claude/CLAUDE.md", "запустить install.py")
        return
    t = p.read_text(encoding="utf-8", errors="ignore")
    pusto = t.count("— (заполнить")
    strok = t.count("\n")
    if pusto:
        tip(f"паспорт есть, не заполнено полей: {pusto} — заполним по интервью (урок 3)")
    else:
        ok("паспорт заполнен")
    if strok > 200:
        tip(f"паспорт длинный ({strok} строк) — больше 200 Claude слушается хуже, подробное лучше перенести в мозг")


def nastroiki(s):
    p = CLAUDE / "settings.json"
    try:
        st = json.loads(p.read_text(encoding="utf-8-sig"))
    except Exception:
        bad("~/.claude/settings.json нет или он испорчен", "попросить Claude починить settings.json, потом install.py")
        return
    perms = st.get("permissions", {})
    mode = perms.get("defaultMode")
    if mode == "auto":
        ok("автономный режим: auto (Claude не спрашивает разрешения на обычные действия)")
    else:
        bad(f"режим разрешений «{mode}», а не auto", "в settings.json permissions.defaultMode = \"auto\" (install.py ставит сам)")
    deny = perms.get("deny", [])
    if "Read(~/.claude/.env)" in deny:
        ok("ключи защищены: Claude запрещено читать .env")
    else:
        bad("нет запрета читать .env", "запустить install.py")
    env_am = st.get("autoMode", {}).get("environment", [])
    if env_am[:1] == ["$defaults"] and len(env_am) > 1:
        ok("проверка безопасности знает твои сервисы (HeyGen, Kie, ElevenLabs …)")
    else:
        bad("autoMode.environment не настроен", "запустить install.py")
    hooks = json.dumps(st.get("hooks", {}).get("SessionStart", []))
    if "obnovlenie.py" in hooks:
        ok("автообновление включено (при открытии нового чата, раз в 6 часов)")
    else:
        bad("нет хука автообновления", "запустить install.py")
    if st.get("env", {}).get("PYTHONUTF8") != "1":
        bad("не включён UTF-8 для Python (русские буквы на Windows)", "запустить install.py")
    if st.get("autoMemoryEnabled") is False:
        bad("память Claude выключена", "в чате открыть /memory и включить auto memory")
    else:
        ok("память Claude включена")


def navyki_i_pomoshchniki(s):
    for vid, imya in (("skills", "навыки"), ("agents", "помощники")):
        nashi = sorted(p.name for p in (ROOT / vid).iterdir()) if (ROOT / vid).exists() else []
        net = []
        for n in nashi:
            f = CLAUDE / vid / n / "SKILL.md" if vid == "skills" else CLAUDE / vid / n
            if not f.exists() or not f.read_text(encoding="utf-8", errors="ignore").startswith("---"):
                net.append(n)
        if net:
            bad(f"{imya}: нет {', '.join(net)}", "запустить install.py")
        else:
            ok(f"{imya}: {', '.join(n.replace('.md', '') for n in nashi)}")


def mozg(s):
    pr = Path(s.get("proekty") or HOME / "Projects")
    if not pr.exists():
        bad(f"нет папки цифрового мозга {pr}", "запустить install.py")
        return
    net = [x for x in ("CLAUDE.md", "Задачи.md", ".gitignore", "мозг", "материалы/входящие", "завод", "проекты")
           if not (pr / x).exists()]
    if net:
        bad(f"в папке {pr.name} нет: {', '.join(net)}", "запустить install.py")
    else:
        ok(f"цифровой мозг: {pr} (мозг, материалы, завод, проекты)")
    gi = (pr / ".gitignore").read_text(encoding="utf-8", errors="ignore") if (pr / ".gitignore").exists() else ""
    if ".env" not in gi.split():
        bad(".gitignore не закрывает .env", "запустить install.py")
    if "onedrive" in str(pr).lower():
        tip("папка лежит в OneDrive — рендер видео может ломаться, лучше перенести в домашнюю папку")
    lishnie = [p for p in pr.rglob(".env") if "node_modules" not in p.parts][:3]
    if lishnie:
        tip(f"в папке мозга есть .env ({lishnie[0]}) — ключи лучше держать в одном месте: ~/.claude/.env")
    if (pr / ".git").exists():
        k, out = run(["git", "-C", str(pr), "ls-files", "--", "*.env", ".env"])
        if out.strip():
            bad(f"ключи попали в Git: {out.split()[0]}", "убрать из Git: git rm --cached <файл>, ключ на сайте сервиса заменить")
        else:
            ok("мозг хранится в Git, ключей в нём нет")
    else:
        tip("мозг пока без Git — бэкап и кнопка «отменить» появятся, когда подключим GitHub (урок 2)")


def klyuchi():
    env = CLAUDE / ".env"
    if not env.exists():
        bad("нет файла ключей ~/.claude/.env", "запустить install.py")
        return
    imena = [m.group(1) for m in re.finditer(r"^[ \t]*([A-Z][A-Z0-9_]*)[ \t]*=[ \t]*\S", env.read_text(encoding="utf-8", errors="ignore"), re.M)]
    imena = [i for i in imena if i != "UMNYI_BEZ_OBNOVLENIY"]
    ok(f"файл ключей на месте, заполнено: {', '.join(imena) if imena else 'пока ни одного (вставим по ходу курса)'}")


def obnovleniya():
    k, out = run([sys.executable, "-I", "-X", "utf8", str(ROOT / "obnovlenie.py"), "--proverka"], timeout=30)
    stroka = (out.strip().splitlines() or ["нет ответа"])[-1]
    if stroka.startswith("✓"):
        ok(stroka[2:])
    else:
        tip(stroka.lstrip("!✗ "))


def main():
    sistema()
    s = paket()
    pravila()
    pasport()
    nastroiki(s)
    navyki_i_pomoshchniki(s)
    mozg(s)
    klyuchi()
    obnovleniya()
    slomano = [x for x in itog if x[0] == "✗"]
    if "--json" in sys.argv:
        print(json.dumps([{"znak": z, "chto": t, "kak": k} for z, t, k in itog], ensure_ascii=False, indent=1))
    else:
        for z, t, k in itog:
            print(f"{z} {t}" + (f"\n    как починить: {k}" if k else ""))
        print()
        print("ВСЁ РАБОТАЕТ" if not slomano else f"ЕСТЬ ПРОБЛЕМЫ: {len(slomano)}")
        print("Последний шаг проверяет Claude: правила видны в новом чате (метка УМНЫЙ-CLAUDE).")
    return 1 if slomano else 0


if __name__ == "__main__":
    sys.exit(main())
