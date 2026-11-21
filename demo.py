"""Command-line demo for PumpGuard AI."""
from __future__ import annotations
import argparse
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt
from .signals import generate_signal
from .features import extract_features, demo_health_score



def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a synthetic pump vibration demo.")
    parser.add_argument("--condition", choices=["healthy", "imbalance", "bearing_like"], default="healthy")
    parser.add_argument("--rpm", type=float, default=1800)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    t, x = generate_signal(args.condition, rpm=args.rpm, seed=args.seed)
    feats = extract_features(x)
    score = demo_health_score(feats)
    out = Path("outputs")
    out.mkdir(exist_ok=True)
    csv_path = out / f"{args.condition}_signal.csv"
    pd.DataFrame({"time_s": t, "vibration": x}).to_csv(csv_path, index=False)
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(t, x, linewidth=0.8)
    ax.set(title=f"Synthetic vibration: {args.condition} (RPM={args.rpm:g})", xlabel="Time (s)", ylabel="Amplitude (arbitrary units)")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    plot_path = out / f"{args.condition}_signal.png"
    fig.savefig(plot_path, dpi=150)
    plt.close(fig)
    print(f"Condition: {args.condition} (synthetic demo)")
    for key, value in feats.items():
        print(f"{key}: {value:.4f}")
    print(f"Toy health score (not calibrated): {score}/100")
    print(f"Saved CSV: {csv_path}\nSaved plot: {plot_path}")

if __name__ == "__main__":
    main()
