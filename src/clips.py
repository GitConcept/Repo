"""Cortes verticais (9:16) da live para o Instagram: 5 cortes de 60-90s só com legendas.

Padrão visual (inspirado no perfil do Gabriel):
  - GANCHO: texto grande, amarelo, em caixa alta, no topo, nos primeiros segundos;
  - DESTAQUE: frase-chave em texto médio, bold, amarelo, no meio do corte;
  - LEGENDA: palavras brancas com contorno preto, palavra falada em amarelo, embaixo.
Tudo em código (ffmpeg + faster-whisper), sem programa de edição.
"""
import os
import re
import shutil
import subprocess

# Ajuste fino do padrão visual num lugar só.
FONT = os.environ.get("CLIP_FONT", "Impact")
YELLOW = "&H0000C4FF&"  # ASS usa BGR: FFC400
WHITE = "&H00FFFFFF&"
BLACK = "&H00000000&"
RED = "&H004B4BFF&"
W, H = 1080, 1920
N_CLIPS = 5
MIN_S, MAX_S = 60.0, 90.0
HOOK_SECONDS = 3.5
HIGHLIGHT_SECONDS = 3.0
# Papo de abertura/encerramento da live não rende corte.
SKIP_START_S, SKIP_END_S = 180.0, 120.0

STOP = set("a o os as um uma de do da dos das e é em no na nos nas que com por para pra se mas ou já não sim eu você tu ele ela nós vocês isso isto essa esse aqui ali tá né então aí ta ne so só como mais muito ser ter foi vai vou tem tinha".split())
POWER = ("importante", "erro", "segredo", "verdade", "problema", "resultado", "dinheiro", "cliente", "vender",
         "venda", "estratégia", "método", "passo", "primeiro", "principal", "nunca", "sempre", "melhor",
         "pior", "precisa", "essencial", "cuidado", "dica", "regra", "chave", "diferença")


def ffmpeg_bin():
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def transcribe(path):
    """Lista de palavras {w, s, e} com tempos em segundos."""
    from faster_whisper import WhisperModel
    model = WhisperModel(os.environ.get("WHISPER_MODEL", "small"), compute_type="int8")
    segments, _ = model.transcribe(path, language="pt", word_timestamps=True, vad_filter=True)
    words = []
    for seg in segments:
        for w in seg.words or []:
            t = w.word.strip()
            if t:
                words.append({"w": t, "s": float(w.start), "e": float(w.end)})
    return words


def sentences(words):
    """Agrupa palavras em frases (pontuação final ou pausa longa)."""
    out, cur = [], []
    for i, w in enumerate(words):
        cur.append(w)
        gap = words[i + 1]["s"] - w["e"] if i + 1 < len(words) else 99
        if re.search(r"[.?!…]$", w["w"]) or gap > 0.9:
            out.append({"words": cur, "s": cur[0]["s"], "e": cur[-1]["e"]})
            cur = []
    if cur:
        out.append({"words": cur, "s": cur[0]["s"], "e": cur[-1]["e"]})
    return out


def _text(sents):
    return " ".join(w["w"] for s in sents for w in s["words"])


def _score(sents):
    words = [w["w"].lower().strip(".,?!…:;") for s in sents for w in s["words"]]
    if not words:
        return 0.0
    dur = sents[-1]["e"] - sents[0]["s"]
    content = [w for w in words if w not in STOP and len(w) > 3]
    density = len(words) / max(dur, 1)  # fala contínua, sem enrolação
    power = sum(1 for w in words if any(p in w for p in POWER))
    questions = sum(1 for s in sents if s["words"][-1]["w"].endswith("?"))
    return density * 2 + len(content) / len(words) * 3 + power * 0.4 + questions * 0.5


def choose_clips(sents, n=N_CLIPS):
    """Janelas de frases inteiras (60-90s), sem sobreposição, melhores primeiro."""
    total = sents[-1]["e"] if sents else 0
    cands = []
    for i, first in enumerate(sents):
        if first["s"] < SKIP_START_S or first["e"] > total - SKIP_END_S:
            continue
        for j in range(i, len(sents)):
            dur = sents[j]["e"] - first["s"]
            if dur > MAX_S:
                break
            if dur >= MIN_S:
                cands.append((_score(sents[i:j + 1]), i, j))
    cands.sort(reverse=True)
    chosen = []
    for _, i, j in cands:
        if all(j < a or i > b for _, a, b in chosen):
            chosen.append((0, i, j))
        if len(chosen) == n:
            break
    return sorted((i, j) for _, i, j in chosen)


def _hook(sents):
    """Gancho: a frase de abertura enxuta (até 7 palavras) ou a de maior 'força'."""
    best = max(sents[:3], key=lambda s: _score([s]))
    ws = [w["w"] for w in best["words"]]
    return " ".join(ws[:7]).strip(" ,;:") + ("…" if len(ws) > 7 else "")


