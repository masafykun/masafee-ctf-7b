"""
masafee-ctf-7b: LoRA → merge → GGUF Q4_K_M 量子化

Strategy:
- CPU で FP16 base + LoRA をマージ（VRAM不足回避、所要数分）
- 普通の HF format でディスクに保存
- llama.cpp の convert_hf_to_gguf.py で GGUF FP16 に変換
- llama-quantize で Q4_K_M に量子化
"""

import os, time, subprocess, sys
os.environ.setdefault("HF_HOME", "/mnt/data/masafee-ctf-7b/hf-cache")
os.environ.setdefault("HF_HUB_CACHE", "/mnt/data/masafee-ctf-7b/hf-cache/hub")

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel

BASE_MODEL = "Qwen/Qwen2.5-Coder-7B-Instruct"
LORA_PATH = "/mnt/data/masafee-ctf-7b/output/lora_final"
MERGED_DIR = "/mnt/data/masafee-ctf-7b/export/merged_fp16"
GGUF_DIR = "/mnt/data/masafee-ctf-7b/export"
LLAMA_CPP = "/mnt/data/masafee-ctf-7b/llama.cpp"

os.makedirs(MERGED_DIR, exist_ok=True)
os.makedirs(GGUF_DIR, exist_ok=True)


# ---- 1. CPU merge ----
if not os.path.exists(os.path.join(MERGED_DIR, "config.json")):
    print(f"[1/4] Loading base {BASE_MODEL} on CPU (FP16) ...")
    t0 = time.time()
    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)
    model = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL,
        torch_dtype=torch.float16,
        device_map="cpu",
        low_cpu_mem_usage=True,
    )
    print(f"   base loaded in {time.time()-t0:.1f}s")

    print(f"[2/4] Loading LoRA adapter from {LORA_PATH} ...")
    t0 = time.time()
    model = PeftModel.from_pretrained(model, LORA_PATH, device_map="cpu")
    print(f"   adapter loaded in {time.time()-t0:.1f}s")

    print(f"[3/4] Merging LoRA into base + saving FP16 ...")
    t0 = time.time()
    model = model.merge_and_unload()
    model.save_pretrained(MERGED_DIR, safe_serialization=True)
    tokenizer.save_pretrained(MERGED_DIR)
    print(f"   merged+saved in {time.time()-t0:.1f}s")
    del model
else:
    print(f"[skip] merged model already exists at {MERGED_DIR}")

# ---- 2. llama.cpp setup ----
if not os.path.exists(os.path.join(LLAMA_CPP, "convert_hf_to_gguf.py")):
    print(f"[setup] cloning llama.cpp to {LLAMA_CPP} ...")
    subprocess.run([
        "git", "clone", "--depth", "1",
        "https://github.com/ggerganov/llama.cpp.git", LLAMA_CPP
    ], check=True)
    print(f"[setup] installing llama.cpp python requirements ...")
    subprocess.run([
        sys.executable, "-m", "pip", "install", "-q",
        "-r", os.path.join(LLAMA_CPP, "requirements.txt")
    ], check=True)
else:
    print(f"[setup] llama.cpp already cloned")

# ---- 3. HF → GGUF FP16 ----
gguf_f16 = os.path.join(GGUF_DIR, "masafee-ctf-7b.f16.gguf")
if not os.path.exists(gguf_f16):
    print(f"[4/4] Converting HF FP16 → GGUF FP16 ...")
    t0 = time.time()
    subprocess.run([
        sys.executable,
        os.path.join(LLAMA_CPP, "convert_hf_to_gguf.py"),
        MERGED_DIR,
        "--outfile", gguf_f16,
        "--outtype", "f16",
    ], check=True)
    print(f"   converted in {time.time()-t0:.1f}s")
else:
    print(f"[skip] {gguf_f16} already exists")

# ---- 4. Q4_K_M quantize ----
# Need llama.cpp's llama-quantize binary. Build if needed.
quant_bin = os.path.join(LLAMA_CPP, "build", "bin", "llama-quantize")
if not os.path.exists(quant_bin):
    print(f"[build] building llama.cpp (cmake) ...")
    subprocess.run(["cmake", "-B", os.path.join(LLAMA_CPP, "build")], cwd=LLAMA_CPP, check=True)
    subprocess.run([
        "cmake", "--build", os.path.join(LLAMA_CPP, "build"),
        "--config", "Release", "-j", "4", "--target", "llama-quantize",
    ], check=True)

gguf_q4 = os.path.join(GGUF_DIR, "masafee-ctf-7b.q4_k_m.gguf")
print(f"[quantize] Q4_K_M ...")
t0 = time.time()
subprocess.run([quant_bin, gguf_f16, gguf_q4, "Q4_K_M"], check=True)
print(f"   quantized in {time.time()-t0:.1f}s")

# ---- summary ----
print(f"\nDone. Files in {GGUF_DIR}:")
for f in sorted(os.listdir(GGUF_DIR)):
    fpath = os.path.join(GGUF_DIR, f)
    if os.path.isfile(fpath):
        size_mb = os.path.getsize(fpath) / 1024 / 1024
        print(f"  {f}  ({size_mb:.1f} MB)")
