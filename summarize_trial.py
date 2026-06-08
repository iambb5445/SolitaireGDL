import os, pandas as pd, sys

base = r"C:\Users\Ben-PC\Documents\SolitaireGDL\1780653626\1780653626"

for g in range(10):
    gdir = os.path.join(base, f"g{g}")
    eval_path = os.path.join(gdir, "evaluation.csv")
    hist_path = os.path.join(gdir, "history.csv")
    if not os.path.exists(eval_path):
        continue

    print(f"\n=== Generation {g} ===")

    df = pd.read_csv(eval_path)
    summary = df.groupby("Game").agg(
        win_rate=("Win", "mean"),
        avg_moves=("Move Count", "mean"),
        exhausted_rate=("Exhausted", "mean"),
        avg_card_usage=("Card Usage", "mean"),
        avg_pile_usage=("Pile Usage", "mean")
    ).sort_values("win_rate", ascending=False)
    print(summary.to_string())

    if os.path.exists(hist_path):
        hist = pd.read_csv(hist_path)
        print(f"\nHistory ({len(hist)} games):")
        if "Origin" in hist.columns:
            print(hist["Origin"].value_counts().to_string())
        elif "origin" in hist.columns:
            print(hist["origin"].value_counts().to_string())
        else:
            print("Columns:", hist.columns.tolist())
            print(hist.head(3).to_string())
