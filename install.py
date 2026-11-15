"""Установщик пакета «Умный Claude». Mac и Windows, Python 3.8+, без сторонних библиотек.

Запуск (его делает Claude): sh "$HOME/.claude/umnyi/bin/py" "$HOME/.claude/umnyi/install.py"
  --tiho      меньше вывода (так зовёт автообновление)
  --proekty   другая папка цифрового мозга (по умолчанию ~/Projects)

Что делает (можно запускать сколько угодно раз, результат тот же):
  правила   -> ~/.claude/rules/umnyi-*.md       (пакетные заменяются, свои moi-pravila.md не трогаются)
  навыки    -> ~/.claude/skills/<имя>/            (только пакетные; свой навык с тем же именем не перезаписывается)
  помощники -> ~/.claude/agents/<имя>.md
  паспорт   -> ~/.claude/CLAUDE.md               (только если его нет)
  ключи     -> ~/.claude/.env                    (только если его нет)
  мозг      -> ~/Projects/...                    (папки и файлы-основы, существующее не трогается)
  настройки -> ~/.claude/settings.json           (пакетные строки дописываются, чужие не трогаются, копия до правки)
"""
import json
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
HOME = Path.home()
CLAUDE = HOME / ".claude"
SOST = CLAUDE / "umnyi-sostoyanie.json"
METKA_HUKA = "/.claude/umnyi/"
PAPKI = ["мозг/бренд", "материалы/входящие", "материалы/расшифровки", "завод", "проекты"]

tiho = "--tiho" in sys.argv
soobshcheniya = []


def say(znak, tekst):
    soobshcheniya.append((znak, tekst))
    if not tiho or znak == "✗":
        print(f"{znak} {tekst}")


def read_json(p, default):
    if not p.exists():
        return default
    try:
        return json.loads(p.read_text(encoding="utf-8-sig"))
    except Exception:
        return None


def write_json(p, data):
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(p)


def copy_dir(src, dst):
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", ".DS_Store"))


def proekty_path():
    if "--proekty" in sys.argv:
        i = sys.argv.index("--proekty")
        return Path(sys.argv[i + 1]).expanduser()
    return HOME / "Projects"


# ---------- части ----------

def ustanovit_pravila(sost):
    d = CLAUDE / "rules"
    d.mkdir(parents=True, exist_ok=True)
    nashi = sorted(p.name for p in (ROOT / "rules").glob("umnyi-*.md"))
    for name in nashi:
        shutil.copyfile(ROOT / "rules" / name, d / name)
    for p in d.glob("umnyi-*.md"):  # старые правила пакета, которых больше нет
        if p.name not in nashi:
            p.unlink()
    moi = d / "moi-pravila.md"
    if not moi.exists():
        shutil.copyfile(ROOT / "shablony" / "moi-pravila.md", moi)
    say("✓", f"правила работы: {len(nashi)} файла в ~/.claude/rules/ (+ твой moi-pravila.md)")


def ustanovit_po_spisku(sost, vid):
    """vid = 'skills' (папки) или 'agents' (файлы .md)."""
    dst_root = CLAUDE / vid
    dst_root.mkdir(parents=True, exist_ok=True)
    byli = set(sost.get(vid, []))
    if vid == "skills":
        nashi = sorted(p.name for p in (ROOT / vid).iterdir() if (p / "SKILL.md").exists())
    else:
        nashi = sorted(p.name for p in (ROOT / vid).glob("*.md"))
    postavleno, propushcheno = [], []
    for name in nashi:
        dst = dst_root / name
        if dst.exists() and name not in byli:
            propushcheno.append(name)  # у человека свой с таким именем — не трогаем
            continue
        if vid == "skills":
            copy_dir(ROOT / vid / name, dst)
        else:
            shutil.copyfile(ROOT / vid / name, dst)
        postavleno.append(name)
    for name in byli - set(nashi):  # убрали из пакета — убираем и у человека
        p = dst_root / name
        if p.is_dir():
            shutil.rmtree(p)
        elif p.exists():
            p.unlink()
    sost[vid] = postavleno
    imya = "навыки" if vid == "skills" else "помощники"
    spisok = ", ".join(n.replace(".md", "") for n in postavleno)
    say("✓", f"{imya}: {spisok}")
    for name in propushcheno:
        say("!", f"{imya}: «{name}» уже есть свой, пакетный не ставлю")


