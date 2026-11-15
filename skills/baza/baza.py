"""База о себе (цифровой мозг): заготовка, «что осталось», расшифровка записей. Mac и Windows, Python 3.8+, без установки пакетов.

Запуск: sh "$HOME/.claude/umnyi/bin/py" "$HOME/.claude/skills/baza/baza.py" <команда>
  zagotovka                 создать в Projects/мозг недостающие файлы с полями (существующее не трогает)
  ostalos                   что пусто: поля ★, истории, эталоны, паспорт; готов ли мозг
  rasshifrovat <файл|ссылка|папка> ... [--yazyk ky|ru|kk|auto] [--servis gemini|elevenlabs] [--model имя]
                            аудио и видео → текст в Projects/материалы/расшифровки/ГГГГ-ММ-ДД-<имя>.md
  voprosy [ky]              открыть страницу вопросов для длинной записи и вывести список
  rasshifrovat --novye      всё новое из Projects/материалы/входящие (уже расшифрованное пропускает)

Ключи: переменная окружения → ~/.claude/.env (GEMINI_API_KEY — основной, ELEVENLABS_API_KEY — запасной).
Ключ в вывод не попадает. Источник: пакет «Умный Claude», 15.11.2026.
"""
import datetime
import json
import mimetypes
import os
import re
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
HOME = Path.home()
CLAUDE = HOME / ".claude"
AUDIO = {".mp3", ".m4a", ".wav", ".ogg", ".oga", ".opus", ".aac", ".flac", ".webm", ".aiff", ".amr", ".3gp",
         ".mp4", ".mov", ".mkv", ".avi", ".m4v"}
MIME = {".m4a": "audio/m4a", ".mp3": "audio/mp3", ".wav": "audio/wav", ".ogg": "audio/ogg", ".oga": "audio/ogg",
        ".opus": "audio/opus", ".aac": "audio/aac", ".flac": "audio/flac", ".webm": "audio/webm", ".aiff": "audio/aiff",
        ".amr": "audio/amr", ".3gp": "video/3gpp", ".mp4": "video/mp4", ".mov": "video/quicktime", ".mkv": "video/x-matroska",
        ".avi": "video/x-msvideo", ".m4v": "video/mp4"}
YAZYK = {"ky": "кыргызском", "ru": "русском", "kk": "казахском"}
GEMINI_MODELI = ["gemini-3.8-flash", "gemini-3.6-flash", "gemini-3.5-flash", "gemini-2.5-flash"]  # по порядку, первая доступная


def proekty():
    try:
        s = json.loads((CLAUDE / "umnyi-sostoyanie.json").read_text(encoding="utf-8"))
        if s.get("proekty"):
            return Path(s["proekty"])
    except Exception:
        pass
    return HOME / "Projects"


def stop(t):
    print(t)
    sys.exit(1)


# ---------- заготовка и «что осталось» ----------

def shablony():
    """shablon-mozga.md → {имя файла: текст}."""
    t = (HERE / "shablon-mozga.md").read_text(encoding="utf-8")
    chasti = re.split(r"^=== (\S+\.md) ===\s*$", t, flags=re.M)
    return {chasti[i]: chasti[i + 1].strip() + "\n" for i in range(1, len(chasti), 2)}


def zagotovka():
    mozg = proekty() / "мозг"
    (mozg / "бренд").mkdir(parents=True, exist_ok=True)
    novye = []
    for imya, tekst in shablony().items():
        f = mozg / imya
        if not f.exists():
            f.write_text(tekst, encoding="utf-8")
            novye.append(imya)
    print(f"Мозг: {mozg}")
    print("Создано: " + (", ".join(novye) if novye else "ничего, все 12 файлов уже есть (не трогал)"))


def polya(tekst):
    """{## Поле: содержимое до следующего ##}."""
    out = {}
    for m in re.finditer(r"^## (.+?)\s*$\n(.*?)(?=^## |\Z)", tekst, flags=re.M | re.S):
        out[m.group(1).strip()] = m.group(2).strip()
    return out


