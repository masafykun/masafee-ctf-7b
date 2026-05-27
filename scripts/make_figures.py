"""Generate figures from training logs and eval summaries.

Outputs PNG files into figures/ at repo root:
  - loss_curve.png       Training & eval loss across 2 epochs
  - cybermetric_bar.png  3-model accuracy on CyberMetric-500
  - nyu_ctf_bar.png      3-model solved on NYU CTF Bench (30q)
  - hedging_bar.png      Hedging language frequency
"""
import json
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent
FIG = ROOT / "figures"
FIG.mkdir(exist_ok=True)

# ---------- 1. Training loss curve ----------
with open(ROOT / "eval" / "trainer_state.json") as f:
    state = json.load(f)
hist = state["log_history"]
train_steps = [e["step"] for e in hist if "loss" in e]
train_loss = [e["loss"] for e in hist if "loss" in e]
eval_steps = [e["step"] for e in hist if "eval_loss" in e]
eval_loss = [e["eval_loss"] for e in hist if "eval_loss" in e]

fig, ax = plt.subplots(figsize=(8, 4.5), dpi=120)
ax.plot(train_steps, train_loss, color="#2563eb", linewidth=1.2, label="Train loss")
if eval_loss:
    ax.scatter(eval_steps, eval_loss, color="#dc2626", s=60, zorder=5,
               label=f"Eval loss (final={eval_loss[-1]:.3f})")
ax.axvline(x=618, color="#9ca3af", linestyle="--", linewidth=0.8, alpha=0.7)
ax.text(618, max(train_loss) * 0.98, "  Epoch 2 start", color="#6b7280", fontsize=9, va="top")
ax.set_xlabel("Training step")
ax.set_ylabel("Loss")
ax.set_title("masafee-ctf-7b: QLoRA training loss (2 epochs, 1,236 steps, RTX 3060 12GB)")
ax.legend(loc="upper right", frameon=False)
ax.grid(True, alpha=0.25)
fig.tight_layout()
fig.savefig(FIG / "loss_curve.png", bbox_inches="tight")
plt.close(fig)
print(f"wrote {FIG/'loss_curve.png'}  (final train loss={train_loss[-1]:.3f}, eval loss={eval_loss[-1]:.3f})")

# ---------- 2. CyberMetric-500 accuracy ----------
with open(ROOT / "eval" / "cybermetric" / "summary.json") as f:
    cm = json.load(f)
labels = ["Base\nQwen 2.5 Coder 7B", "masafee-ctf-7b", "Foundation-Sec-8B\n(Cisco)"]
order = ["base-qwen-coder", "masafee-ctf-7b", "foundation-sec-8b"]
by_label = {r["label"]: r for r in cm}
accs = [by_label[k]["acc"] for k in order]
colors = ["#6b7280", "#7c3aed", "#0ea5e9"]

fig, ax = plt.subplots(figsize=(7, 4.5), dpi=120)
bars = ax.bar(labels, accs, color=colors, edgecolor="#1f2937", linewidth=0.6)
ax.axhline(y=84.0, color="#9ca3af", linestyle=":", linewidth=0.8, alpha=0.7)
ax.fill_between([-0.5, 2.5], [80.9, 80.9], [87.1, 87.1], color="#e5e7eb", alpha=0.45,
                label="95% CI band (±3.1pp around masafee)")
for bar, val in zip(bars, accs):
    ax.text(bar.get_x() + bar.get_width()/2, val + 0.6, f"{val:.2f}%",
            ha="center", fontsize=11, fontweight="bold")
ax.set_ylabel("Accuracy (%)")
ax.set_ylim(70, 95)
ax.set_xlim(-0.5, 2.5)
ax.set_title("CyberMetric-500 (general cybersecurity knowledge MCQ, n=500)")
ax.legend(loc="lower right", frameon=False, fontsize=9)
ax.grid(True, axis="y", alpha=0.25)
fig.tight_layout()
fig.savefig(FIG / "cybermetric_bar.png", bbox_inches="tight")
plt.close(fig)
print(f"wrote {FIG/'cybermetric_bar.png'}")

# ---------- 3. NYU CTF Bench solved ----------
with open(ROOT / "eval" / "nyu_ctf" / "summary.json") as f:
    ny = json.load(f)
solved = [ny[k]["correct"] for k in order]

fig, ax = plt.subplots(figsize=(7, 4.5), dpi=120)
bars = ax.bar(labels, solved, color=colors, edgecolor="#1f2937", linewidth=0.6)
for bar, val in zip(bars, solved):
    ax.text(bar.get_x() + bar.get_width()/2, val + 0.1, f"{val}/30",
            ha="center", fontsize=11, fontweight="bold")
ax.set_ylabel("Challenges solved (of 30)")
ax.set_ylim(0, 6)
ax.set_title("NYU CTF Bench — 30-challenge subset, single-shot pass@1")
ax.grid(True, axis="y", alpha=0.25)
fig.tight_layout()
fig.savefig(FIG / "nyu_ctf_bar.png", bbox_inches="tight")
plt.close(fig)
print(f"wrote {FIG/'nyu_ctf_bar.png'}")

# ---------- 4. Hedging language frequency ----------
hedging = {"masafee-ctf-7b": 7, "foundation-sec-8b": 77}
fig, ax = plt.subplots(figsize=(6.5, 4), dpi=120)
labels2 = ["masafee-ctf-7b\n(writeup-trained)", "Foundation-Sec-8B\n(SOC-tuned)"]
vals2 = [hedging["masafee-ctf-7b"], hedging["foundation-sec-8b"]]
colors2 = ["#7c3aed", "#0ea5e9"]
bars = ax.bar(labels2, vals2, color=colors2, edgecolor="#1f2937", linewidth=0.6)
for bar, val in zip(bars, vals2):
    ax.text(bar.get_x() + bar.get_width()/2, val + 1.5, str(val),
            ha="center", fontsize=12, fontweight="bold")
ratio = vals2[1] / vals2[0]
ax.annotate(f"{ratio:.0f}× more hedging in SOC-tuned model",
            xy=(1, vals2[1]), xytext=(0.4, vals2[1] - 15),
            fontsize=10, color="#374151",
            arrowprops=dict(arrowstyle="->", color="#9ca3af", lw=0.8))
ax.set_ylabel("Hedging-language occurrences (sum over 30 CTF outputs)")
ax.set_ylim(0, max(vals2) + 15)
ax.set_title("Hedging language: writeup style vs SOC style")
ax.grid(True, axis="y", alpha=0.25)
fig.tight_layout()
fig.savefig(FIG / "hedging_bar.png", bbox_inches="tight")
plt.close(fig)
print(f"wrote {FIG/'hedging_bar.png'}")

print("done.")