def _highlight(sents):
    """Frase de destaque: a mais forte do miolo do corte, curta o bastante para caber."""
    mid = sents[1:-1] or sents
    ok = [s for s in mid if 4 <= len(s["words"]) <= 12 and s["s"] - sents[0]["s"] > HOOK_SECONDS + 2] or mid
    return max(ok, key=lambda s: _score([s]))


def _t(sec):
    sec = max(sec, 0)
    return f"{int(sec // 3600)}:{int(sec % 3600 // 60):02d}:{sec % 60:05.2f}"


def _wrap(text, width):
    lines, cur = [], ""
    for w in text.split():
        if cur and len(cur) + 1 + len(w) > width:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    return lines + ([cur] if cur else [])


def build_ass(sents, t0):
    """Legenda ASS do corte (tempos relativos ao início t0)."""
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 2

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Hook,{FONT},135,{YELLOW},{YELLOW},{BLACK},{BLACK},0,0,0,0,100,100,0,0,1,6,5,8,60,60,190,1
Style: Destaque,{FONT},96,{YELLOW},{YELLOW},{BLACK},{BLACK},0,0,0,0,100,100,0,0,1,6,4,5,70,70,0,1
Style: Legenda,{FONT},74,{WHITE},{WHITE},{BLACK},{BLACK},0,0,0,0,100,100,0,0,1,6,3,2,80,80,330,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    ev = []
    hook = _hook(sents)
    ev.append(f"Dialogue: 2,{_t(0.2)},{_t(HOOK_SECONDS)},Hook,,0,0,0,,{{\\fad(150,250)}}" + r"\N".join(_wrap(hook.upper(), 12)))
    hl = _highlight(sents)
    hs = hl["s"] - t0
    hl_txt = " ".join(w["w"] for w in hl["words"]).strip(" ,;:")
    ev.append(f"Dialogue: 2,{_t(hs)},{_t(hs + HIGHLIGHT_SECONDS)},Destaque,,0,0,0,,{{\\fad(150,200)}}" + r"\N".join(_wrap(hl_txt.upper(), 16)))

    words = [w for s in sents for w in s["words"]]
    # Blocos de até 4 palavras; dentro do bloco, a palavra falada fica amarela.
    for k in range(0, len(words), 4):
        block = words[k:k + 4]
        for idx, cur in enumerate(block):
            start = cur["s"] - t0
            end = (block[idx + 1]["s"] if idx + 1 < len(block) else cur["e"]) - t0
            end = max(end, start + 0.12)
            parts = []
            for m, w in enumerate(block):
                color = YELLOW if m == idx else WHITE
                parts.append(f"{{\\c{color}}}{w['w'].strip(' ,;:.')}")
            ev.append(f"Dialogue: 1,{_t(start)},{_t(end)},Legenda,,0,0,0,," + " ".join(parts))
    return head + "\n".join(ev) + "\n"


def render(src, out, t0, t1, ass_path):
    """Corta [t0, t1], deixa 9:16 (vídeo centralizado sobre fundo desfocado) e queima as legendas."""
    ass = ass_path.replace("\\", "/").replace(":", r"\:").replace("'", r"\'")
    vf = (f"[0:v]split[a][b];"
          f"[a]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},boxblur=40:6,eq=brightness=-0.12[bg];"
          f"[b]scale={W}:-2[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2,ass='{ass}'[v]")
    cmd = [ffmpeg_bin(), "-y", "-loglevel", "error", "-ss", f"{t0:.2f}", "-i", src, "-t", f"{t1 - t0:.2f}",
           "-filter_complex", vf, "-map", "[v]", "-map", "0:a:0",
           "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p", "-r", "30",
           "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", out]
    subprocess.run(cmd, check=True)


def make_clips(src, out_dir, n=N_CLIPS):
    """Gera os cortes e devolve a lista de arquivos."""
    os.makedirs(out_dir, exist_ok=True)
    print("Transcrevendo a live (pode levar alguns minutos)...")
    sents = sentences(transcribe(src))
    picks = choose_clips(sents, n)
    print(f"{len(picks)} cortes escolhidos.")
    files = []
    for num, (i, j) in enumerate(picks, 1):
        part = sents[i:j + 1]
        t0, t1 = part[0]["s"] - 0.2, part[-1]["e"] + 0.4
        base = os.path.join(out_dir, f"corte-{num}")
        with open(base + ".ass", "w", encoding="utf-8") as f:
            f.write(build_ass(part, t0))
        render(src, base + ".mp4", t0, t1, base + ".ass")
        with open(base + ".txt", "w", encoding="utf-8") as f:
            f.write(f"Gancho: {_hook(part)}\nTrecho: {t0:.0f}s a {t1:.0f}s ({t1 - t0:.0f}s)\n\n{_text(part)}\n")
        os.remove(base + ".ass")
        print(f"  corte {num}: {t1 - t0:.0f}s -> {base}.mp4")
        files.append(base + ".mp4")
    return files


if __name__ == "__main__":
    import sys
    make_clips(sys.argv[1], sys.argv[2])