def pusto(s):
    s = re.sub(r"<!--.*?-->", "", s, flags=re.S).strip()
    return not s or s.startswith("— (спросить") or s == "—"


ZVEZDY = {"кто-я.md": ["Ниша", "Доказательства", "Границы личного"],
          "продукт.md": ["Лестница", "Главный продукт", "Как купить", "Кодовые слова"],
          "позиция.md": ["Обещание", "Рубрики"],
          "голос.md": ["Эталоны"],
          "бренд.md": ["Цвета", "Шрифты"],
          "площадки.md": ["Аккаунты", "Ссылка в шапке", "Норма"]}


def ostalos():
    mozg = proekty() / "мозг"
    if not mozg.exists():
        stop("Мозга ещё нет. Сначала: baza.py zagotovka")
    net_zvezd, vsego_pusto = [], {}
    for imya in shablony():
        f = mozg / imya
        if not f.exists():
            net_zvezd.append(f"{imya}: файла нет")
            continue
        t = f.read_text(encoding="utf-8", errors="ignore")
        p = polya(t)
        pustye = [k for k, v in p.items() if pusto(v) and not k.startswith("Сегмент")] if imya != "истории.md" else []
        if pustye:
            vsego_pusto[imya] = pustye
        for z in ZVEZDY.get(imya, []):
            if z not in p or pusto(p[z]):
                net_zvezd.append(f"{imya} → {z}")
        if imya == "аудитория.md":
            segs = [v for k, v in p.items() if k.startswith("Сегмент") and "(имя)" not in k]
            def est(v, pole):
                m = re.search(rf"^- {pole}:\s*(.*)$", v, flags=re.M)
                return bool(m) and not pusto(m.group(1))
            if not any(est(v, "Кто") and est(v, "Боли") for v in segs):
                net_zvezd.append("аудитория.md → хотя бы один сегмент с «Кто» и «Боли»")
    ist = mozg / "истории.md"
    n_ist = len(re.findall(r"^## ", ist.read_text(encoding="utf-8"), flags=re.M)) if ist.exists() else 0
    gol = mozg / "голос.md"
    n_et = len(re.findall(r"^### ", gol.read_text(encoding="utf-8"), flags=re.M)) if gol.exists() else 0
    pas = CLAUDE / "CLAUDE.md"
    # «— (заполнить)» в кавычках-ёлочках — пояснение шаблона, а не пустое поле
    n_pas = len(re.findall(r"(?<!«)— \(заполнить", pas.read_text(encoding="utf-8", errors="ignore"))) if pas.exists() else -1

    print(f"Мозг: {mozg}")
    print(f"Без этого завод не стартует (★), пусто: {len(net_zvezd)}")
    for z in net_zvezd:
        print(f"  ★ {z}")
    print(f"Истории: {n_ist} из 5 минимум" + (" ✓" if n_ist >= 5 else ""))
    print(f"Эталоны голоса: {n_et} из 3 минимум" + (" ✓" if n_et >= 3 else ""))
    print("Паспорт: " + ("нет файла" if n_pas < 0 else "заполнен ✓" if n_pas == 0 else f"не заполнено полей: {n_pas}"))
    if vsego_pusto:
        print("Остальное пустое (дозаполним по ходу):")
        for imya, pp in vsego_pusto.items():
            print(f"  {imya}: {', '.join(pp)}")
    gotov = not net_zvezd and n_ist >= 5 and n_et >= 3 and n_pas == 0
    print("ИТОГ: " + ("МОЗГ ГОТОВ — проверка «напиши пост про меня»" if gotov else "мозг не готов, спросить то, что выше"))


# ---------- ключи и сеть ----------

def klyuch(imya):
    if os.environ.get(imya):
        return os.environ[imya].strip()
    env = CLAUDE / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8", errors="ignore").splitlines():
            m = re.match(rf"^\s*{imya}\s*=\s*(.*?)\s*$", line)
            if m and m.group(1).strip("\"'"):
                return m.group(1).strip("\"'")
    return ""


