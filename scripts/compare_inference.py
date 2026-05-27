"""
masafee-ctf-7b: Before/After 推論比較

Base (Qwen 2.5 Coder 7B Instruct) vs masafee-ctf-7b (LoRA適用後) を、
同じ CTF 関連プロンプトで生成させて並べる。

実装ノート: PeftModel の enable_adapters / disable_adapters を使うと、
モデルを2回ロードせず1回のロードで両方の出力が取れる。
"""

import os, time, json
os.environ.setdefault("HF_HOME", "/mnt/data/masafee-ctf-7b/hf-cache")
os.environ.setdefault("HF_HUB_CACHE", "/mnt/data/masafee-ctf-7b/hf-cache/hub")

import torch
from unsloth import FastLanguageModel
from peft import PeftModel

MODEL_NAME = "unsloth/Qwen2.5-Coder-7B-Instruct"
LORA_PATH = "/mnt/data/masafee-ctf-7b/output/lora_final"
OUT_FILE = "/mnt/data/masafee-ctf-7b/eval/compare_results.md"

# 比較用CTF系プロンプト
PROMPTS = [
    "I have a binary that segfaults when I send too many characters. How should I approach exploiting this?",
    "Walk me through how you'd solve a typical CTF challenge tagged 'web' with a login form that uses a JWT token.",
    "Given a binary with no symbols and PIE enabled, how do you locate the win() function for ret2win exploitation?",
    "Explain how to approach an RSA crypto CTF challenge where you have a small public exponent e=3 and three different ciphertexts.",
    "I see this code in a CTF challenge:\n```python\nimport os\nflag = open('/flag.txt').read()\nname = input('Name: ')\nprint(f'Hello {name}!')\n```\nWhat vulnerability is this?",
]

print(f"[1/3] Loading base + LoRA adapter ...")
t0 = time.time()
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name=MODEL_NAME,
    max_seq_length=2048,
    dtype=None,
    load_in_4bit=True,
)
# Attach our trained LoRA on top of the base
model = PeftModel.from_pretrained(model, LORA_PATH)
FastLanguageModel.for_inference(model)
print(f"   loaded in {time.time()-t0:.1f}s; VRAM={torch.cuda.memory_allocated()/1024**3:.2f} GB")

def gen(prompt: str, use_adapter: bool, max_new_tokens=400) -> str:
    if use_adapter:
        model.enable_adapter_layers()
    else:
        model.disable_adapter_layers()
    messages = [{"role": "user", "content": prompt}]
    inputs = tokenizer.apply_chat_template(
        messages, return_tensors="pt", add_generation_prompt=True
    ).to("cuda")
    with torch.no_grad():
        out = model.generate(
            inputs,
            max_new_tokens=max_new_tokens,
            do_sample=False,
            temperature=None, top_p=None,
            pad_token_id=tokenizer.eos_token_id,
        )
    return tokenizer.decode(out[0][inputs.shape[1]:], skip_special_tokens=True)

print(f"[2/3] Running comparison on {len(PROMPTS)} prompts ...")
os.makedirs(os.path.dirname(OUT_FILE), exist_ok=True)
results = []
with open(OUT_FILE, "w") as f:
    f.write("# masafee-ctf-7b: Before/After 推論比較\n\n")
    f.write(f"Base: `{MODEL_NAME}`  \nLoRA: `{LORA_PATH}` (CTFtime writeups で QLoRA 学習)\n\n")
    f.write("---\n\n")

    for i, prompt in enumerate(PROMPTS, 1):
        print(f"   [{i}/{len(PROMPTS)}] {prompt[:60]}...")
        t1 = time.time()
        base_out = gen(prompt, use_adapter=False)
        t_base = time.time() - t1
        t1 = time.time()
        ft_out = gen(prompt, use_adapter=True)
        t_ft = time.time() - t1

        section = f"""## Prompt {i}

> {prompt}

### 🔵 Base (Qwen 2.5 Coder 7B Instruct) — {t_base:.1f}s

{base_out}

### 🟢 masafee-ctf-7b (after CTF QLoRA) — {t_ft:.1f}s

{ft_out}

---

"""
        f.write(section)
        f.flush()
        results.append({"prompt": prompt, "base": base_out, "ft": ft_out,
                       "base_time": t_base, "ft_time": t_ft})

print(f"[3/3] Saved: {OUT_FILE}")
with open(OUT_FILE.replace(".md", ".json"), "w") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

print("Done. VRAM final:", torch.cuda.memory_allocated() / 1024**3, "GB")
