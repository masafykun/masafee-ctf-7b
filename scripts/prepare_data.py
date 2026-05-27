"""
masafee-ctf-7b: training data preparation
- Source: justinwangx/CTFtime (18,013 raw writeup chunks)
- Filter: 500 < length < 8000 chars (drop URL stubs / overly long combined posts)
- Strategy: continued pretraining (raw text, causal LM objective)
- Tokenize with Qwen 2.5 Coder 7B Instruct tokenizer
- Pack into max_seq_length=4096 chunks
- Split: 95% train / 5% val
"""

import os, json, random
os.environ.setdefault("HF_HOME", "/mnt/data/masafee-ctf-7b/hf-cache")
os.environ.setdefault("HF_HUB_CACHE", "/mnt/data/masafee-ctf-7b/hf-cache/hub")

from datasets import load_dataset, Dataset, DatasetDict
from transformers import AutoTokenizer

# ---- config ----
OUT_DIR = "/mnt/data/masafee-ctf-7b/datasets/processed"
MAX_SEQ_LEN = int(os.environ.get("SEQ_LEN", 2048))
MIN_CHARS = 500
MAX_CHARS = 8000
VAL_RATIO = 0.05
SEED = 42
MODEL_NAME = "unsloth/Qwen2.5-Coder-7B-Instruct"

random.seed(SEED)
os.makedirs(OUT_DIR, exist_ok=True)

# ---- load source ----
print(f"[1/5] Loading justinwangx/CTFtime ...")
ds = load_dataset("justinwangx/CTFtime", split="train")
print(f"   {len(ds):,} rows loaded")

# ---- filter by length ----
print(f"[2/5] Filtering: {MIN_CHARS} < length < {MAX_CHARS} chars ...")
def keep(ex):
    n = len(ex["text_chunk"])
    return MIN_CHARS < n < MAX_CHARS
ds_filt = ds.filter(keep, num_proc=4)
print(f"   {len(ds_filt):,} rows after filter ({100*len(ds_filt)/len(ds):.1f}% retained)")

# ---- tokenize ----
print(f"[3/5] Loading tokenizer & tokenizing ...")
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
# Ensure pad token exists
if tokenizer.pad_token is None:
    tokenizer.pad_token = tokenizer.eos_token

def tokenize(batch):
    out = tokenizer(
        batch["text_chunk"],
        add_special_tokens=True,
        return_attention_mask=False,
    )
    return {"input_ids": out["input_ids"]}

ds_tok = ds_filt.map(
    tokenize,
    batched=True,
    batch_size=64,
    num_proc=4,
    remove_columns=["text_chunk"],
)
total_tokens = sum(len(x) for x in ds_tok["input_ids"])
print(f"   Total tokens: {total_tokens:,}")

# ---- pack into max_seq_length chunks (sliding-window-less, just concatenate + split) ----
print(f"[4/5] Packing into {MAX_SEQ_LEN}-token chunks ...")
EOS = tokenizer.eos_token_id

all_ids = []
for ids in ds_tok["input_ids"]:
    all_ids.extend(ids)
    all_ids.append(EOS)  # separator between documents

# Drop last partial chunk
n_full = len(all_ids) // MAX_SEQ_LEN
all_ids = all_ids[: n_full * MAX_SEQ_LEN]
chunks = [all_ids[i:i + MAX_SEQ_LEN] for i in range(0, len(all_ids), MAX_SEQ_LEN)]
print(f"   {len(chunks):,} chunks of {MAX_SEQ_LEN} tokens each ({MAX_SEQ_LEN * len(chunks):,} tokens total)")

# ---- shuffle & train/val split ----
print(f"[5/5] Shuffling & splitting (val={VAL_RATIO}) ...")
random.shuffle(chunks)
n_val = max(1, int(len(chunks) * VAL_RATIO))
val_chunks = chunks[:n_val]
train_chunks = chunks[n_val:]

train_ds = Dataset.from_dict({"input_ids": train_chunks})
val_ds = Dataset.from_dict({"input_ids": val_chunks})
dsd = DatasetDict({"train": train_ds, "validation": val_ds})

dsd.save_to_disk(OUT_DIR)
print(f"\nSaved to {OUT_DIR}")
print(f"  train: {len(train_ds):,} chunks")
print(f"  val:   {len(val_ds):,} chunks")
print(f"  total: {len(train_ds) + len(val_ds):,} chunks ({MAX_SEQ_LEN * (len(train_ds) + len(val_ds)):,} tokens)")