def http(url, data=None, headers=None, method=None, timeout=120):
    req = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read(), dict(r.headers)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "ignore")[:400]
        raise RuntimeError(f"HTTP {e.code}: {body}") from None


# ---------- Gemini ----------

def gemini_model(key, zhelaemaya):
    if zhelaemaya:
        return zhelaemaya
    try:
        raw, _ = http("https://generativelanguage.googleapis.com/v1beta/models?pageSize=1000", headers={"x-goog-api-key": key}, timeout=30)
        est = {m["name"].split("/")[-1] for m in json.loads(raw).get("models", [])
               if "generateContent" in m.get("supportedGenerationMethods", [])}
    except Exception:
        return GEMINI_MODELI[0]
    for m in GEMINI_MODELI:
        if m in est:
            return m
    flash = sorted((m for m in est if re.fullmatch(r"gemini-[\d.]+-flash", m)), key=lambda x: [float(c) for c in re.findall(r"[\d.]+", x)[0].split(".")[:2]])
    return flash[-1] if flash else GEMINI_MODELI[0]


def gemini_zagruzit(key, put, mime):
    """Files API: любой размер (до 2 ГБ). Возвращает file_uri."""
    razmer = put.stat().st_size
    _, h = http("https://generativelanguage.googleapis.com/upload/v1beta/files", method="POST",
                data=json.dumps({"file": {"display_name": "zapis"}}).encode(),
                headers={"x-goog-api-key": key, "X-Goog-Upload-Protocol": "resumable", "X-Goog-Upload-Command": "start",
                         "X-Goog-Upload-Header-Content-Length": str(razmer), "X-Goog-Upload-Header-Content-Type": mime,
                         "Content-Type": "application/json"})
    url = {k.lower(): v for k, v in h.items()}.get("x-goog-upload-url")
    if not url:
        raise RuntimeError("Gemini не дал адрес для загрузки")
    raw, _ = http(url, data=put.read_bytes(), method="POST", timeout=900,
                  headers={"Content-Length": str(razmer), "X-Goog-Upload-Offset": "0", "X-Goog-Upload-Command": "upload, finalize"})
    f = json.loads(raw)["file"]
    for _ in range(120):  # видео и длинное аудио Google готовит не сразу
        if f.get("state") in (None, "ACTIVE"):
            return f["uri"]
        if f.get("state") == "FAILED":
            raise RuntimeError("Gemini не смог прочитать файл")
        time.sleep(5)
        raw, _ = http(f"https://generativelanguage.googleapis.com/v1beta/{f['name']}", headers={"x-goog-api-key": key}, timeout=30)
        f = json.loads(raw)
    raise RuntimeError("Gemini слишком долго готовит файл")


def prompt(yazyk):
    ya = YAZYK.get(yazyk)
    return ("Сделай дословную расшифровку речи из этой записи. "
            + (f"Человек говорит в основном на {ya} языке. " if ya else "Язык определи сам: обычно это кыргызский, русский или казахский, часто вперемешку. ")
            + "Пиши каждое слово на том языке, на котором оно сказано: ничего не переводи, не исправляй и не пересказывай. "
              "Кыргызские и казахские буквы (ң, ө, ү, ә, ғ, қ, ұ, һ, і) пиши правильно. Разбей на абзацы по смыслу. "
              "Если человек называет номер вопроса («Вопрос один», «Вопрос 5», «Биринчи суроо», «Бешинчи суроо», «Суроо 3», «Сұрақ 2»), "
              "начинай с этого места новую строку `## Вопрос N` (N цифрой). Неразборчивое место пометь [неразборчиво]. "
              "Если речи нет, ответь одним словом: БЕЗ РЕЧИ. Выведи только текст расшифровки, без вступлений.")


