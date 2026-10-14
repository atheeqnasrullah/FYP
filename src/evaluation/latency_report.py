"""Summarise camera-frame-to-game latency logged by the games (data/logs/latency_*.csv).

Latency = time the game consumed a fused command minus the capture time of the
camera frame whose label it carries (MediaPipe, smoothing, fusion polling and
the game loop are all included). Target from plan.md: under 300 ms.
"""
import argparse
import pandas as pd
from src.utils.config import ROOT

TARGET_MS = 300


def summarise(frame):
    grouped = frame.groupby(["game", "mode"]).latency_ms
    out = grouped.agg(samples="size", median_ms="median", mean_ms="mean",
                      p95_ms=lambda x: x.quantile(.95), max_ms="max").reset_index()
    out["within_target_pct"] = grouped.apply(lambda x: 100 * (x < TARGET_MS).mean()).to_numpy()
    return out.round(1)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Latency summary against the 300 ms target")
    parser.add_argument("--logs", default=str(ROOT / "data/logs"))
    args = parser.parse_args(argv)
    paths = sorted(__import__("pathlib").Path(args.logs).glob("latency_*.csv"))
    if not paths: raise SystemExit("No latency logs yet. Play a game in vision or live mode, then press Esc.")
    summary = summarise(pd.concat([pd.read_csv(p) for p in paths], ignore_index=True))
    dest = ROOT / "results/tables/latency_summary.csv"; dest.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(dest, index=False); print(summary.to_string(index=False)); print(f"Target: < {TARGET_MS} ms. Saved {dest}")

if __name__ == "__main__": main()
