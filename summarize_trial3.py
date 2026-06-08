import os, pandas as pd

base = r"C:\Users\Ben-PC\Documents\SolitaireGDL\1780653626\1780653626"

# History generation method breakdown
print("History 'Generation Method' breakdown per generation:")
for g in range(10):
    gdir = os.path.join(base, f"g{g}")
    hist_path = os.path.join(gdir, "history.csv")
    if not os.path.exists(hist_path):
        continue
    hist = pd.read_csv(hist_path)
    if "Generation Method" in hist.columns:
        counts = hist["Generation Method"].value_counts()
        print(f"  g{g}: {dict(counts)}")