def gemini(put, yazyk, model):
    key = klyuch("GEMINI_API_KEY")
    if not key:
        raise LookupError("GEMINI_API_KEY")
    model = gemini_model(key, model)
    mime = MIME.get(put.suffix.lower()) or mimetypes.guess_type(put.name)[0] or "audio/mpeg"
    if put.stat().st_size < 15_000_000:
        import base64
        chast = {"inline_data": {"mime_type": mime, "data": base64.b64encode(put.read_bytes()).decode()}}
    else:
        chast = {"file_data": {"mime_type": mime, "file_uri": gemini_zagruzit(key, put, mime)}}
    body = {"contents": [{"parts": [chast, {"text": prompt(yazyk)}]}],
            "generationConfig": {"temperature": 0, "maxOutputTokens": 65000}}
    raw, _ = http(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent", method="POST",
                  data=json.dumps(body).encode(), headers={"x-goog-api-key": key, "Content-Type": "application/json"}, timeout=1200)
    d = json.loads(raw)
    try:
        tekst = "".join(p.get("text", "") for p in d["candidates"][0]["content"]["parts"])
    except (KeyError, IndexError):
        raise RuntimeError("Gemini вернул пустой ответ: " + json.dumps(d, ensure_ascii=False)[:300])
    obrezano = d["candidates"][0].get("finishReason") == "MAX_TOKENS"
    return tekst.strip(), f"Gemini {model}" + (" (ОБРЕЗАНО: запись слишком длинная, разрежь на части)" if obrezano else "")


# ---------- ElevenLabs (запасной) ----------

