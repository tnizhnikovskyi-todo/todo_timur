#!/usr/bin/env python3
"""Автоперевірки відео A-21c (VID-*). stdlib + ffprobe/ffmpeg. Вивід: JSON [{id,status,msg}]; код виходу 1, якщо є FAIL.
Використання: check_video.py <prototype-real/video> [--intake OWNER-INTAKE.md] [--sample] [--no-frames] [--frames-out DIR]
VID-format — формати за анкетою materials.formats: video_16x9 -> *-16x9.mp4 (H.264, 1920x1080, ~30 fps, 180–240 с), reels_9x16 -> *-9x16.mp4 (1080x1920, 55–60 с),
             mobile -> у captions.yaml є фрагмент type: phone|reel (WARN, решта — MANUAL: очима), one_pager -> SHOW.md|html|pdf поруч із video/. --sample: 10–20 с (зразок N-18, файли sample-*).
VID-freeze — ffmpeg freezedetect (n=-55dB, d=2): жодного статичного фрагмента довше 2 с (заставки теж анімовані).
VID-frames — кадри для рецензента (0, 1, 3 с і далі кожні 2 с, останній) у video/frames/<файл>-<t>s.jpg + перевірка перших/останніх 5 с: майже білий кадр (YAVG>235) = FAIL.
Без ffprobe/ffmpeg перевірки -> SKIP з поясненням (не PASS)."""
import argparse, glob, json, os, re, shutil, subprocess, sys

res = []
def add(i, status, msg=""): res.append({"id": i, "status": status, "msg": msg})

def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)

def probe(f):
    r = run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=codec_name,width,height,r_frame_rate:format=duration", "-of", "json", f])
    if r.returncode: return None
    j = json.loads(r.stdout); s = (j.get("streams") or [{}])[0]
    n, _, d = (s.get("r_frame_rate") or "0/1").partition("/")
    fps = float(n) / float(d or 1) if float(d or 1) else 0
    return {"codec": s.get("codec_name"), "w": s.get("width"), "h": s.get("height"), "fps": fps, "dur": float(j.get("format", {}).get("duration") or 0)}

def has_audio(f):
    return bool(run(["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries", "stream=codec_name", "-of", "csv=p=0", f]).stdout.strip())

