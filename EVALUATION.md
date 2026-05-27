# Evaluation Report: masafee-ctf-7b

> *日本語版*: [EVALUATION_ja.md](EVALUATION_ja.md)

This document reports the empirical evaluation of **masafee-ctf-7b**, a 7B-parameter
language model fine-tuned via QLoRA on CTF (Capture-the-Flag) writeup text, against
two reference models on two cybersecurity benchmarks. The intent is to characterize
behavioral differences induced by writeup-style continued pretraining, not to claim
generalized superiority.

---

## Models Evaluated

| Model | Base | Size | Quantization | Source |
|---|---|---|---|---|
| `qwen2.5-coder:7b` | Qwen 2.5 Coder 7B Instruct | 4.7 GB | Q4_K_M | Alibaba (Apache 2.0) |
| `masafee-ctf-7b` | Qwen 2.5 Coder 7B Instruct + QLoRA | 4.4 GB | Q4_K_M | This work |
| `foundation-sec-8b` | Llama 3.1 8B + Cisco continued-pretraining | 8.5 GB | Q8_0 | Cisco / fdtn-ai ([paper](https://arxiv.org/abs/2508.01059)) |

### Training of masafee-ctf-7b

- **Data:** [`justinwangx/CTFtime`](https://huggingface.co/datasets/justinwangx/CTFtime) — 18,013 writeup chunks scraped from CTFtime.org. After length filtering (500 < chars < 8,000) and tokenization into 2,048-token packed sequences, ~5,200 training chunks (10.6M tokens) were used.
- **Method:** QLoRA via [unsloth](https://github.com/unslothai/unsloth), r=32, α=64, learning rate 2e-4, 2 epochs.
- **Hardware:** Single NVIDIA GeForce RTX 3060 12 GB.
- **Time:** 12 h 17 m wall clock.
- **Strategy:** continued pretraining on raw writeup text (no instruction-format conversion). This was a deliberate choice to study what continued pretraining alone induces.

### Important Caveat on the Comparison with Foundation-Sec-8B

Cisco's **Foundation-Sec-8B-Instruct** is designed for security operations centers
(SOCs) — threat intelligence summarization, vulnerability classification, incident
triage. It is **not** built for solving CTF challenges. The comparison in this
document evaluates both models on cybersecurity benchmarks, but the CTF context
necessarily favors writeup-trained behavior. Readers should not interpret
single-context performance differences as a general capability ranking.

The quantization levels also differ (Q4_K_M vs Q8_0), so size and inference-speed
numbers in this report should be read as "the configurations as published," not
as a like-for-like architectural comparison.

---

## Benchmark 1: CyberMetric-500 (Multiple-Choice Knowledge)

[CyberMetric](https://huggingface.co/datasets/tihanyin/CyberMetric) is a 10,000-question
cybersecurity multiple-choice benchmark generated via Retrieval-Augmented Generation
over NIST publications, RFCs, and public security texts ([Tihanyi et al., IEEE CSR 2024](https://arxiv.org/abs/2402.07688)).
The 500-item subset was used. Each item presents a question, four options (A–D),
and a labeled correct answer. Models were prompted with the same MCQ template via
Ollama's `/api/chat`; outputs were parsed for the first letter A–D.

### Results

| Model | Accuracy | Correct / Total | Wall time |
|---|---|---|---|
| `qwen2.5-coder:7b` | 86.20% | 431 / 500 | 63 s |
| `masafee-ctf-7b` | 84.00% | 420 / 500 | 69 s |
| `foundation-sec-8b` | 82.60% | 413 / 500 | 308 s |

### Statistical Notes

- The 95% confidence interval around a binomial proportion of ~0.85 with n=500
  is approximately ±3.1 percentage points. All three models fall within the same
  CI band; the differences are not statistically significant at α=0.05.
- The substantial wall-time difference (5× factor) is primarily attributable to the
  quantization-level difference (Q8_0 vs Q4_K_M), not architectural differences.

### Observation

CTF-writeup continued pretraining did not produce a measurable knowledge gain on
generalized cybersecurity MCQs; it also did not produce a measurable degradation.
masafee-ctf-7b's accuracy lies between Base and Foundation-Sec-8B and within
sampling noise of both.

---

## Benchmark 2: NYU CTF Bench (Single-Shot, 30-Challenge Subset)

[NYU CTF Bench](https://nyu-llm-ctf.github.io) ([Shao et al., NeurIPS 2024](https://arxiv.org/abs/2406.05590))
provides 200 test-set CTF challenges with metadata, distributed files, and reference
flags. The official benchmark protocol is agentic (multi-turn execution in a
sandbox). For this evaluation, a **single-shot, non-agentic protocol** was used
instead: each challenge's `challenge.json` description, README, and distributed
files were embedded in a single prompt, and the model was asked to produce a
solution narrative ending with `FLAG: <value>`. Auto-scoring required the
reference flag (or its inner `{...}` content) to appear in the model output.

This protocol is strictly weaker than the official benchmark. Results are not
directly comparable to published NYU CTF Bench numbers and should be read as
characterizing single-shot capability only.

### Subset Composition

Random sample (seed 42), stratified by category:

| Category | n |
|---|---|
| crypto | 6 |
| rev | 6 |
| pwn | 6 |
| misc | 4 |
| web | 4 |
| forensics | 4 |
| **Total** | **30** |

### Results

| Model | Correct / 30 | Accuracy |
|---|---|---|
| `qwen2.5-coder:7b` | 4 | 13.3% |
| `foundation-sec-8b` | 2 | 6.7% |
| `masafee-ctf-7b` | 0 | 0.0% |

Per-category breakdown:

| Category | `qwen2.5-coder` | `masafee-ctf-7b` | `foundation-sec-8b` |
|---|---|---|---|
| crypto | 0 / 6 | 0 / 6 | 0 / 6 |
| rev | 1 / 6 | 0 / 6 | 1 / 6 |
| pwn | 1 / 6 | 0 / 6 | 0 / 6 |
| misc | 1 / 4 | 0 / 4 | 1 / 4 |
| web | 0 / 4 | 0 / 4 | 0 / 4 |
| forensics | 1 / 4 | 0 / 4 | 0 / 4 |

### Failure Mode Analysis

Manual inspection of `masafee-ctf-7b` outputs revealed that the model frequently
produces writeup-formatted narrative ("# CSAW 2023 - target_practice / ## Solution / ...")
that consumes the 800-token output budget before reaching a concrete flag string.
On at least one challenge (`2017q-pwn-pilot`), the model generated a coherent
writeup for an unrelated problem (describing a menu-based ordering program instead
of the actual quadcopter-themed challenge), suggesting that writeup-format priors
override prompt-specific content. This is consistent with style overfitting in
small-scale continued pretraining.

`foundation-sec-8b`'s lower score reflects its design: it produces measured
threat-analysis prose rather than committing to specific flag values.

`qwen2.5-coder:7b`'s 13.3% likely reflects a mixture of (a) pretraining-data
overlap with publicly available CSAW writeups, (b) successful inference from
challenge metadata, and (c) the chosen subset's relative tractability. It does
not imply functional CTF-solving capability at this model scale.

For context, the NYU CTF Bench paper reports that 32B open-weight models reach
≈31.9% Pass@1 with agent harnesses; 7B-class single-shot performance is expected
to be substantially below this.

---

## Stylistic Analysis: Output Behavior on CTF Prompts

Beyond flag accuracy, the three models exhibit different surface behaviors on
identical CTF prompts. The following metrics were measured across the 30-challenge
output set.

### Quantitative Measures

| Measure | `masafee-ctf-7b` | `foundation-sec-8b` |
|---|---|---|
| Average output length | 1,860 chars | 1,903 chars |
| Distinct CTF tool/technique terms used | 22 | 21 |
| Hedging-language occurrences (30 outputs, sum) | 7 | 77 |

The hedging-language metric counts occurrences of `might be`, `possibly`, `could be`,
`perhaps`, `may have`, `appears to`, `seems to`, and `unable to determine`. The
~11× ratio is the largest behavioral divergence observed.

### Interpretation

Hedging language is **functionally appropriate** in SOC and threat-intelligence
contexts, where premature commitment to a specific exploit hypothesis can mislead
analysts. Foundation-Sec-8B's higher hedging frequency aligns with its stated
design goals. CTF writeups, by contrast, are after-the-fact narratives that
state what worked; this prior surfaces in masafee-ctf-7b's output as more
direct, command-oriented phrasing. The same prior is also responsible for the
failure mode described above (committing to incorrect specific narratives).

### Side-by-Side Example (crypto: `2022q-cry-beyond_quantum`)

**`foundation-sec-8b`** (selected excerpt):

> The challenge seems to be based on the NTRU cryptosystem... there are several
> potential vulnerabilities or oversights:
> 1. Key Generation: The key generation process might not be secure enough...
> 2. Error Handling: There's a possibility of an error handling issue...

**`masafee-ctf-7b`** (selected excerpt):

> The vulnerability here is that the polynomial `f` can be recovered from `h`,
> `g` and `p`.
>
> 1. We know `h = f * g mod q`
> 2. We also know `q = 2^k - 1` for some k, so we can write `h = f * g + q * m`
> 3. Since `g` and `p` are known, we can compute `f_p = invert(f, R) mod p` …

Neither output yields a correct flag for the challenge. The contrast illustrates
the two distinct priors induced by the respective training corpora — neither is
"better" in absolute terms, but they will be appropriate or inappropriate
depending on downstream application.

---

## Conclusions

1. **On generalized cybersecurity MCQs (CyberMetric-500)**, the three models
   perform within statistical noise of each other (84.0% / 86.2% / 82.6%). CTF
   writeup pretraining produced neither measurable gain nor degradation in
   knowledge-MCQ accuracy.

2. **On single-shot CTF challenge solving (NYU CTF subset)**, all three models
   perform poorly (0% / 13.3% / 6.7%); none demonstrate practical CTF-solving
   ability under this protocol. The 7B scale and the absence of an agent harness
   are limiting factors independent of training data.

3. **Stylistically, masafee-ctf-7b produces ~11× less hedging language** than
   Foundation-Sec-8B and ~5× more direct procedural instructions. This reflects
   their respective training-data domains (CTF writeups vs SOC analysis text)
   rather than a quality difference.

4. **Continued pretraining on raw writeup text functions as style transfer**,
   not capability transfer. masafee-ctf-7b acquires writeup formatting and
   terminology but does not acquire problem-solving ability beyond the Base
   model. In several cases the acquired style actively impedes correct flag
   extraction (the output is structured as a writeup and exhausts the token
   budget before the flag).

These results are consistent with prior findings that small-model continued
pretraining on narrow corpora primarily induces surface-form adaptation rather
than improved task performance, and that style overfitting can degrade
task-relevant outputs.

---

## Reproducibility

- **Hardware:** NVIDIA GeForce RTX 3060 12 GB
- **Training cost:** ≈150 JPY in electricity; 0 JPY in cloud compute
- **Scripts:**
  - Training data preparation: [`scripts/prepare_data.py`](scripts/prepare_data.py)
  - QLoRA training: [`scripts/train.py`](scripts/train.py)
  - Before/after inference comparison: [`scripts/compare_inference.py`](scripts/compare_inference.py)
  - LoRA merge + GGUF export: [`scripts/export_gguf.py`](scripts/export_gguf.py)
  - CyberMetric evaluation: [`scripts/eval_cybermetric.py`](scripts/eval_cybermetric.py)
  - NYU CTF evaluation: [`scripts/eval_nyu_ctf.py`](scripts/eval_nyu_ctf.py)
- **Random seeds:** 42 throughout.

---

## References

- Tihanyi et al., *CyberMetric: A Benchmark Dataset based on Retrieval-Augmented Generation for Evaluating LLMs in Cybersecurity Knowledge*, IEEE CSR 2024. [arXiv:2402.07688](https://arxiv.org/abs/2402.07688)
- Shao et al., *NYU CTF Bench: A Scalable Open-Source Benchmark Dataset for Evaluating LLMs in Offensive Security*, NeurIPS 2024 D&B. [arXiv:2406.05590](https://arxiv.org/abs/2406.05590)
- fdtn-ai team, *Foundation-Sec-8B*, 2025. [arXiv:2508.01059](https://arxiv.org/abs/2508.01059)
- Hui et al., *Qwen2.5-Coder Technical Report*, 2024. [arXiv:2409.12186](https://arxiv.org/abs/2409.12186)
- Daniel et al., *Unsloth: 2x Faster Open Source Fine-Tuning*, 2024. [github.com/unslothai/unsloth](https://github.com/unslothai/unsloth)

---

© 2026 Masato Suzuki — [ORCID 0009-0000-7977-2756](https://orcid.org/0009-0000-7977-2756) — [masafy.org](https://masafy.org/)
