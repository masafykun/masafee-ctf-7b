# 🐾 Masafee CTF 7B

> CTF (Capture-the-Flag) writeup でファインチューニングした 7B 日英対応LLM — 消費者向けGPU 1台・電気代 150円で完結した個人研究

[![License: MIT (code)](https://img.shields.io/badge/Code-MIT-yellow.svg?style=flat-square)](LICENSE)
[![Weights License: Research-only](https://img.shields.io/badge/Weights-research%20%2F%20personal-orange?style=flat-square)](#license)
[![Base Model](https://img.shields.io/badge/Base-Qwen2.5--Coder--7B--Instruct-8A2BE2?style=flat-square)](https://huggingface.co/Qwen/Qwen2.5-Coder-7B-Instruct)
[![Method](https://img.shields.io/badge/Method-QLoRA-34d399?style=flat-square)](https://github.com/unslothai/unsloth)
[![GPU](https://img.shields.io/badge/GPU-RTX%203060%2012GB-76b900?style=flat-square)](https://www.nvidia.com/en-us/geforce/graphics-cards/30-series/rtx-3060-3060ti/)

[Stable Diffusion LoRA](https://github.com/masafykun/masafee-lora) で作った [masafee-lora](https://huggingface.co/masafy/masafee-lora) と同じ「**自宅 RTX 3060 で完結する個人研究シリーズ**」第二弾。今回はテキスト生成 LLM で、**CTF writeup の文体・専門用語** を 7B モデルに継続事前学習させた。

評価結果の詳細は [EVALUATION.md](EVALUATION.md) を参照。

---

## 概要

| 項目 | 値 |
|---|---|
| ベースモデル | [Qwen 2.5 Coder 7B Instruct](https://huggingface.co/Qwen/Qwen2.5-Coder-7B-Instruct) |
| 学習手法 | QLoRA (r=32, α=64) via [unsloth](https://github.com/unslothai/unsloth) |
| 学習データ | [`justinwangx/CTFtime`](https://huggingface.co/datasets/justinwangx/CTFtime) (18,013 writeup chunks → packed to 5,200 × 2048-token sequences) |
| 学習ハードウェア | NVIDIA GeForce RTX 3060 12GB (自宅) |
| 学習時間 | 12 時間 17 分 |
| 学習電気代 | 約 150 円 |
| クラウドコスト | 0 円 |
| 配布フォーマット | LoRA adapter (`safetensors`) + Q4_K_M GGUF (4.4 GB) |

---

## 結果サマリー

3モデル（masafee-ctf-7b / Base Qwen 2.5 Coder 7B / Cisco Foundation-Sec-8B）を 2 種のベンチマークで比較した。

### CyberMetric-500 (一般 cybersecurity 知識 MCQ)

| Model | Accuracy |
|---|---|
| `qwen2.5-coder:7b` (Base) | 86.20% |
| **`masafee-ctf-7b`** | **84.00%** |
| `foundation-sec-8b` | 82.60% |

3モデルとも 95% 信頼区間 (±3.1pp) 内で実質同等。CTF writeup 学習は MCQ 知識に有意な影響を与えなかった。

### NYU CTF Bench (実 CTF 問題、30 問サブセット、single-shot)

| Model | Solved |
|---|---|
| `qwen2.5-coder:7b` | 4 / 30 (13.3%) |
| `foundation-sec-8b` | 2 / 30 (6.7%) |
| **`masafee-ctf-7b`** | 0 / 30 (0.0%) |

すべて pass@1 で実用レベル未満。masafee-ctf-7b は writeup format を出力途中で生成し、トークン上限内に最終 flag に到達できないケースが多かった (style overfitting)。

### 行動の差異（CTF プロンプト下）

| Measure | `masafee-ctf-7b` | `foundation-sec-8b` |
|---|---|---|
| Hedging-language occurrences (30 outputs) | 7 | 77 |
| Distinct CTF tool/technique terms | 22 | 21 |

masafee-ctf-7b は writeup の断定的口調を学習し、Foundation-Sec-8B は SOC analysis に適した慎重な hedging を保持している。これは設計目的の違いを反映しており、どちらが優れているという話ではない。

### 主な学術的観察

- CTF writeup の continued pretraining は **style transfer** であり capability transfer ではない
- 7B 規模 + 18k 件規模の SFT では、Base 推論能力に対する増分は限定的
- 過剰な style 学習は、direct answer 生成を妨げるケースがある

---

## 使い方

### Hugging Face で使う

LoRA adapter: https://huggingface.co/masafy/masafee-ctf-7b

```python
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer
import torch

base = AutoModelForCausalLM.from_pretrained(
    "Qwen/Qwen2.5-Coder-7B-Instruct",
    torch_dtype=torch.bfloat16,
).to("cuda")
tokenizer = AutoTokenizer.from_pretrained("Qwen/Qwen2.5-Coder-7B-Instruct")
model = PeftModel.from_pretrained(base, "masafy/masafee-ctf-7b")
```

### Ollama で使う (Q4_K_M GGUF, 4.4 GB)

```bash
# GGUF ファイルを Hugging Face からダウンロード
huggingface-cli download masafy/masafee-ctf-7b masafee-ctf-7b.q4_k_m.gguf

# Modelfile を作って ollama に登録
echo 'FROM ./masafee-ctf-7b.q4_k_m.gguf
TEMPLATE """{{ if .System }}<|im_start|>system
{{ .System }}<|im_end|>
{{ end }}{{ range .Messages }}<|im_start|>{{ .Role }}
{{ .Content }}<|im_end|>
{{ end }}<|im_start|>assistant
"""
PARAMETER stop "<|im_start|>"
PARAMETER stop "<|im_end|>"
PARAMETER temperature 0.7
PARAMETER num_ctx 4096' > Modelfile

ollama create masafee-ctf-7b -f Modelfile
ollama run masafee-ctf-7b
```

---

## ディレクトリ構成

```
masafee-ctf-7b/
├── EVALUATION.md         評価レポート（CyberMetric / NYU CTF）
├── README.md             このファイル
├── LICENSE               MIT (コード・スクリプト・文書部分)
├── CITATION.cff          引用情報
├── .zenodo.json          Zenodo アーカイブ用メタデータ
└── scripts/
    ├── prepare_data.py       学習データ前処理（フィルタ・トークン化・パッキング）
    ├── train.py              QLoRA 学習（unsloth）
    ├── compare_inference.py  Before/After 出力比較
    ├── export_gguf.py        LoRA マージ → GGUF FP16 → Q4_K_M 量子化
    ├── eval_cybermetric.py   CyberMetric-500 評価
    └── eval_nyu_ctf.py       NYU CTF Bench サブセット評価
```

学習データ・モデル重み・チェックポイントは git 管理外（`.gitignore` 参照）。

---

## 再現方法

学習からGGUF出力まで:

```bash
# 1. Python 3.11 環境（uv 推奨。システムPythonが新しすぎる場合に有効）
uv venv --python 3.11 venv
source venv/bin/activate

# 2. PyTorch + unsloth (cu128 wheels)
uv pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128
uv pip install unsloth "transformers>=4.46" datasets accelerate peft trl bitsandbytes sentencepiece protobuf

# 3. 学習データ前処理
python scripts/prepare_data.py        # justinwangx/CTFtime → 4096-token chunks

# 4. QLoRA 学習（~12 時間 / RTX 3060）
python scripts/train.py

# 5. LoRA マージ → GGUF 量子化
python scripts/export_gguf.py

# 6. 評価
python scripts/eval_cybermetric.py
python scripts/eval_nyu_ctf.py
```

各スクリプトは冒頭にハイパーパラメータをコメントで記載。

---

## License

### Code, scripts, EVALUATION.md, README.md
**MIT License** — see [LICENSE](LICENSE).

### Model weights (LoRA adapter and GGUF)
**Research and personal use only.** This LoRA adapter is a derivative work
of `justinwangx/CTFtime`, which itself is scraped CTFtime writeups whose
copyright belongs to individual contributors. Redistribution of the weights
or commercial use is not permitted without explicit permission from the
original writeup authors.

### Base model (`Qwen/Qwen2.5-Coder-7B-Instruct`)
Apache 2.0 — see the [base model page](https://huggingface.co/Qwen/Qwen2.5-Coder-7B-Instruct).

---

## Citation

If you reference this work:

```bibtex
@software{suzuki_masafee_ctf_7b_2026,
  author = {Suzuki, Masato},
  title  = {{Masafee CTF 7B: QLoRA Fine-Tuning of a 7B Code Model on
            CTF Writeups for Stylistic and Knowledge Adaptation}},
  year   = {2026},
  url    = {https://github.com/masafykun/masafee-ctf-7b},
  orcid  = {0009-0000-7977-2756}
}
```

GitHub 右上の "Cite this repository" からも生成できる（[CITATION.cff](CITATION.cff)）。

---

## シリーズ

| 第 | プロジェクト | 領域 |
|---|---|---|
| 1 | [masafee-lora](https://github.com/masafykun/masafee-lora) | 画像生成 (Stable Diffusion LoRA) |
| **2** | **masafee-ctf-7b** *(このプロジェクト)* | **テキスト生成 (QLoRA on LLM)** |

---

© 2026 Masato Suzuki — [masafy.org](https://masafy.org/) · [ORCID 0009-0000-7977-2756](https://orcid.org/0009-0000-7977-2756) · [GitHub @masafykun](https://github.com/masafykun)
