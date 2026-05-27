"""
masafee-ctf-7b: QLoRA continued pretraining on CTF writeups.

Base: unsloth/Qwen2.5-Coder-7B-Instruct (4-bit)
Data: /mnt/data/masafee-ctf-7b/datasets/processed (pre-packed 4096-token chunks)
Output: /mnt/data/masafee-ctf-7b/output/

Optimized for single RTX 3060 12GB via unsloth.
"""

import os, time
os.environ.setdefault("HF_HOME", "/mnt/data/masafee-ctf-7b/hf-cache")
os.environ.setdefault("HF_HUB_CACHE", "/mnt/data/masafee-ctf-7b/hf-cache/hub")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

import torch
from datasets import load_from_disk
from unsloth import FastLanguageModel
from transformers import TrainingArguments, Trainer, DataCollatorForLanguageModeling

# ---- config ----
MODEL_NAME = "unsloth/Qwen2.5-Coder-7B-Instruct"
DATA_DIR = "/mnt/data/masafee-ctf-7b/datasets/processed"
OUTPUT_DIR = "/mnt/data/masafee-ctf-7b/output"
MAX_SEQ_LEN = 2048

LORA_R = 32
LORA_ALPHA = 64
LORA_DROPOUT = 0.05

NUM_EPOCHS = 2
BATCH_SIZE = 1
GRAD_ACCUM = 8
LEARNING_RATE = 2e-4
WARMUP_STEPS = 10
SAVE_STEPS = 400
EVAL_STEPS = 400
LOGGING_STEPS = 10

os.makedirs(OUTPUT_DIR, exist_ok=True)

# ---- 1. load model + tokenizer (4-bit) ----
print(f"[1/5] Loading {MODEL_NAME} in 4-bit ...")
t0 = time.time()
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name=MODEL_NAME,
    max_seq_length=MAX_SEQ_LEN,
    dtype=None,           # auto-detect (bf16 on Ampere)
    load_in_4bit=True,
)
print(f"   loaded in {time.time()-t0:.1f}s; VRAM={torch.cuda.memory_allocated()/1024**3:.2f} GB")

# ---- 2. attach LoRA ----
print(f"[2/5] Attaching LoRA (r={LORA_R}, alpha={LORA_ALPHA}) ...")
model = FastLanguageModel.get_peft_model(
    model,
    r=LORA_R,
    target_modules=[
        "q_proj", "k_proj", "v_proj", "o_proj",
        "gate_proj", "up_proj", "down_proj",
    ],
    lora_alpha=LORA_ALPHA,
    lora_dropout=LORA_DROPOUT,
    bias="none",
    use_gradient_checkpointing="unsloth",
    random_state=42,
    use_rslora=False,
    loftq_config=None,
)
trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
total_params = sum(p.numel() for p in model.parameters())
print(f"   trainable: {trainable_params:,} / total: {total_params:,} ({100*trainable_params/total_params:.3f}%)")

# ---- 3. load dataset ----
print(f"[3/5] Loading dataset from {DATA_DIR} ...")
dsd = load_from_disk(DATA_DIR)
print(f"   train: {len(dsd['train']):,} chunks, val: {len(dsd['validation']):,} chunks")

# add labels=input_ids for causal LM
def add_labels(batch):
    batch["labels"] = [list(ids) for ids in batch["input_ids"]]
    return batch

train_ds = dsd["train"].map(add_labels, batched=True, num_proc=4)
val_ds = dsd["validation"].map(add_labels, batched=True, num_proc=4)

# ---- 4. trainer ----
print(f"[4/5] Configuring trainer ...")
_max_steps_env = os.environ.get("MAX_STEPS")
_smoke = _max_steps_env is not None
training_args = TrainingArguments(
    output_dir=OUTPUT_DIR,
    num_train_epochs=NUM_EPOCHS if not _smoke else 1,
    max_steps=int(_max_steps_env) if _smoke else -1,
    per_device_train_batch_size=BATCH_SIZE,
    per_device_eval_batch_size=BATCH_SIZE,
    gradient_accumulation_steps=GRAD_ACCUM,
    learning_rate=LEARNING_RATE,
    warmup_steps=WARMUP_STEPS,
    logging_steps=LOGGING_STEPS,
    save_steps=SAVE_STEPS,
    save_total_limit=2,
    eval_steps=EVAL_STEPS,
    eval_strategy="steps",
    bf16=True,
    optim="paged_adamw_8bit",
    weight_decay=0.01,
    lr_scheduler_type="cosine",
    seed=42,
    report_to=[],         # disable wandb etc.
    dataloader_num_workers=2,
    remove_unused_columns=False,
)

trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=train_ds,
    eval_dataset=val_ds,
    data_collator=DataCollatorForLanguageModeling(tokenizer=tokenizer, mlm=False),
)

# ---- 5. train ----
print(f"[5/5] Starting training ...")
print(f"   epochs={NUM_EPOCHS}, batch={BATCH_SIZE}, grad_accum={GRAD_ACCUM} (effective batch={BATCH_SIZE*GRAD_ACCUM})")
print(f"   total optimization steps: ~{len(train_ds) * NUM_EPOCHS // (BATCH_SIZE * GRAD_ACCUM)}")

trainer.train()

# ---- save LoRA adapter only ----
adapter_dir = os.path.join(OUTPUT_DIR, "lora_final")
print(f"\nSaving LoRA adapter to {adapter_dir}")
model.save_pretrained(adapter_dir)
tokenizer.save_pretrained(adapter_dir)
print(f"Done. VRAM final: {torch.cuda.memory_allocated()/1024**3:.2f} GB")