def elevenlabs(put, yazyk, model):
    key = klyuch("ELEVENLABS_API_KEY")
    if not key:
        raise LookupError("ELEVENLABS_API_KEY")
    model = model or "scribe_v2"
    gran = uuid.uuid4().hex
    chasti = [("model_id", model)] + ([("language_code", yazyk)] if yazyk in YAZYK else [])
    body = b"".join(f"--{gran}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode() for k, v in chasti)
    mime = MIME.get(put.suffix.lower()) or "application/octet-stream"
    body += (f"--{gran}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"zapis{put.suffix.lower()}\"\r\n"
             f"Content-Type: {mime}\r\n\r\n").encode() + put.read_bytes() + f"\r\n--{gran}--\r\n".encode()
    raw, _ = http("https://api.elevenlabs.io/v1/speech-to-text", method="POST", data=body, timeout=1800,
                  headers={"xi-api-key": key, "Content-Type": f"multipart/form-data; boundary={gran}"})
    d = json.loads(raw)
    return (d.get("text") or "").strip(), f"ElevenLabs {model}"


# ---------- расшифровка ----------

def skachat(url):
    imya = Path(urllib.parse.urlparse(url).path).name or "zapis.mp4"
    if Path(imya).suffix.lower() not in AUDIO:
        imya += ".mp4"
    put = Path(tempfile.mkdtemp()) / imya
    raw, _ = http(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=300)
    put.write_bytes(raw)
    return put


def imya_rasshifrovki(istochnik):
    stem = re.sub(r"[^\w\-]+", "-", Path(urllib.parse.urlparse(istochnik).path).stem if "://" in istochnik else Path(istochnik).stem).strip("-")
    return stem[:60] or "zapis"


def uzhe_est(kuda, stem):
    return any(kuda.glob(f"*-{stem}.md"))


def rasshifrovat(args):
    yazyk = arg(args, "--yazyk", "auto")
    servis = arg(args, "--servis", "")
    model = arg(args, "--model", "")
    kuda = Path(arg(args, "--kuda", str(proekty() / "материалы" / "расшифровки"))).expanduser()
    kuda.mkdir(parents=True, exist_ok=True)
    celi = []
    if "--novye" in args:
        vh = proekty() / "материалы" / "входящие"
        celi = [str(p) for p in sorted(vh.rglob("*")) if p.is_file() and p.suffix.lower() in AUDIO and not uzhe_est(kuda, imya_rasshifrovki(str(p)))]
        if not celi:
            print("Во входящих нет новых аудио и видео: всё уже расшифровано.")
            return
    znacheniya = {args[i + 1] for i, x in enumerate(args[:-1]) if x in ("--yazyk", "--servis", "--model", "--kuda")}
    for a in [a for a in args if not a.startswith("--") and a not in znacheniya]:
        p = Path(a).expanduser()
        if p.is_dir():
            celi += [str(x) for x in sorted(p.rglob("*")) if x.is_file() and x.suffix.lower() in AUDIO]
        else:
            celi.append(a)
    if not celi:
        stop("Не указан файл. Пример: baza.py rasshifrovat «путь к записи» --yazyk ky")
    sdelano, oshibki = [], []
    for c in celi:
        try:
            put = skachat(c) if "://" in c else Path(c).expanduser()
            if not put.exists():
                raise RuntimeError("файла нет")
            mb = put.stat().st_size / 1e6
            print(f"Расшифровываю: {Path(c).name if '://' not in c else c[:60]} ({mb:.1f} МБ)…", flush=True)
            poryadok = [servis] if servis else ["gemini", "elevenlabs"]
            tekst, kto, prichiny = "", "", []
            for s in poryadok:
                try:
                    tekst, kto = (gemini if s == "gemini" else elevenlabs)(put, yazyk, model if servis else "")
                    if tekst:
                        break
                except LookupError as e:
                    prichiny.append(f"нет ключа {e.args[0]}")
                except Exception as e:
                    prichiny.append(f"{s}: {e}")
            if not tekst:
                raise RuntimeError("; ".join(prichiny) or "пустой ответ")
            data = datetime.date.today().isoformat()
            f = kuda / f"{data}-{imya_rasshifrovki(c)}.md"
            f.write_text(f"# Расшифровка: {Path(c).name if '://' not in c else c}\n\n"
                         f"Дата: {data} · Источник: {c} · Расшифровал: {kto} · Язык: {yazyk}\n"
                         f"Машинная расшифровка: имена, цифры и редкие слова сверить с человеком.\n\n{tekst}\n", encoding="utf-8")
            slov = len(tekst.split())
            sdelano.append(f)
            print(f"  ✓ {f.name}: {slov} слов · {kto}")
        except Exception as e:
            oshibki.append(f"{c}: {e}")
            print(f"  ✗ {c}: {e}")
    print(f"Готово: {len(sdelano)}, ошибок: {len(oshibki)}. Папка: {kuda}")
    if oshibki and all("нет ключа" in o for o in oshibki):
        print("Нужен ключ: GEMINI_API_KEY (бесплатно, aistudio.google.com/apikey) в ~/.claude/.env")
    sys.exit(1 if oshibki and not sdelano else 0)


def arg(args, imya, default):
    return args[args.index(imya) + 1] if imya in args and args.index(imya) + 1 < len(args) else default


def main():
    a = sys.argv[1:]
    if not a or a[0] in ("-h", "--help", "pomosh"):
        print(__doc__)
        return
    k = a[0]
    if k == "zagotovka":
        zagotovka()
    elif k == "ostalos":
        ostalos()
    elif k == "rasshifrovat":
        rasshifrovat(a[1:])
    elif k == "voprosy":
        voprosy(a[1] if len(a) > 1 else "ru")
    else:
        stop(f"Не знаю команду {k}. Есть: zagotovka, ostalos, rasshifrovat, voprosy")


def voprosy(yazyk):
    """Открыть страницу вопросов для длинной записи и вывести список."""
    import webbrowser
    stranica = HERE / "voprosy-zapis.html"
    t = stranica.read_text(encoding="utf-8")
    blok = re.search(rf"^{'ky' if yazyk == 'ky' else 'ru'}: \[(.*?)^\]", t, flags=re.M | re.S).group(1)
    spisok = re.findall(r'^\s*"(.+)",?\s*$', blok, flags=re.M)
    otkryto = webbrowser.open(stranica.as_uri() + ("#ky" if yazyk == "ky" else ""))
    print(("Открыл в браузере: " if otkryto else "Браузер не открылся, открой вручную: ") + str(stranica))
    slovo = "Суроо" if yazyk == "ky" else "Вопрос"
    for n, q in enumerate(spisok, 1):
        print(f"{slovo} {n}. {q}")


if __name__ == "__main__":
    main()
