"""CPU benchmark for the IndicTrans2 checkpoints.

    cd backend && .venv/bin/python -m scripts.benchmark_translation [--runs 5] [--beams 3] [--threads 4]

Reports model load time, resident memory (RSS) after loading, and per-direction latency for
short chat-style messages. Results are written to ../docs/benchmark-results.md as well.
"""

import argparse
import os
import platform
import statistics
import time
from datetime import UTC, datetime

import psutil

SAMPLES = {
    ("guj_Gujr", "hin_Deva"): ["તમે કેમ છો?", "આજે હવામાન ખૂબ સરસ છે.", "હું સાંજે તને ફોન કરીશ."],
    ("hin_Deva", "guj_Gujr"): ["मैं ठीक हूँ, धन्यवाद।", "क्या तुम कल आ रहे हो?", "मुझे यह किताब बहुत पसंद है।"],
    ("eng_Latn", "hin_Deva"): ["How are you?", "The meeting starts at five.", "Please send me the file."],
    ("hin_Deva", "eng_Latn"): ["आप कैसे हैं?", "मैं घर जा रहा हूँ।", "खाना बहुत स्वादिष्ट था।"],
    ("eng_Latn", "tam_Taml"): ["Good morning!", "Where are you now?", "See you tomorrow."],
    ("tam_Taml", "ben_Beng"): ["நீங்கள் எப்படி இருக்கிறீர்கள்?", "நான் நன்றாக இருக்கிறேன்.", "நாளை சந்திப்போம்."],
}


def rss_mb() -> float:
    return psutil.Process(os.getpid()).memory_info().rss / 1024 / 1024


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--beams", type=int, default=None)
    parser.add_argument("--threads", type=int, default=None)
    args = parser.parse_args()

    from app.core.config import get_settings
    from app.integrations.translation.base import Direction
    from app.integrations.translation.indictrans2 import IndicTrans2Engine

    settings = get_settings()
    updates: dict[str, object] = {"TRANSLATION_BACKEND": "indictrans2"}
    if args.beams:
        updates["TRANSLATION_NUM_BEAMS"] = args.beams
    if args.threads:
        updates["TRANSLATION_TORCH_THREADS"] = args.threads
    settings = settings.model_copy(update=updates)
    engine = IndicTrans2Engine(settings)

    lines = [
        f"## Run {datetime.now(UTC):%Y-%m-%d %H:%M UTC}",
        "",
        f"- CPU: {platform.processor() or platform.machine()}, {psutil.cpu_count(logical=False)} cores; "
        f"RAM {psutil.virtual_memory().total / 2**30:.1f} GiB",
        f"- beams={settings.TRANSLATION_NUM_BEAMS}, torch threads={settings.TRANSLATION_TORCH_THREADS}, "
        f"runs per sentence={args.runs}",
        f"- RSS before loading: {rss_mb():.0f} MB",
        "",
        "| Checkpoint | Load time (s) | RSS after load (MB) |",
        "|---|---|---|",
    ]
    for direction in Direction:
        start = time.perf_counter()
        engine.load(direction)
        status = engine.status()[direction.value]
        if status["state"] != "ready":
            raise SystemExit(f"Failed to load {status['model']}: {status['error']}")
        lines.append(f"| {status['model']} | {time.perf_counter() - start:.1f} | {rss_mb():.0f} |")

    lines += ["", "| Direction | Checkpoint | median ms | p90 ms | max ms | sample output |", "|---|---|---|---|---|---|"]
    for (src, tgt), sentences in SAMPLES.items():
        direction = engine.registry.direction(src, tgt)
        engine.translate_batch([sentences[0]], src, tgt, direction)  # warm-up
        timings = []
        example = ""
        for _ in range(args.runs):
            for s in sentences:
                t0 = time.perf_counter()
                out = engine.translate_batch([s], src, tgt, direction)[0]
                timings.append((time.perf_counter() - t0) * 1000)
                example = example or f"{s} → {out}"
        timings.sort()
        p90 = timings[int(len(timings) * 0.9) - 1] if len(timings) > 1 else timings[0]
        lines.append(f"| {src}→{tgt} | {engine.registry.checkpoints[direction].split('/')[-1]} | "
                     f"{statistics.median(timings):.0f} | {p90:.0f} | {max(timings):.0f} | {example} |")
    lines += ["", f"- Peak RSS: {rss_mb():.0f} MB", ""]

    report = "\n".join(lines)
    print(report)
    out_path = os.path.join(os.path.dirname(__file__), "..", "..", "docs", "benchmark-results.md")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    header = "" if os.path.exists(out_path) else "# IndicTrans2 CPU benchmark results\n\n"
    with open(out_path, "a", encoding="utf-8") as f:
        f.write(header + report + "\n")


if __name__ == "__main__":
    main()
