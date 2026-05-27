"""
CyberMetric-500 で 3 モデルの知識ベース比較。

Models:
  - qwen2.5-coder:7b                      (Base)
  - masafee-ctf-7b                        (Our QLoRA fine-tune)
  - hf.co/fdtn-ai/Foundation-Sec-8B-...  (Reference)

Method:
  - 各質問を MCQ プロンプトとして投げる
  - 出力から A/B/C/D を抽出して solution と比較
  - 全体正答率 + LoRA特化ドメインで集計
"""

import os, re, json, time, sys
os.environ.setdefault("HF_HOME", "/mnt/data/masafee-ctf-7b/hf-cache")
os.environ.setdefault("HF_HUB_CACHE", "/mnt/data/masafee-ctf-7b/hf-cache/hub")

import requests
from datasets import load_dataset

OLLAMA_URL = "http://localhost:11434/api/chat"

MODELS = [
    ("base-qwen-coder",  "qwen2.5-coder:7b"),
    ("masafee-ctf-7b",   "masafee-ctf-7b:latest"),
    ("foundation-sec-8b", "foundation-sec-8b:latest"),
]

DATASET_NAME = "tihanyin/CyberMetric"
DATA_FILE = "CyberMetric-500-v1.json"  # CyberMetric-500 split
OUT_DIR = "/mnt/data/masafee-ctf-7b/eval/cybermetric"

os.makedirs(OUT_DIR, exist_ok=True)


def load_questions():
    """CyberMetric は HF dataset の data ファイル指定が必要"""
    from huggingface_hub import hf_hub_download
    fp = hf_hub_download(
        repo_id=DATASET_NAME,
        filename=DATA_FILE,
        repo_type="dataset",
    )
    with open(fp) as f:
        data = json.load(f)
    return data.get("questions", data)


def format_prompt(q):
    """Q + 4 options を LLM に分かりやすい MCQ プロンプトに整形"""
    options_str = "\n".join(f"{k}. {v}" for k, v in q["answers"].items())
    return (
        f"{q['question']}\n\n"
        f"{options_str}\n\n"
        f"Respond with only a single letter (A, B, C, or D)."
    )


def parse_letter(text):
    """モデル出力から最初に登場する A/B/C/D を取り出す"""
    if not text:
        return None
    # よくあるパターンを順に試す
    patterns = [
        r"^\s*([ABCD])\b",         # "A" or "A." at start
        r"\b(?:Answer|answer)[:\s]*([ABCD])\b",
        r"\b([ABCD])\b",           # any standalone letter
    ]
    for p in patterns:
        m = re.search(p, text)
        if m:
            return m.group(1).upper()
    return None


def query(model, prompt, retries=2):
    for attempt in range(retries + 1):
        try:
            r = requests.post(OLLAMA_URL, json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "options": {"temperature": 0, "num_predict": 30},
            }, timeout=120)
            r.raise_for_status()
            return r.json().get("message", {}).get("content", "")
        except Exception as e:
            if attempt == retries:
                return f"<ERROR:{e}>"
            time.sleep(2)


def evaluate(label, model):
    print(f"\n=== {label} ({model}) ===")
    questions = load_questions()
    total = len(questions)
    correct = 0
    by_topic = {}  # not all CyberMetric items have topics, but try
    results = []

    t_start = time.time()
    for i, q in enumerate(questions):
        prompt = format_prompt(q)
        raw = query(model, prompt)
        pred = parse_letter(raw)
        truth = q.get("solution", "?").strip().upper()
        ok = (pred == truth)
        if ok:
            correct += 1
        results.append({
            "i": i, "question": q["question"][:120],
            "truth": truth, "pred": pred, "ok": ok, "raw": raw[:200],
        })
        if (i + 1) % 50 == 0:
            elapsed = time.time() - t_start
            rate = (i + 1) / elapsed
            eta = (total - i - 1) / rate
            print(f"  [{i+1}/{total}] acc={100*correct/(i+1):.1f}% "
                  f"({correct}/{i+1}) - rate={rate:.1f}q/s, ETA={eta:.0f}s")

    elapsed = time.time() - t_start
    acc = 100 * correct / total
    print(f"  FINAL: {correct}/{total} = {acc:.2f}%  ({elapsed:.0f}s)")

    out_path = os.path.join(OUT_DIR, f"{label}.json")
    with open(out_path, "w") as f:
        json.dump({
            "label": label, "model": model,
            "n": total, "correct": correct, "accuracy": acc,
            "elapsed_sec": elapsed,
            "results": results,
        }, f, indent=2, ensure_ascii=False)
    return {"label": label, "model": model, "acc": acc, "correct": correct,
            "total": total, "elapsed_sec": elapsed}


def main():
    summary = []
    for label, model in MODELS:
        try:
            res = evaluate(label, model)
            summary.append(res)
        except Exception as e:
            print(f"ERROR on {label}: {e}")
            summary.append({"label": label, "model": model, "error": str(e)})

    print("\n" + "="*60)
    print("FINAL SUMMARY (CyberMetric-500)")
    print("="*60)
    for r in summary:
        if "acc" in r:
            print(f"  {r['label']:25s}  {r['acc']:5.2f}%  "
                  f"({r['correct']:3d}/{r['total']})  in {r['elapsed_sec']:.0f}s")
        else:
            print(f"  {r['label']:25s}  ERROR: {r.get('error', '?')}")

    with open(os.path.join(OUT_DIR, "summary.json"), "w") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    main()
