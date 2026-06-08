import os, pandas as pd

base = r"C:\Users\Ben-PC\Documents\SolitaireGDL\1780653626\1780653626"

print("Gen | N_games | Win>0 | Win=1 | Max_win | Avg_win | Top5_games (win, moves, card_use)")
print("-" * 100)

for g in range(10):
    gdir = os.path.join(base, f"g{g}")
    eval_path = os.path.join(gdir, "evaluation.csv")
    if not os.path.exists(eval_path):
        continue

    df = pd.read_csv(eval_path)
    summary = df.groupby("Game").agg(
        win_rate=("Win", "mean"),
        avg_moves=("Move Count", "mean"),
        avg_card_usage=("Card Usage", "mean"),
    )

    n_games = len(summary)
    win_any = (summary["win_rate"] > 0).sum()
    win_all = (summary["win_rate"] == 1.0).sum()
    max_win = summary["win_rate"].max()
    avg_win = summary["win_rate"].mean()

    top5 = summary.sort_values("win_rate", ascending=False).head(5)
    top5_str = ", ".join(
        f"{name}({row.win_rate:.1f} w, {row.avg_moves:.0f} mv, {row.avg_card_usage:.2f} cu)"
        for name, row in top5.iterrows()
    )

    print(f"g{g:2d} | {n_games:7d} | {win_any:5d} | {win_all:5d} | {max_win:.2f}    | {avg_win:.3f}   | {top5_str}")

print()

# History origin breakdown per generation
print("\nHistory origin breakdown per generation:")
for g in range(10):
    gdir = os.path.join(base, f"g{g}")
    hist_path = os.path.join(gdir, "history.csv")
    if not os.path.exists(hist_path):
        continue
    hist = pd.read_csv(hist_path)
    origin_col = next((c for c in hist.columns if "origin" in c.lower()), None)
    if origin_col:
        counts = hist[origin_col].value_counts()
        print(f"  g{g}: {dict(counts)}")
    else:
        print(f"  g{g}: columns={hist.columns.tolist()}")