def intake_formats(path):
    """Рядковий `formats: [a, b]` або блоковий список `formats:` + `- a`; коментарі в рядках відкидаються."""
    if not path or not os.path.exists(path): return None
    t = open(path, encoding="utf-8").read()
    m = re.search(r"formats:[ \t]*\[([^\]]*)\]", t)
    if m: fm = [re.sub(r"\s+#.*$", "", x).strip().strip("'\"") for x in m.group(1).split(",") if x.strip()]
    else:
        m = re.search(r"(?m)^([ \t]*)formats:[ \t]*(?:#.*)?\n((?:[ \t]*-[ \t]*[^\n]*\n?)+)", t)
        fm = [re.sub(r"\s+#.*$", "", x.strip()[1:]).strip().strip("'\"") for x in m.group(2).splitlines() if x.strip().startswith("-")] if m else []
    return [x for x in fm if x] or None

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("video"); ap.add_argument("--intake"); ap.add_argument("--sample", action="store_true")
    ap.add_argument("--no-frames", action="store_true"); ap.add_argument("--frames-out")
    a = ap.parse_args(); vd = a.video.rstrip("/")
    if not shutil.which("ffprobe") or not shutil.which("ffmpeg"):
        for i in ("VID-format", "VID-freeze", "VID-frames"): add(i, "SKIP", "ffprobe/ffmpeg недоступні — не перевірено")
        return out()
    if not os.path.isdir(vd):
        add("VID-format", "FAIL", f"немає теки {vd}"); return out()
    if a.intake and not os.path.isfile(a.intake):
        add("VID-format", "FAIL", f"--intake {a.intake}: файла немає (шлях — docs/industries/<галузь>/OWNER-INTAKE.md від кореня репо)"); return out()
    fm = intake_formats(a.intake)
    if fm is None:
        add("VID-format", "WARN", "анкета без materials.formats — беру video_16x9, reels_9x16" if a.intake else "--intake не задано — беру video_16x9, reels_9x16"); fm = ["video_16x9", "reels_9x16"]
    parent = os.path.dirname(os.path.abspath(vd)); pref = "sample-" if a.sample else ""
    spec = {"video_16x9": ("16x9", 1920, 1080, (10, 20) if a.sample else (180, 240)), "reels_9x16": ("9x16", 1080, 1920, (10, 20) if a.sample else (55, 60))}
    videos = []
    for f in fm:
        if f in spec:
            suf, W, H, (lo, hi) = spec[f]
            cands = [p for p in sorted(glob.glob(os.path.join(vd, f"*-{suf}.mp4"))) if os.path.basename(p).startswith("sample-") == a.sample]
            if not cands: add("VID-format", "FAIL", f"{f}: немає {pref}*-{suf}.mp4 у {vd}"); continue
            for p in cands:
                n = os.path.basename(p); pr = probe(p)
                if not pr: add("VID-format", "FAIL", f"{n}: ffprobe не прочитав файл"); continue
                bad = []
                if pr["codec"] != "h264": bad.append(f"кодек {pr['codec']} ≠ h264")
                if (pr["w"], pr["h"]) != (W, H): bad.append(f"{pr['w']}x{pr['h']} ≠ {W}x{H}")
                if abs(pr["fps"] - 30) > 1: bad.append(f"{pr['fps']:.1f} fps ≠ 30")
                if not (lo <= pr["dur"] <= hi): bad.append(f"тривалість {pr['dur']:.1f} с поза {lo}–{hi}")
                add("VID-format", "FAIL" if bad else "PASS", f"{n}: " + ("; ".join(bad) if bad else f"{W}x{H}, {pr['dur']:.1f} с"))
                mb = os.path.getsize(p) / 1048576
                if mb > 50: add("VID-format", "WARN", f"{n}: {mb:.0f} МБ > 50 МБ — ризик ліміту push GitHub (100 МБ); див. video-spec.md, відкрите питання про LFS")
                if not has_audio(p): add("VID-format", "WARN", f"{n}: немає аудіодоріжки (очікується тиха ambient)")
                videos.append((p, pr["dur"]))
        elif f == "mobile":
            c = os.path.join(parent, "captions.yaml")
            if not os.path.exists(c): add("VID-format", "FAIL", "mobile: немає captions.yaml поруч із video/")
            elif not re.search(r"type:\s*(phone|reel)\b", open(c, encoding="utf-8").read()): add("VID-format", "FAIL", "mobile: у captions.yaml немає фрагмента type: phone|reel")
            else: add("VID-format", "MANUAL", "mobile: живий запис телефона ≥85 % ширини (Reels) — перевірити за кадрами очима")
        elif f == "one_pager":
            hit = [e for e in ("md", "html", "pdf") if os.path.exists(os.path.join(parent, f"SHOW.{e}"))]
            add("VID-format", "PASS" if hit else ("WARN" if a.sample else "FAIL"), "one_pager: SHOW." + ",".join(hit) if hit else "one_pager: немає SHOW.md|html|pdf" + (" (зразок — не обов'язково)" if a.sample else ""))
        else:
            add("VID-format", "WARN", f"формат «{f}» цей скрипт не знає — перевірити вручну")
    for p, dur in videos:
        n = os.path.basename(p)
        r = run(["ffmpeg", "-v", "info", "-i", p, "-vf", "freezedetect=n=-55dB:d=2", "-an", "-f", "null", "-"])
        fr = re.findall(r"freeze_duration:\s*([\d.]+)", r.stderr); st = re.findall(r"freeze_start:\s*([\d.]+)", r.stderr)
        ds = [float(d) for d in fr]; ss = [float(x) for x in st]
        if len(ss) > len(ds): ds.append(max(0.0, dur - ss[-1]))  # заморожений кадр до кінця файла: ffmpeg не друкує freeze_duration
        longf = [(s, d) for s, d in zip(ss, ds) if d > 2]
        add("VID-freeze", "FAIL" if longf else "PASS", f"{n}: " + (f"статичні фрагменти >2 с: " + ", ".join(f"{s:.1f} с (+{d:.1f})" for s, d in longf[:4]) if longf else "статичних кадрів >2 с немає"))
        if a.no_frames: add("VID-frames", "SKIP", f"{n}: --no-frames"); continue
        outdir = a.frames_out or os.path.join(vd, "frames"); os.makedirs(outdir, exist_ok=True)
        ts = sorted({0.0, 1.0, 3.0} | {float(x) for x in range(5, int(dur), 2)} | {round(max(0.0, dur - 0.3), 1)}); made = 0
        for t in ts:
            if t >= dur: continue
            o = os.path.join(outdir, f"{os.path.splitext(n)[0]}-{t:g}s.jpg")
            if run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.2f}", "-i", p, "-frames:v", "1", "-vf", "scale=960:-2", o]).returncode == 0 and os.path.exists(o): made += 1
        r = run(["ffmpeg", "-v", "error", "-i", p, "-vf", "fps=2,signalstats,metadata=print:key=lavfi.signalstats.YAVG:file=-", "-an", "-f", "null", "-"])
        vals = []; cur = None
        for line in r.stdout.splitlines():
            m = re.search(r"pts_time:([\d.]+)", line)
            if m: cur = float(m.group(1))
            m = re.search(r"YAVG=([\d.]+)", line)
            if m and cur is not None: vals.append((cur, float(m.group(1))))
        white = [t for t, y in vals if y > 235 and (t < 5 or t > dur - 5)]
        if made < 3 or not vals: add("VID-frames", "FAIL", f"{n}: кадри не витягнуто ({made})")
        elif white: add("VID-frames", "FAIL", f"{n}: майже білі кадри в перших/останніх 5 с: " + ", ".join(f"{t:.1f} с" for t in white[:5]))
        else: add("VID-frames", "PASS", f"{n}: {made} кадрів у {outdir}; перші/останні 5 с без порожніх кадрів")
    if not videos and not any(r["id"] == "VID-format" and r["status"] == "FAIL" for r in res):
        for i in ("VID-freeze", "VID-frames"): add(i, "SKIP", "немає відео для перевірки")
    out()

def out():
    print(json.dumps(res, ensure_ascii=False, indent=1)); sys.exit(1 if any(r["status"] == "FAIL" for r in res) else 0)

main()