def ustanovit_osnovy(proekty):
    pasport = CLAUDE / "CLAUDE.md"
    if not pasport.exists():
        shutil.copyfile(ROOT / "shablony" / "pasport.md", pasport)
        say("✓", "паспорт: создан шаблон ~/.claude/CLAUDE.md (заполним по интервью)")
    else:
        say("✓", "паспорт: уже есть, не трогаю")

    env = CLAUDE / ".env"
    if not env.exists():
        shutil.copyfile(ROOT / "shablony" / "env.txt", env)
        say("✓", "ключи: создан пустой ~/.claude/.env")
    else:
        say("✓", "ключи: ~/.claude/.env уже есть, не трогаю")

    proekty.mkdir(parents=True, exist_ok=True)
    for p in PAPKI:
        (proekty / p).mkdir(parents=True, exist_ok=True)
    for src, name in (("projects-CLAUDE.md", "CLAUDE.md"), ("zadachi.md", "Задачи.md")):
        if not (proekty / name).exists():
            shutil.copyfile(ROOT / "shablony" / src, proekty / name)
    gi = proekty / ".gitignore"
    if not gi.exists():
        shutil.copyfile(ROOT / "shablony" / "gitignore", gi)
    elif ".env" not in gi.read_text(encoding="utf-8", errors="ignore").split():
        with gi.open("a", encoding="utf-8") as f:
            f.write("\n# Ключи — никогда в Git\n.env\n*.env\n")
    say("✓", f"цифровой мозг: папка {proekty} (мозг, материалы, завод, проекты)")


def slit_spisok(cur, new, old):
    cur = [x for x in (cur or []) if not (x in old and x not in new)]
    for x in new:
        if x not in cur:
            cur.append(x)
    return cur


def podstavit(obj, zamena):
    if isinstance(obj, str):
        for k, v in zamena.items():
            obj = obj.replace(k, v)
        return obj
    if isinstance(obj, list):
        return [podstavit(x, zamena) for x in obj]
    if isinstance(obj, dict):
        return {k: podstavit(v, zamena) for k, v in obj.items() if not k.startswith("_")}
    return obj


def nash_huk(gruppa):
    return any(METKA_HUKA in h.get("command", "").replace("\\", "/") for h in gruppa.get("hooks", []))


def vlit_nastroiki(sost, proekty):
    put = CLAUDE / "settings.json"
    s = read_json(put, {})
    if s is None:
        say("✗", "настройки: ~/.claude/settings.json испорчен (не JSON). Не трогаю. Как починить: попроси Claude «почини settings.json»")
        return False
    if put.exists():
        shutil.copyfile(put, CLAUDE / "settings.json.umnyi-kopiya")
    pkg = podstavit(json.loads((ROOT / "nastroiki" / "paket.json").read_text(encoding="utf-8")),
                    {"{HOME}": HOME.as_posix(), "{PROJECTS}": proekty.as_posix()})
    staroe = sost.get("nastroiki", {})
    novoe = {}

    perms = s.setdefault("permissions", {})
    for key in ("allow", "deny", "ask", "additionalDirectories"):
        new = pkg["permissions"].get(key, [])
        perms[key] = slit_spisok(perms.get(key), new, staroe.get(key, []))
        if not perms[key]:
            del perms[key]
        novoe[key] = new
    if perms.get("defaultMode") in (None, "default", "manual", "acceptEdits"):
        perms["defaultMode"] = pkg["permissions"]["defaultMode"]

    am = s.setdefault("autoMode", {})
    new = pkg["autoMode"]["environment"]
    env_list = slit_spisok(am.get("environment"), new, staroe.get("environment", []))
    if "$defaults" in env_list:  # «$defaults» всегда первым, иначе пропадут встроенные правила
        env_list.remove("$defaults")
    am["environment"] = ["$defaults"] + env_list
    novoe["environment"] = new

    env = s.setdefault("env", {})
    for k, v in pkg["env"].items():
        env.setdefault(k, v)

    hooks = s.setdefault("hooks", {})
    for event in list(hooks):
        hooks[event] = [g for g in hooks[event] if not nash_huk(g)]
        if not hooks[event]:
            del hooks[event]
    for event, gruppy in pkg["hooks"].items():
        hooks.setdefault(event, []).extend(gruppy)

    if s.get("autoMemoryEnabled") is False:
        say("!", "память Claude выключена (autoMemoryEnabled: false) — включи в /memory, если это не нарочно")

    write_json(put, s)
    sost["nastroiki"] = novoe
    say("✓", f"настройки: автономный режим «{perms['defaultMode']}», запрет читать .env, автообновление при открытии чата")
    return True


def main():
    if sys.version_info < (3, 8):
        print("✗ нужен Python 3.8 или новее")
        return 1
    if ROOT != (CLAUDE / "umnyi").resolve():
        say("!", f"пакет лежит в {ROOT}, а должен в ~/.claude/umnyi — автообновление и навыки ищут его там")
    CLAUDE.mkdir(parents=True, exist_ok=True)
    proekty = proekty_path()
    sost = read_json(SOST, {}) or {}
    ustanovit_pravila(sost)
    ustanovit_po_spisku(sost, "skills")
    ustanovit_po_spisku(sost, "agents")
    ustanovit_osnovy(proekty)
    ok = vlit_nastroiki(sost, proekty)
    sost["versiya"] = (ROOT / "VERSIYA").read_text(encoding="utf-8").strip()
    sost["proekty"] = proekty.as_posix()
    sost["ustanovleno"] = int(time.time())
    write_json(SOST, sost)
    if not tiho:
        print(f"\nУмный Claude {sost['versiya']} поставлен. Дальше: проверка (proverka.py) и новый чат — правила начнут работать в нём.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
