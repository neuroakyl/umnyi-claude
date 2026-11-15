"""Автообновление пакета «Умный Claude».

Без аргументов — режим хука SessionStart: раз в 6 часов при открытии нового чата тихо проверяет GitHub.
Есть новая версия — скачивает, ставит (install.py --tiho) и передаёт Claude, что нового, чтобы он сказал человеку одной строкой.
Нет интернета, слабая сеть, ошибка — молчит и пробует в следующий раз. Чат из-за обновления не ждёт дольше ~20 секунд.
  --seichas   обновить прямо сейчас, с выводом для человека (навык obnovit)
  --proverka  только сказать, есть ли обновление, ничего не менять (proverka.py)
Выключить: строка UMNYI_BEZ_OBNOVLENIY=1 в ~/.claude/.env.
Личные файлы человека не трогает: в папке пакета только код пакета, всё личное лежит в других местах.
"""
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLAUDE = Path.home() / ".claude"
SOST = CLAUDE / "umnyi-sostoyanie.json"
RAZ_V = 6 * 3600
SETEVOI_TAIMAUT = 20

seichas = "--seichas" in sys.argv
tolko_proverka = "--proverka" in sys.argv
hook = not (seichas or tolko_proverka)


def git(*args, timeout=10):
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0", LC_ALL="C")
    r = subprocess.run(["git", "-C", str(ROOT)] + list(args), capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=timeout, env=env)
    return r.returncode, (r.stdout or "").strip(), (r.stderr or "").strip()


def sost_read():
    try:
        return json.loads(SOST.read_text(encoding="utf-8"))
    except Exception:
        return {}


def sost_write(s):
    try:
        SOST.write_text(json.dumps(s, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except Exception:
        pass


def vyklyucheno():
    try:
        tekst = (CLAUDE / ".env").read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return False
    return re.search(r"^\s*UMNYI_BEZ_OBNOVLENIY\s*=\s*1\s*$", tekst, re.M) is not None


def versiya():
    try:
        return (ROOT / "VERSIYA").read_text(encoding="utf-8").strip()
    except Exception:
        return "?"


def chto_novogo(staraya):
    """Разделы ЧТО-НОВОГО.md новее старой версии («## 1.0.1 — дата»)."""
    try:
        tekst = (ROOT / "ЧТО-НОВОГО.md").read_text(encoding="utf-8")
    except Exception:
        return ""
    kuski = re.split(r"^## ", tekst, flags=re.M)[1:]
    nado = []
    for k in kuski:
        if k.split()[0] == staraya:
            break
        nado.append("## " + k.strip())
    return "\n".join(nado)[:1500]


def skazat(tekst):
    """Хук: передать Claude. Иначе: напечатать человеку."""
    if hook:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": tekst}},
                         ensure_ascii=False))
    else:
        print(tekst)


def main():
    if hook:
        try:
            sys.stdin.read()  # Claude Code передаёт данные о чате — нам не нужны
        except Exception:
            pass
        if vyklyucheno():
            return 0
    s = sost_read()
    if hook and time.time() - s.get("posl_proverka", 0) < RAZ_V:
        return 0
    if not (ROOT / ".git").exists():
        if not hook:
            print("✗ папка пакета не из Git — обновляться неоткуда. Поставь пакет заново по README.")
        return 0

    try:
        kod, _, err = git("fetch", "--quiet", "origin", timeout=SETEVOI_TAIMAUT)
    except subprocess.TimeoutExpired:
        kod, err = 1, "долго нет ответа (слабый интернет?)"
    except FileNotFoundError:
        kod, err = 1, "не найден git"
    if kod != 0:
        s["posl_proverka"] = int(time.time()) - RAZ_V + 3600  # без сети не тормозим каждый чат: снова через час
        sost_write(s)
        if not hook:
            print(f"! обновление не проверено: {err[:200] or 'нет связи с GitHub'}. Попробуем позже.")
        return 0
    s["posl_proverka"] = int(time.time())
    sost_write(s)

    _, moya, _ = git("rev-parse", "HEAD")
    kod, ego, _ = git("rev-parse", "@{u}")
    if kod != 0:
        _, ego, _ = git("rev-parse", "origin/main")
    if not ego or moya == ego:
        if not hook:
            print(f"✓ Умный Claude последней версии ({versiya()})")
        return 0
    if tolko_proverka:
        print("! есть обновление пакета — скажи «обнови Умный Claude»")
        return 0

    staraya = versiya()
    kod, _, err = git("reset", "--hard", "--quiet", ego)  # в папке пакета нет личного: берём версию с GitHub целиком
    if kod != 0:
        skazat(f"Умный Claude: обновление не встало ({err[:200]}). Скажи человеку одной строкой и предложи «обнови Умный Claude».")
        return 0
    r = subprocess.run([sys.executable, "-I", "-X", "utf8", str(ROOT / "install.py"), "--tiho"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
    novaya = versiya()
    if r.returncode != 0:
        skazat(f"Умный Claude обновился до {novaya}, но установка споткнулась:\n{(r.stdout + r.stderr)[-600:]}\n"
               "Почини сам по сообщению или запусти навык proverka. Человеку — одной строкой, что чинишь.")
        return 0
    novoe = chto_novogo(staraya) or "(список изменений пуст)"
    if hook:
        skazat(f"Пакет «Умный Claude» сам обновился: {staraya} → {novaya}. Скажи человеку одной строкой в начале ответа, "
               f"что нового, простыми словами. Новые правила полностью заработают со следующего чата.\n{novoe}")
    else:
        print(f"✓ Умный Claude обновлён: {staraya} → {novaya}\n{novoe}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # хук никогда не должен ломать открытие чата
        if not hook:
            print(f"✗ обновление: {e}")
        sys.exit(0)
