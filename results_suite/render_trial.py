"""
Render evolution trial gallery + 2D/3D diversity space.

Expensive work (game rendering, pairwise diffs, MDS) is cached to JSON so
re-running only regenerates the HTML.

Usage:
    python results_suite/render_trial.py <trial_dir> [options]

    --out PATH          Output HTML (default: <trial_dir>/gallery.html)
    --gens 0,3,5        Only include these generations
    --cache-dir DIR     Cache location (default: results_suite/cache/)
    --force             Recompute everything even if cache exists
    --no-diversity      Skip diversity tabs (faster HTML-only rebuild)
"""

from __future__ import annotations
import os, sys, argparse, base64, io, json, traceback, time
import pandas as pd
import numpy as np

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
import pygame

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from parser import Parser
from diffs import Diffs
from game import Game
from gui import GameGraphic, TextureRepo, SCREEN_WIDTH, SCREEN_HEIGHT

THUMB_W = 400
THUMB_H = 267

VERDICT_OK          = "OK"
VERDICT_EXTRA_CARD  = "EXTRA_CARD"
VERDICT_EXTRA_PILE  = "EXTRA_PILE"
VERDICT_TRIVIAL     = "TRIVIAL"
VERDICT_IMPOSSIBLE  = "IMPOSSIBLE"
VERDICT_UNKNOWN     = "UNKNOWN"
VERDICT_ERROR       = "ERROR"

GEN_COLORS = ['#e74c3c','#e67e22','#f1c40f','#2ecc71','#1abc9c',
              '#3498db','#9b59b6','#e91e8c','#00bcd4','#8bc34a']


# ── Eval / history loading ────────────────────────────────────────────────────

def compute_verdict(win_rate, exhausted_rate, win_rows):
    if exhausted_rate > 0.9:           return VERDICT_UNKNOWN
    if win_rate < 0.1:                 return VERDICT_IMPOSSIBLE
    if len(win_rows) == 0:             return VERDICT_IMPOSSIBLE
    if win_rows["Move Count"].mean() < 20:         return VERDICT_TRIVIAL
    if (win_rows["Card Usage"] < 0.9).any():       return VERDICT_EXTRA_CARD
    if (win_rows["Pile Usage"] < 0.8).any():       return VERDICT_EXTRA_PILE
    return VERDICT_OK

def compute_score(win_rate, verdict, win_rows):
    if verdict in (VERDICT_UNKNOWN, VERDICT_IMPOSSIBLE, VERDICT_ERROR): return 0.0
    if verdict == VERDICT_TRIVIAL: return 0.05 + win_rate * 0.05
    win_sweet    = max(0.15, 1.0 - abs(win_rate - 0.5) * 1.6)
    win_moves    = win_rows["Move Count"].mean() if len(win_rows) else 0
    moves_factor = min(win_moves / 300.0, 1.0)
    win_cu = win_rows["Card Usage"].mean() if len(win_rows) else 0.0
    win_pu = win_rows["Pile Usage"].mean() if len(win_rows) else 0.0
    mult   = 1.0 if verdict == VERDICT_OK else 0.7
    return mult * win_sweet * moves_factor * win_cu * win_pu

def load_eval_data(gen_dir):
    path = os.path.join(gen_dir, "evaluation.csv")
    if not os.path.exists(path): return {}
    df = pd.read_csv(path)
    result = {}
    for name, group in df.groupby("Game"):
        win_mask = group["Win"].astype(bool)
        win_rows = group[win_mask]
        win_rate       = float(group["Win"].mean())
        exhausted_rate = float(group["Exhausted"].mean())
        verdict = compute_verdict(win_rate, exhausted_rate, win_rows)
        score   = compute_score(win_rate, verdict, win_rows)
        result[str(name)] = dict(
            win_rate=win_rate,
            avg_moves=float(group["Move Count"].mean()),
            avg_card_usage=float(group["Card Usage"].mean()),
            avg_pile_usage=float(group["Pile Usage"].mean()),
            exhausted_rate=exhausted_rate,
            verdict=verdict,
            score=score,
            sgdl_hash=int(group["SGDL Hash"].iloc[0]),
        )
    return result

def load_history(gen_dir):
    path = os.path.join(gen_dir, "history.csv")
    if not os.path.exists(path): return {}
    df = pd.read_csv(path)
    result = {}
    for _, row in df.iterrows():
        name = str(row.get("Name",""))
        result[name] = dict(
            method=str(row.get("Generation Method","")),
            parent1=str(row.get("Parent 1","")),
            parent2=str(row.get("Parent 2","")),
        )
    return result

def find_trial_dirs(workspace: str) -> list[str]:
    """Find all trial directories (containing g0/, g1/, ...) in a workspace."""
    results = []
    for entry in sorted(os.listdir(workspace)):
        full = os.path.join(workspace, entry)
        if not os.path.isdir(full):
            continue
        if os.path.isdir(os.path.join(full, 'g0')):
            results.append(full)
        else:
            for sub in sorted(os.listdir(full)):
                subsub = os.path.join(full, sub)
                if os.path.isdir(subsub) and os.path.isdir(os.path.join(subsub, 'g0')):
                    results.append(subsub)
    return results


def trial_summary(data: dict) -> dict:
    nodes    = data["nodes"]
    last_gen = max(n["gen"] for n in nodes) if nodes else 0
    last_nodes = [n for n in nodes if n["gen"] == last_gen]
    scores   = [n["score"] for n in nodes]
    return {
        "id":        data["trial_id"],
        "n_gens":    last_gen + 1,
        "n_games":   len(nodes),
        "best":      round(max(scores), 3) if scores else 0,
        "last_avg":  round(sum(n["score"] for n in last_nodes) / len(last_nodes), 3) if last_nodes else 0,
        "ok_count":  sum(1 for n in nodes if n["verdict"] == VERDICT_OK),
    }


def find_generations(trial_dir):
    gens = [e for e in os.listdir(trial_dir)
            if os.path.isdir(os.path.join(trial_dir, e))
            and e.startswith("g") and not e.endswith("-best") and e[1:].isdigit()]
    return sorted(gens, key=lambda x: int(x[1:]))

def find_sgdl_files(gen_dir):
    files = [f for f in os.listdir(gen_dir) if f.endswith(".sgdl")]
    return sorted(files, key=lambda f: int(f.split("_")[0]))


# ── Rendering ─────────────────────────────────────────────────────────────────

def render_game(sgdl_path):
    game   = Parser.from_file(sgdl_path, seed=0, should_log=False, should_start=True)
    screen = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
    screen.fill((34, 139, 34))
    GameGraphic(game).render(screen)
    return screen, game

def surface_to_b64(surface):
    thumb = pygame.transform.smoothscale(surface, (THUMB_W, THUMB_H))
    buf   = io.BytesIO()
    pygame.image.save(thumb, buf, "PNG")
    return base64.b64encode(buf.getvalue()).decode()


# ── Distances + MDS ──────────────────────────────────────────────────────────

def compute_distance_matrix(games):
    n, mat = len(games), np.zeros((len(games), len(games)), dtype=np.float32)
    total  = n * (n-1) // 2
    done, t0 = 0, time.perf_counter()
    for i in range(n):
        for j in range(i+1, n):
            d = games[i].diff(games[j], True, Diffs.get_sum_normalized_diff_normalized)
            mat[i,j] = mat[j,i] = d.get_sum_normalized_diff_normalized()
            done += 1
            if done % 500 == 0 or done == total:
                el  = time.perf_counter() - t0
                eta = (total-done) / (done/el) if done else 0
                print(f"  diffs {done}/{total}  {el:.0f}s  ETA {eta:.0f}s", flush=True)
    return mat

def mds_embed(dist_matrix, n_components):
    from sklearn.manifold import MDS
    mds    = MDS(n_components=n_components, dissimilarity="precomputed",
                 random_state=42, normalized_stress="auto")
    coords = mds.fit_transform(dist_matrix)
    for ax in range(n_components):
        lo, hi = coords[:,ax].min(), coords[:,ax].max()
        if hi > lo: coords[:,ax] = 2*(coords[:,ax]-lo)/(hi-lo) - 1
    return coords


def render_score_heatmap(nodes: list[dict]) -> str:
    """
    Nadaraya-Watson density-invariant score field over the 3D MDS XY plane.

    For each grid pixel p:
        score(p) = sum_i [ K(||p - xi||) * score_i ] / sum_i [ K(||p - xi||) ]

    Dividing by the total kernel weight cancels out local point density,
    so a dense cluster of low-score games does not bleed into sparse high-score
    regions (and vice-versa).

    Black = 0, White = 1.0
    """
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.colors import LinearSegmentedColormap

    xs     = np.array([n['x3'] for n in nodes], dtype=np.float32)
    ys     = np.array([n['y3'] for n in nodes], dtype=np.float32)
    scores = np.array([n['score'] for n in nodes], dtype=np.float32)

    # Silverman bandwidth for 2-D KDE, then back off slightly for crisper field
    n   = len(nodes)
    bw  = 1.06 * float(np.std(np.concatenate([xs, ys]))) * n ** (-1/5) * 0.7
    bw  = max(bw, 0.05)
    print(f"  Score heatmap bandwidth = {bw:.4f}")

    # Build grid (float32 keeps memory manageable)
    RES = 200
    xi  = np.linspace(-1.1, 1.1, RES, dtype=np.float32)
    yi  = np.linspace(-1.1, 1.1, RES, dtype=np.float32)
    XX, YY = np.meshgrid(xi, yi)
    gx  = XX.ravel()  # (RES*RES,)
    gy  = YY.ravel()

    # Kernel weights: (RES*RES, n)  — float32, ~100MB peak for 200×200 & 700 nodes
    dx  = gx[:, None] - xs[None, :]
    dy  = gy[:, None] - ys[None, :]
    K   = np.exp(-(dx*dx + dy*dy) / (2.0 * bw*bw))  # Gaussian kernel

    denom = K.sum(axis=1)                             # (RES*RES,)
    numer = (K * scores[None, :]).sum(axis=1)         # (RES*RES,)

    H = np.where(denom > 1e-8, numer / denom, np.nan).reshape(RES, RES)

    # ── Render ────────────────────────────────────────────────────────────────
    fig, ax = plt.subplots(figsize=(10, 10), dpi=120)
    fig.patch.set_facecolor('#0d0d1a')
    ax.set_facecolor('#0d0d1a')
    ax.set_aspect('equal')
    ax.axis('off')

    cmap = LinearSegmentedColormap.from_list('score_field', ['black', 'white'])
    # nan regions shown as the dark background
    cmap.set_bad(color='#0d0d1a')

    im = ax.imshow(H, origin='lower', extent=[-1.1, 1.1, -1.1, 1.1],
                   cmap=cmap, vmin=0, vmax=1,
                   interpolation='bilinear', zorder=1)

    # Overlay nodes — colored by generation, sized by score
    node_cols  = [GEN_COLORS[n['gen'] % len(GEN_COLORS)] for n in nodes]
    node_sizes = [max(4, n['score'] * 40 + 4) for n in nodes]
    ax.scatter(xs, ys, s=node_sizes, c=node_cols, alpha=0.7,
               linewidths=0.4, edgecolors='#ffffff44', zorder=2)

    ax.set_xlim(-1.1, 1.1)
    ax.set_ylim(-1.1, 1.1)

    cb = plt.colorbar(im, ax=ax, fraction=0.03, pad=0.01)
    cb.ax.yaxis.set_tick_params(color='#888')
    plt.setp(cb.ax.yaxis.get_ticklabels(), color='#888', fontsize=8)
    cb.set_label('Score', color='#888', fontsize=9)

    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=120,
                facecolor=fig.get_facecolor(), bbox_inches='tight', pad_inches=0.05)
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode()


def compute_score_field_3d(nodes: list[dict], res: int = 20) -> list[dict]:
    """
    Nadaraya-Watson score estimate on a 3D grid over the MDS space.
    Returns [{x, y, z, s, w}] — only grid points with enough kernel support.
    Density-invariant: s(p) = sum K(d_i)*score_i / sum K(d_i)
    """
    xs     = np.array([n['x3'] for n in nodes], dtype=np.float32)
    ys     = np.array([n['y3'] for n in nodes], dtype=np.float32)
    zs     = np.array([n['z3'] for n in nodes], dtype=np.float32)
    scores = np.array([n['score'] for n in nodes], dtype=np.float32)

    n  = len(nodes)
    bw = 1.06 * float(np.std(np.concatenate([xs, ys, zs]))) * n ** (-1/5) * 0.8
    bw = max(bw, 0.06)
    print(f"  3D NW bandwidth = {bw:.4f}")

    xi         = np.linspace(-1.05, 1.05, res, dtype=np.float32)
    XX, YY, ZZ = np.meshgrid(xi, xi, xi)
    gx = XX.ravel()[:, None]
    gy = YY.ravel()[:, None]
    gz = ZZ.ravel()[:, None]

    # Gaussian kernel — (res³, n) at float32
    dx = gx - xs[None, :]
    dy = gy - ys[None, :]
    dz = gz - zs[None, :]
    K  = np.exp(-(dx*dx + dy*dy + dz*dz) / (2.0 * bw**2))

    denom  = K.sum(axis=1)
    numer  = (K * scores[None, :]).sum(axis=1)
    weight = denom / float(denom.max())           # normalised kernel support
    score  = np.where(denom > 1e-8, numer / denom, 0.0)

    mask   = weight > 0.015                       # skip near-empty voids
    gxf, gyf, gzf = XX.ravel(), YY.ravel(), ZZ.ravel()

    result = [
        {'x': round(float(gxf[i]), 3),
         'y': round(float(gyf[i]), 3),
         'z': round(float(gzf[i]), 3),
         's': round(float(score[i]), 3),
         'w': round(float(weight[i]), 3)}
        for i in np.where(mask)[0]
    ]
    print(f"  3D score field: {len(result)}/{res**3} points above threshold")
    return result


# ── Cache ─────────────────────────────────────────────────────────────────────

def get_cache_path(trial_dir, cache_dir):
    trial_id = os.path.basename(trial_dir)
    return os.path.join(cache_dir, f"{trial_id}_data.json"), \
           os.path.join(cache_dir, f"{trial_id}_dist.npy")

def save_cache(data_path, dist_path, data, dist_mat, unique_hashes):
    os.makedirs(os.path.dirname(data_path), exist_ok=True)
    # Save distance matrix as numpy
    np.save(dist_path, dist_mat)
    # Save everything else as JSON (includes b64 thumbnails)
    payload = dict(data, unique_hashes=unique_hashes)
    with open(data_path, "w", encoding="utf-8") as f:
        json.dump(payload, f)
    print(f"  Cache saved -> {data_path}")

def load_cache(data_path, dist_path):
    if not os.path.exists(data_path): return None, None, None
    print(f"  Loading cache from {data_path}...")
    with open(data_path, encoding="utf-8") as f:
        data = json.load(f)
    unique_hashes = data.pop("unique_hashes", None)
    dist_mat = np.load(dist_path) if os.path.exists(dist_path) else None
    return data, dist_mat, unique_hashes


# ── Compute trial data (rendering + diffs + MDS, with caching) ───────────────

def compute_trial_data(trial_dir, generations, cache_dir, force=False):
    """
    Returns data dict: {trial_id, nodes, edges}
    Nodes include b64_thumb, stats, MDS coords (x2,y2,x3,y3,z3).
    Uses cache if available.
    """
    data_path, dist_path = get_cache_path(trial_dir, cache_dir)

    # ── Try loading from cache ────────────────────────────────────────────────
    if not force:
        cached_data, cached_dist, cached_hashes = load_cache(data_path, dist_path)
        if cached_data is not None:
            # Verify generations match
            cached_gens = sorted(set(n["gen"] for n in cached_data["nodes"]))
            req_gens    = sorted(int(g[1:]) for g in generations)
            if cached_gens == req_gens:
                print(f"  Cache hit — {len(cached_data['nodes'])} nodes loaded")
                return cached_data

    # ── Render games ──────────────────────────────────────────────────────────
    trial_id   = os.path.basename(trial_dir)
    raw_nodes  = []   # nodes with game objects (not serialisable)

    for gen in generations:
        gen_dir    = os.path.join(trial_dir, gen)
        sgdl_files = find_sgdl_files(gen_dir)
        eval_data  = load_eval_data(gen_dir)
        history    = load_history(gen_dir)
        gen_idx    = int(gen[1:])
        gen_t0     = time.perf_counter()
        print(f"\n{gen}: {len(sgdl_files)} games", flush=True)

        def sort_key(fname):
            parts = fname.replace(".sgdl","").split("_")
            name  = "_".join(parts[1:-1]) if len(parts)>=3 else parts[-1]
            return -eval_data.get(name,{}).get("score",-1)

        for fname in sorted(sgdl_files, key=sort_key):
            parts     = fname.replace(".sgdl","").split("_")
            name      = "_".join(parts[1:-1]) if len(parts)>=3 else parts[-1]
            file_hash = int(parts[-1]) if len(parts)>=3 and parts[-1].isdigit() else None
            stats     = eval_data.get(name, {"verdict":VERDICT_ERROR,"score":0.0})
            hist      = history.get(name, {})
            node_id   = f"g{gen_idx}_{name}"

            b64 = None; game = None
            t0  = time.perf_counter()
            try:
                surface, game = render_game(os.path.join(gen_dir, fname))
                b64 = surface_to_b64(surface)
                print(f"  OK   {name:<28} score={stats.get('score',0):.3f}  "
                      f"{stats.get('verdict','?'):<12}  {time.perf_counter()-t0:.2f}s", flush=True)
            except Exception:
                stats = dict(stats); stats["verdict"]=VERDICT_ERROR; stats["score"]=0.0
                print(f"  FAIL {name:<28} {time.perf_counter()-t0:.2f}s  "
                      f"{traceback.format_exc().splitlines()[-1]}")

            raw_nodes.append(dict(
                id=node_id, name=name, gen=gen_idx,
                file_hash=file_hash,
                game=game, b64_thumb=b64 or "",
                stats=stats, hist=hist,
            ))

        print(f"  {gen} done in {time.perf_counter()-gen_t0:.1f}s")

    # ── Compute distances ─────────────────────────────────────────────────────
    valid     = [n for n in raw_nodes if n["game"] is not None]
    seen_hash: dict[int,int] = {}
    unique_games: list[Game] = []
    node_to_uid: dict[str,int] = {}

    for node in valid:
        h = node["game"].get_efficient_hash()
        if h not in seen_hash:
            seen_hash[h] = len(unique_games)
            unique_games.append(node["game"])
        node_to_uid[node["id"]] = seen_hash[h]

    n = len(unique_games)
    print(f"\nDiversity: {len(valid)} nodes, {n} unique — {n*(n-1)//2} pairs...")

    # Reuse cached distance matrix if hashes match
    _, cached_dist, cached_hashes = load_cache(data_path, dist_path)
    hash_list = list(seen_hash.keys())
    if (cached_dist is not None and cached_hashes == hash_list
            and cached_dist.shape == (n, n)):
        print("  Reusing cached distance matrix")
        dist_mat = cached_dist
    else:
        dist_mat = compute_distance_matrix(unique_games)

    print("  MDS 2D...")
    coords2 = mds_embed(dist_mat, 2)
    print("  MDS 3D...")
    coords3 = mds_embed(dist_mat, 3)

    # ── Build serialisable node list ─────────────────────────────────────────
    # hash_to_id: SGDL eval hash → node_id (matches Parent 1/2 in history.csv)
    hash_to_id: dict[int, str] = {}
    nodes_out = []
    for node in valid:
        uid  = node_to_uid[node["id"]]
        s    = node["stats"]
        h    = node["hist"]
        nd   = dict(
            id=node["id"], name=node["name"], gen=node["gen"],
            b64_thumb=node["b64_thumb"],
            score=round(s.get("score",0.0),4),
            verdict=s.get("verdict",VERDICT_ERROR),
            win_rate=round(s.get("win_rate",0.0),3),
            avg_moves=round(s.get("avg_moves",0.0),1),
            avg_card_usage=round(s.get("avg_card_usage",0.0),3),
            avg_pile_usage=round(s.get("avg_pile_usage",0.0),3),
            exhausted_rate=round(s.get("exhausted_rate",0.0),3),
            method=h.get("method",""),
            parent1=h.get("parent1",""),
            parent2=h.get("parent2",""),
            x2=round(float(coords2[uid,0]),4), y2=round(float(coords2[uid,1]),4),
            x3=round(float(coords3[uid,0]),4), y3=round(float(coords3[uid,1]),4),
            z3=round(float(coords3[uid,2]),4),
        )
        nodes_out.append(nd)
        # Key by (hash, gen) so the same game carried across gens resolves correctly
        eval_hash = s.get("sgdl_hash")
        if eval_hash is not None:
            hash_to_id[(eval_hash, node["gen"])] = node["id"]
        # Name lookup for best-of (parent fields are NaN, connection is by name)
        hash_to_id[("name", node["name"], node["gen"])] = node["id"]

    # ── Build edges ───────────────────────────────────────────────────────────
    edges_out = []
    for node in valid:
        h      = node["hist"]
        nid    = node["id"]
        g      = node["gen"]
        method = (h.get("method","") or "").lower()

        if "best" in method:
            # No parent hash stored — same game carried by name from previous gen
            pid = hash_to_id.get(("name", node["name"], g - 1))
            if pid and pid != nid:
                edges_out.append([pid, nid])
        else:
            for pfield in ("parent1", "parent2"):
                pval = h.get(pfield, "")
                if not pval or pval == "nan":
                    continue
                try:
                    phash = int(float(pval))
                    pid   = hash_to_id.get((phash, g - 1))
                    if pid and pid != nid:
                        edges_out.append([pid, nid])
                except (ValueError, TypeError):
                    pass
    print(f"  Built {len(edges_out)} lineage edges")

    data = dict(trial_id=trial_id, nodes=nodes_out, edges=edges_out)
    save_cache(data_path, dist_path, data, dist_mat, hash_list)
    return data


# ── HTML / CSS / JS ───────────────────────────────────────────────────────────

CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: system-ui, sans-serif; background: #1a1a2e; color: #eee; }

/* ── experiment nav ── */
#exp-nav {
    background:#06060f; border-bottom:1px solid #1a1a2a;
    padding:5px 14px; display:flex; align-items:center; gap:7px; flex-wrap:wrap;
}
#exp-nav .elabel { font-size:.68rem; color:#444; margin-right:2px; }
.exp-btn {
    font-size:.7rem; padding:3px 11px; border-radius:4px;
    border:1px solid #2a2a3a; background:#0d0d1a; color:#666;
    text-decoration:none; cursor:pointer; white-space:nowrap;
}
.exp-btn:hover  { border-color:#e2b96f; color:#e2b96f; }
.exp-btn.active { border-color:#e2b96f; color:#e2b96f; background:#1a150a; font-weight:600; }

#tabs { display:flex; background:#0d0d1a; border-bottom:2px solid #333; }
.tab-btn {
    padding:9px 22px; cursor:pointer; font-size:0.82rem; color:#777;
    border:none; background:none; border-bottom:2px solid transparent; margin-bottom:-2px;
}
.tab-btn.active { color:#e2b96f; border-bottom-color:#e2b96f; }
.tab-btn:hover  { color:#ddd; }

#toolbar {
    position:sticky; top:0; z-index:100;
    background:#0f0f1e; border-bottom:1px solid #333;
    padding:7px 14px; display:flex; align-items:center; gap:14px; flex-wrap:wrap;
}
#toolbar-title { font-size:0.95rem; color:#e2b96f; }
.ctrl-group { display:flex; align-items:center; gap:6px; }
.ctrl-group label { font-size:0.7rem; color:#aaa; white-space:nowrap; }
#score-slider { width:110px; accent-color:#e2b96f; }
#score-val { font-size:0.75rem; color:#e2b96f; min-width:30px; }
.tb-btn {
    font-size:0.68rem; padding:3px 9px; border-radius:4px;
    border:1px solid #555; background:#222; color:#ccc; cursor:pointer;
}
.tb-btn:hover { border-color:#e2b96f; color:#e2b96f; }
#gen-counts { font-size:0.68rem; color:#666; }

.gen-block { margin:10px 14px 26px; }
.gen-header {
    display:flex; align-items:baseline; gap:12px;
    padding:7px 0 5px; border-bottom:1px solid #2a2a3e; margin-bottom:8px;
}
.gen-title { font-size:1.05rem; color:#e2b96f; }
.gen-stats  { font-size:0.72rem; color:#666; }
.gen-visible-count { font-size:0.68rem; color:#444; margin-left:auto; }
.grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(185px,1fr)); gap:7px; }

.card {
    background:#16213e; border-radius:6px; overflow:hidden;
    border:2px solid transparent; transition:border-color 0.15s;
}
.card:hover { border-color:#e2b96f; }
.card img { width:100%; display:block; }
.card-body { padding:6px; }
.game-name {
    font-size:0.78rem; font-weight:600;
    white-space:nowrap; overflow:hidden; text-overflow:ellipsis; margin-bottom:3px;
}
.win-bar-wrap { background:#2a2a3e; border-radius:2px; height:4px; margin:3px 0; }
.win-bar { height:4px; border-radius:2px; }
.meta { font-size:0.65rem; color:#888; line-height:1.5; }
.score-pip { display:inline-block; width:7px; height:7px; border-radius:50%; margin-right:3px; vertical-align:middle; }
.badge {
    display:inline-block; font-size:0.55rem; padding:1px 4px;
    border-radius:10px; margin-right:3px; text-transform:uppercase;
    font-weight:700; letter-spacing:0.03em; vertical-align:middle;
}
.badge-random    { background:#3a5a8a; color:#bdf; }
.badge-mutation  { background:#5a3a8a; color:#dbf; }
.badge-crossover { background:#3a8a5a; color:#bfd; }
.badge-best      { background:#8a6a3a; color:#fed; }
.verdict-OK         { border-color:#2a5a2a; }
.verdict-EXTRA_CARD { border-color:#5a4a10; }
.verdict-EXTRA_PILE { border-color:#4a3a10; }
.verdict-TRIVIAL    { border-color:#5a3010; opacity:0.55; }
.verdict-IMPOSSIBLE { border-color:#5a1010; opacity:0.4; }
.verdict-UNKNOWN    { border-color:#303030; opacity:0.4; }
.verdict-ERROR      { border-color:#2a1010; opacity:0.35; }
.vlabel {
    display:inline-block; font-size:0.55rem; padding:1px 4px;
    border-radius:3px; font-weight:700; letter-spacing:0.04em;
    text-transform:uppercase; vertical-align:middle;
}
.vlabel-OK         { background:#1a4a1a; color:#7f7; }
.vlabel-EXTRA_CARD { background:#4a3a0a; color:#fd8; }
.vlabel-EXTRA_PILE { background:#3a2a0a; color:#eb7; }
.vlabel-TRIVIAL    { background:#4a2a0a; color:#fa8; }
.vlabel-IMPOSSIBLE { background:#4a0a0a; color:#f88; }
.vlabel-UNKNOWN    { background:#2a2a2a; color:#777; }
.vlabel-ERROR      { background:#2a0a0a; color:#a44; }

/* ── Shared diversity layout ── */
.div-pane-inner {
    display:flex; flex-direction:column; height:calc(100vh - 42px);
}
.div-toolbar {
    background:#0f0f1e; border-bottom:1px solid #333;
    padding:7px 14px; display:flex; align-items:center; gap:12px; flex-wrap:wrap;
    flex-shrink:0;
}
.div-toolbar span.label { font-size:0.8rem; color:#e2b96f; font-weight:600; }
.div-toolbar span.desc  { font-size:0.68rem; color:#555; }
.div-canvas-wrap { flex:1; position:relative; overflow:hidden; }
.div-canvas-wrap canvas { position:absolute; top:0; left:0; width:100%; height:100%; }
.div-tooltip {
    position:absolute; pointer-events:none; display:none;
    background:#0d0d1a; border:1px solid #444; border-radius:6px;
    padding:8px 10px; font-size:0.7rem; color:#ccc; max-width:220px;
    box-shadow:0 4px 12px rgba(0,0,0,.6); z-index:10;
}
.div-tooltip img { width:200px; display:block; margin-bottom:5px; border-radius:3px; }
.gen-chip {
    display:inline-block; font-size:0.62rem; padding:2px 8px;
    border-radius:10px; cursor:pointer; border:1px solid transparent;
    font-weight:600; transition:opacity .15s;
}
.gen-chip.off { opacity:0.3; }
"""

GALLERY_JS = """
// ── Gallery ────────────────────────────────────────────────────────────────
let scoreThreshold=0, showTrivial=true;

function scoreColor(s){
    if(s<=0)   return '#555';
    if(s<.05)  return '#a33';
    if(s<.15)  return '#c63';
    if(s<.35)  return '#c93';
    if(s<.6)   return '#9b3';
    return '#4c4';
}
function applyFilter(){
    let total=0;
    document.querySelectorAll('.gen-block').forEach(block=>{
        let vis=0;
        block.querySelectorAll('.card').forEach(c=>{
            const hide=parseFloat(c.dataset.score)<scoreThreshold||(c.dataset.trivial==='1'&&!showTrivial);
            c.style.display=hide?'none':'';
            if(!hide)vis++;
        });
        total+=vis;
        const ct=block.querySelector('.gen-visible-count');
        if(ct)ct.textContent=vis+' shown';
    });
    document.getElementById('gen-counts').textContent=total+' games shown';
}
function setThreshold(v){
    scoreThreshold=parseFloat(v);
    document.getElementById('score-val').textContent=parseFloat(v).toFixed(2);
    applyFilter();
}
function toggleTrivial(){
    showTrivial=!showTrivial;
    document.getElementById('trivial-btn').textContent=showTrivial?'Hide trivial':'Show trivial';
    applyFilter();
}

// ── Tabs ───────────────────────────────────────────────────────────────────
const PANES=['gallery','diversity2d','diversity3d','heatmap','timeline'];
function switchTab(name){
    document.querySelectorAll('.tab-btn').forEach(b=>b.classList.toggle('active',b.dataset.tab===name));
    PANES.forEach(p=>{ document.getElementById(p+'-pane').style.display='none'; });
    const target=document.getElementById(name+'-pane');
    target.style.display= name==='gallery' ? 'block' : 'flex';
    if(name==='diversity2d') resize2D();
    if(name==='diversity3d') resize3D();
    if(name==='heatmap')     resizeSF();
    if(name==='timeline')    resizeTimeline();
}

// Safe ready: fires immediately if DOM already loaded (handles live-reload)
function onReady(fn){ document.readyState!=='loading' ? fn() : window.addEventListener('DOMContentLoaded',fn); }
onReady(()=>{
    document.querySelectorAll('.grid').forEach(grid=>{
        const cards=[...grid.querySelectorAll('.card')];
        cards.sort((a,b)=>parseFloat(b.dataset.score)-parseFloat(a.dataset.score));
        cards.forEach(c=>grid.appendChild(c));
    });
    document.querySelectorAll('.card').forEach(c=>{
        const pip=c.querySelector('.score-pip');
        if(pip)pip.style.background=scoreColor(parseFloat(c.dataset.score));
    });
    applyFilter();
    init2D();
    init3D();
    initScoreField();
    initTimeline();
});
"""

DIVERSITY_2D_JS = """
// ── Diversity 2D ───────────────────────────────────────────────────────────
const GEN_COLORS_2D=__GEN_COLORS__;
var cv2,ctx2,tt2;
var tr2={x:0,y:0,scale:1}, drag2=null, hover2=null, vis2={};
var nodeById2={};

function w2s(wx,wy){
    return[cv2.width/2+(wx+tr2.x)*tr2.scale, cv2.height/2+(wy+tr2.y)*tr2.scale];
}
function s2w(sx,sy){
    return[(sx-cv2.width/2)/tr2.scale-tr2.x,(sy-cv2.height/2)/tr2.scale-tr2.y];
}
function nr2(n){ return Math.max(4,n.score*16+5); }

function init2D(){
    cv2=document.getElementById('cv2d');
    ctx2=cv2.getContext('2d');
    tt2=document.getElementById('tt2d');
    DIV_NODES.forEach(n=>{nodeById2[n.id]=n;});
    const gens=[...new Set(DIV_NODES.map(n=>n.gen))].sort();
    gens.forEach(g=>{vis2[g]=true;});
    const bar=document.getElementById('chips2d');
    gens.forEach(g=>{
        const c=document.createElement('span');
        c.className='gen-chip';
        c.textContent='g'+g;
        c.style.background=GEN_COLORS_2D[g%GEN_COLORS_2D.length]+'33';
        c.style.borderColor=GEN_COLORS_2D[g%GEN_COLORS_2D.length];
        c.style.color=GEN_COLORS_2D[g%GEN_COLORS_2D.length];
        c.onclick=()=>{vis2[g]=!vis2[g];c.classList.toggle('off',!vis2[g]);draw2D();};
        bar.appendChild(c);
    });
    cv2.addEventListener('wheel',e=>{
        e.preventDefault();
        const f=e.deltaY<0?1.12:1/1.12;
        const r=cv2.getBoundingClientRect();
        const mx=e.clientX-r.left,my=e.clientY-r.top;
        const[wx,wy]=s2w(mx,my);
        tr2.scale=Math.max(.15,Math.min(30,tr2.scale*f));
        const[nx,ny]=w2s(wx,wy);
        tr2.x+=(mx-nx)/tr2.scale; tr2.y+=(my-ny)/tr2.scale;
        draw2D();
    },{passive:false});
    cv2.addEventListener('mousedown',e=>{drag2={sx:e.clientX,sy:e.clientY,tx:tr2.x,ty:tr2.y};tt2.style.display='none';});
    cv2.addEventListener('mouseup',()=>{drag2=null;});
    cv2.addEventListener('mousemove',onMM2D);
    cv2.addEventListener('mouseleave',()=>{drag2=null;hover2=null;tt2.style.display='none';draw2D();});
    resize2D();
    window.addEventListener('resize',()=>{
        if(document.getElementById('diversity2d-pane').style.display!=='none')resize2D();
    });
}

function resize2D(){
    const w=document.getElementById('wrap2d');
    cv2.width=w.clientWidth; cv2.height=w.clientHeight;
    draw2D();
}

function draw2D(){
    const W=cv2.width,H=cv2.height,ws=Math.min(W,H)*.42;
    ctx2.clearRect(0,0,W,H);
    ctx2.fillStyle='#0d0d1a'; ctx2.fillRect(0,0,W,H);
    ctx2.globalAlpha=.1; ctx2.strokeStyle='#aaa'; ctx2.lineWidth=.7;
    DIV_EDGES.forEach(e=>{
        const a=nodeById2[e[0]],b=nodeById2[e[1]];
        if(!a||!b||!vis2[a.gen]||!vis2[b.gen])return;
        const[ax,ay]=w2s(a.x2*ws,a.y2*ws),[bx,by]=w2s(b.x2*ws,b.y2*ws);
        ctx2.beginPath();ctx2.moveTo(ax,ay);ctx2.lineTo(bx,by);ctx2.stroke();
    });
    ctx2.globalAlpha=1;
    const sorted=[...DIV_NODES].sort((a,b)=>a.score-b.score);
    sorted.forEach(node=>{
        if(!vis2[node.gen])return;
        const[sx,sy]=w2s(node.x2*ws,node.y2*ws);
        const r=nr2(node),col=GEN_COLORS_2D[node.gen%GEN_COLORS_2D.length];
        const isH=node===hover2;
        if(isH){ctx2.beginPath();ctx2.arc(sx,sy,r+6,0,Math.PI*2);ctx2.fillStyle='#ffffff33';ctx2.fill();}
        ctx2.beginPath();ctx2.arc(sx,sy,r,0,Math.PI*2);
        ctx2.fillStyle=col+(isH?'ff':'99');ctx2.fill();
        const ring={OK:'#4f4',EXTRA_CARD:'#fc4',EXTRA_PILE:'#fa4',TRIVIAL:'#f84',IMPOSSIBLE:'#f44',UNKNOWN:'#555',ERROR:'#322'}[node.verdict]||'#555';
        ctx2.beginPath();ctx2.arc(sx,sy,r,0,Math.PI*2);
        ctx2.strokeStyle=ring;ctx2.lineWidth=isH?2.5:1;ctx2.stroke();
    });
}

function findNode2D(mx,my){
    const ws=Math.min(cv2.width,cv2.height)*.42;
    let best=null,bd=28*28;
    for(const n of DIV_NODES){
        if(!vis2[n.gen])continue;
        const[nx,ny]=w2s(n.x2*ws,n.y2*ws);
        const d2=(mx-nx)**2+(my-ny)**2,r=nr2(n)+5;
        if(d2<r*r&&d2<bd){bd=d2;best=n;}
    }
    return best;
}

function showTooltip(tt,node,mx,my,W,H){
    const wr=(node.win_rate*100).toFixed(0),sc=node.score.toFixed(3);
    let html='';
    const gi=document.getElementById('gimg-'+node.id);
    if(gi)html+=`<img src="${gi.src}">`;
    html+=`<strong style="color:#e2b96f">${node.name}</strong> <span style="color:#777">g${node.gen}</span><br>`;
    html+=`<span style="color:#aaa">${node.verdict}</span> &nbsp; score <strong>${sc}</strong><br>`;
    html+=`win ${wr}% &nbsp; ${node.avg_moves.toFixed(0)}mv`;
    if(node.method)html+=`<br><span style="color:#666">${node.method}</span>`;
    tt.innerHTML=html; tt.style.display='block';
    tt.style.left='0'; tt.style.top='0';
    const tw=tt.offsetWidth,th=tt.offsetHeight;
    let tx=mx+14,ty=my-10;
    if(tx+tw>W)tx=mx-tw-14;
    if(ty+th>H)ty=my-th-10;
    tt.style.left=tx+'px'; tt.style.top=ty+'px';
}

function onMM2D(e){
    const r=cv2.getBoundingClientRect(),mx=e.clientX-r.left,my=e.clientY-r.top;
    if(drag2){
        tr2.x=drag2.tx+(e.clientX-drag2.sx)/tr2.scale;
        tr2.y=drag2.ty+(e.clientY-drag2.sy)/tr2.scale;
        draw2D(); return;
    }
    const node=findNode2D(mx,my);
    if(node!==hover2){hover2=node;draw2D();}
    if(node){cv2.style.cursor='pointer';showTooltip(tt2,node,mx,my,cv2.width,cv2.height);}
    else{cv2.style.cursor='crosshair';tt2.style.display='none';}
}
function reset2D(){tr2={x:0,y:0,scale:1};draw2D();}
"""

DIVERSITY_3D_JS = """
// ── Diversity 3D (Three.js) ────────────────────────────────────────────────
const GEN_COLORS_3D=__GEN_COLORS__;
var renderer3,scene3,camera3,tt3,cv3;
var theta3=.5,phi3=1.1,camR3=2.8;
var drag3d=null,hover3=null,vis3={};
var nodeMeshes3=[],raycaster3,mouse3NDC;
var initialized3=false;

function init3D(){
    cv3=document.getElementById('cv3d');
    tt3=document.getElementById('tt3d');
    if(typeof THREE==='undefined'){
        cv3.parentElement.innerHTML='<div style="padding:40px;color:#a55">Three.js failed to load from CDN. Check your internet connection.</div>';
        return;
    }
    scene3=new THREE.Scene();
    scene3.background=new THREE.Color(0x0d0d1a);
    scene3.fog=new THREE.FogExp2(0x0d0d1a,.25);

    const W=cv3.clientWidth||800,H=cv3.clientHeight||600;
    camera3=new THREE.PerspectiveCamera(55,W/H,.01,50);
    updateCam3();

    renderer3=new THREE.WebGLRenderer({canvas:cv3,antialias:true});
    renderer3.setPixelRatio(Math.min(window.devicePixelRatio,2));
    renderer3.setSize(W,H);

    scene3.add(new THREE.AmbientLight(0xffffff,.6));
    const dl=new THREE.DirectionalLight(0xffffff,.8);
    dl.position.set(1,2,3); scene3.add(dl);

    const geom=new THREE.IcosahedronGeometry(1,1);
    const gens=[...new Set(DIV_NODES.map(n=>n.gen))].sort();
    gens.forEach(g=>{vis3[g]=true;});
    const bar=document.getElementById('chips3d');
    gens.forEach(g=>{
        const c=document.createElement('span');
        c.className='gen-chip';
        c.textContent='g'+g;
        c.style.background=GEN_COLORS_3D[g%GEN_COLORS_3D.length]+'33';
        c.style.borderColor=GEN_COLORS_3D[g%GEN_COLORS_3D.length];
        c.style.color=GEN_COLORS_3D[g%GEN_COLORS_3D.length];
        c.onclick=()=>{
            vis3[g]=!vis3[g]; c.classList.toggle('off',!vis3[g]);
            nodeMeshes3.forEach(m=>{if(m.userData.gen===g)m.visible=vis3[g];});
            render3();
        };
        bar.appendChild(c);
    });

    DIV_NODES.forEach(node=>{
        const col=new THREE.Color(GEN_COLORS_3D[node.gen%GEN_COLORS_3D.length]);
        const mat=new THREE.MeshPhongMaterial({color:col,transparent:true,opacity:.85});
        const mesh=new THREE.Mesh(geom,mat);
        const r=Math.max(.018,node.score*.07+.018);
        mesh.scale.setScalar(r);
        mesh.position.set(node.x3,node.y3,node.z3);
        mesh.userData=node;
        scene3.add(mesh);
        nodeMeshes3.push(mesh);
    });

    raycaster3=new THREE.Raycaster();
    raycaster3.params.Mesh.threshold=.02;
    mouse3NDC=new THREE.Vector2();

    cv3.addEventListener('wheel',e=>{
        e.preventDefault();
        camR3*=e.deltaY<0?.88:1.12;
        camR3=Math.max(.3,Math.min(8,camR3));
        updateCam3(); render3();
    },{passive:false});
    cv3.addEventListener('mousedown',e=>{drag3d={sx:e.clientX,sy:e.clientY,th:theta3,ph:phi3};});
    cv3.addEventListener('mouseup',()=>{drag3d=null;});
    cv3.addEventListener('mousemove',onMM3D);
    cv3.addEventListener('mouseleave',()=>{drag3d=null;hover3=null;tt3.style.display='none';render3();});

    window.addEventListener('resize',()=>{
        if(document.getElementById('diversity3d-pane').style.display!=='none')resize3D();
    });

    initialized3=true;
    resize3D();
}

function updateCam3(){
    camera3.position.set(
        camR3*Math.sin(phi3)*Math.cos(theta3),
        camR3*Math.cos(phi3),
        camR3*Math.sin(phi3)*Math.sin(theta3)
    );
    camera3.lookAt(0,0,0);
}

function render3(){
    if(renderer3)renderer3.render(scene3,camera3);
}

function resize3D(){
    if(!initialized3)return;
    const w=document.getElementById('wrap3d');
    const W=w.clientWidth,H=w.clientHeight;
    camera3.aspect=W/H; camera3.updateProjectionMatrix();
    renderer3.setSize(W,H);
    render3();
}

function onMM3D(e){
    const r=cv3.getBoundingClientRect(),mx=e.clientX-r.left,my=e.clientY-r.top;
    if(drag3d){
        theta3=drag3d.th-(e.clientX-drag3d.sx)*.008;
        phi3=Math.max(.05,Math.min(Math.PI-.05,drag3d.ph-(e.clientY-drag3d.sy)*.008));
        updateCam3(); render3(); return;
    }
    mouse3NDC.set(mx/r.width*2-1,-(my/r.height)*2+1);
    raycaster3.setFromCamera(mouse3NDC,camera3);
    const hits=raycaster3.intersectObjects(nodeMeshes3);
    const node=hits.length?hits[0].object.userData:null;
    if(node!==hover3){
        if(hover3)hover3.__mesh.material.emissive?.set(0,0,0);
        if(node)hits[0].object.material.emissiveIntensity=.4;
        hover3=node;
        if(hover3)hover3.__mesh=hits[0].object;
        render3();
    }
    if(node){
        cv3.style.cursor='pointer';
        showTooltip(tt3,node,mx,my,r.width,r.height);
    } else {
        cv3.style.cursor='default';
        tt3.style.display='none';
    }
}
function reset3D(){theta3=.5;phi3=1.1;camR3=2.8;updateCam3();render3();}
"""


SCORE_FIELD_JS = """
// ── Score Field 3D ─────────────────────────────────────────────────────────
const GEN_COLORS_SF = __GEN_COLORS__;
var sfRenderer, sfScene, sfCamera, sfCanvas, sfTooltip;
var sfTheta=0.5, sfPhi=1.1, sfR=2.8;
var sfDrag=null, sfNodeMeshes=[];
var sfRaycaster3, sfMouseNDC3;
var sfInit=false;

function initScoreField(){
    sfCanvas  = document.getElementById('sfCanvas');
    sfTooltip = document.getElementById('sfTooltip');
    if(typeof THREE==='undefined'){
        sfCanvas.parentElement.innerHTML='<div style="padding:40px;color:#a55">Three.js not loaded from CDN.</div>';
        return;
    }
    sfScene = new THREE.Scene();
    sfScene.background = new THREE.Color(0x0d0d1a);

    const W = sfCanvas.clientWidth||800, H = sfCanvas.clientHeight||600;
    sfCamera = new THREE.PerspectiveCamera(55, W/H, 0.01, 50);
    updateSFCam();

    sfRenderer = new THREE.WebGLRenderer({canvas:sfCanvas, antialias:true});
    sfRenderer.setPixelRatio(Math.min(window.devicePixelRatio,2));
    sfRenderer.setSize(W, H);

    // ── Score-field particle cloud ──────────────────────────────────────────
    const positions=[], colors=[], sizes=[];
    const black = new THREE.Color(0,0,0);
    const white = new THREE.Color(1,1,1);
    const tc    = new THREE.Color();

    SCORE_FIELD.forEach(p=>{
        positions.push(p.x, p.y, p.z);
        // density-invariant colour: pure score, no density bias
        tc.lerpColors(black, white, Math.max(0, Math.min(1, p.s)));
        colors.push(tc.r, tc.g, tc.b);
    });

    const sfGeom = new THREE.BufferGeometry();
    sfGeom.setAttribute('position', new THREE.Float32BufferAttribute(positions,3));
    sfGeom.setAttribute('color',    new THREE.Float32BufferAttribute(colors,3));
    const sfMat = new THREE.PointsMaterial({
        size: 0.085, vertexColors: true,
        transparent: true, opacity: 0.45, sizeAttenuation: true,
    });
    sfScene.add(new THREE.Points(sfGeom, sfMat));

    // ── Game node overlays (small coloured spheres) ─────────────────────────
    const nodeGeom = new THREE.IcosahedronGeometry(1,0);
    DIV_NODES.forEach(node=>{
        const col = new THREE.Color(GEN_COLORS_SF[node.gen % GEN_COLORS_SF.length]);
        const mat = new THREE.MeshBasicMaterial({color:col});
        const mesh= new THREE.Mesh(nodeGeom, mat);
        const r   = Math.max(0.012, node.score*0.035+0.012);
        mesh.scale.setScalar(r);
        mesh.position.set(node.x3, node.y3, node.z3);
        mesh.userData = node;
        sfScene.add(mesh);
        sfNodeMeshes.push(mesh);
    });

    sfRaycaster3 = new THREE.Raycaster();
    sfMouseNDC3  = new THREE.Vector2();

    sfCanvas.addEventListener('wheel', e=>{
        e.preventDefault();
        sfR *= e.deltaY<0 ? 0.88 : 1.12;
        sfR  = Math.max(0.3, Math.min(8, sfR));
        updateSFCam(); sfRenderer.render(sfScene, sfCamera);
    },{passive:false});
    sfCanvas.addEventListener('mousedown', e=>{ sfDrag={sx:e.clientX,sy:e.clientY,th:sfTheta,ph:sfPhi}; });
    sfCanvas.addEventListener('mouseup',   ()=>{ sfDrag=null; });
    sfCanvas.addEventListener('mousemove', onSFMove);
    sfCanvas.addEventListener('mouseleave',()=>{ sfDrag=null; sfTooltip.style.display='none'; });

    sfInit=true;
    resizeSF();
    window.addEventListener('resize',()=>{
        if(document.getElementById('heatmap-pane').style.display!=='none') resizeSF();
    });
}

function updateSFCam(){
    sfCamera.position.set(
        sfR*Math.sin(sfPhi)*Math.cos(sfTheta),
        sfR*Math.cos(sfPhi),
        sfR*Math.sin(sfPhi)*Math.sin(sfTheta));
    sfCamera.lookAt(0,0,0);
}

function resizeSF(){
    if(!sfInit) return;
    const w=document.getElementById('sfWrap');
    const W=w.clientWidth, H=w.clientHeight;
    sfCamera.aspect=W/H; sfCamera.updateProjectionMatrix();
    sfRenderer.setSize(W,H);
    sfRenderer.render(sfScene, sfCamera);
}

function onSFMove(e){
    const rect=sfCanvas.getBoundingClientRect();
    const mx=e.clientX-rect.left, my=e.clientY-rect.top;
    if(sfDrag){
        sfTheta=sfDrag.th-(e.clientX-sfDrag.sx)*.008;
        sfPhi=Math.max(.05,Math.min(Math.PI-.05, sfDrag.ph-(e.clientY-sfDrag.sy)*.008));
        updateSFCam(); sfRenderer.render(sfScene,sfCamera); return;
    }
    sfMouseNDC3.set(mx/rect.width*2-1, -(my/rect.height)*2+1);
    sfRaycaster3.setFromCamera(sfMouseNDC3, sfCamera);
    const hits=sfRaycaster3.intersectObjects(sfNodeMeshes);
    if(hits.length){
        sfCanvas.style.cursor='pointer';
        showTooltip(sfTooltip, hits[0].object.userData, mx, my, rect.width, rect.height);
    } else {
        sfCanvas.style.cursor='default';
        sfTooltip.style.display='none';
    }
}
function resetSF(){ sfTheta=0.5;sfPhi=1.1;sfR=2.8;updateSFCam();sfRenderer.render(sfScene,sfCamera); }
"""


TIMELINE_JS = """
// ── Evolution Timeline ─────────────────────────────────────────────────────
// World x in [-1,1]: gen 0 → -1, maxGen → +1
// World y in [-1,1]: score 0 → -1 (bottom), score 1 → +1 (top)
//   but canvas y is flipped, so we negate wy when converting to screen
const GEN_COLORS_TL = __GEN_COLORS__;
var tlCanvas, tlCtx, tlTooltip;
var tlTr = {x:0, y:0, s:1};
var tlDrag = null, tlHover = null;
var tlLayout = null;
var tlInit = false;

const TL_PAD = {l:58, r:20, t:25, b:42};

// y is negated so positive score = up on screen
function tlW2S(wx,wy){ return [tlCanvas.width/2+(wx+tlTr.x)*tlTr.s, tlCanvas.height/2+(-wy+tlTr.y)*tlTr.s]; }
function tlS2W(sx,sy){ return [(sx-tlCanvas.width/2)/tlTr.s-tlTr.x, -((sy-tlCanvas.height/2)/tlTr.s-tlTr.y)]; }

function tlFit(){
    const W=tlCanvas.width, H=tlCanvas.height;
    const sX=(W-TL_PAD.l-TL_PAD.r)/2.0;
    const sY=(H-TL_PAD.t-TL_PAD.b)/2.0;
    tlTr.s=Math.min(sX,sY);
    // shift world centre into the padded area centre
    const cx=TL_PAD.l+(W-TL_PAD.l-TL_PAD.r)/2;
    const cy=TL_PAD.t+(H-TL_PAD.t-TL_PAD.b)/2;
    tlTr.x=(cx-W/2)/tlTr.s;
    tlTr.y=(cy-H/2)/tlTr.s;   // negative because y is flipped in tlW2S
}

function buildLayout(){
    const gens=[...new Set(DIV_NODES.map(n=>n.gen))].sort((a,b)=>a-b);
    const maxGen=gens[gens.length-1]||1;
    const byGen={};
    DIV_NODES.forEach(n=>{if(!byGen[n.gen])byGen[n.gen]=[];byGen[n.gen].push(n);});
    Object.values(byGen).forEach(g=>g.sort((a,b)=>a.score-b.score));
    const colSpan=2.0/maxGen;
    const pos={};
    gens.forEach(gen=>{
        const group=byGen[gen]||[];
        const cx=maxGen>0?gen/maxGen*2-1:0;
        const jitter=colSpan*0.55;  // wider spread within column
        group.forEach((node,i)=>{
            const n=group.length;
            const off=n>1?(i/(n-1)-0.5)*jitter:0;
            // sqrt transform so the dense score≈0 cluster spreads out
            const wy=Math.sqrt(Math.max(0,node.score))*2-1;
            pos[node.id]={wx:cx+off, wy, node};
        });
    });
    return {pos,gens,maxGen,colSpan};
}

function initTimeline(){
    tlCanvas=document.getElementById('tlCanvas');
    tlCtx=tlCanvas.getContext('2d');
    tlTooltip=document.getElementById('tlTooltip');
    tlLayout=buildLayout();
    tlCanvas.addEventListener('wheel',e=>{
        e.preventDefault();
        const f=e.deltaY<0?1.12:1/1.12;
        const r=tlCanvas.getBoundingClientRect();
        const mx=e.clientX-r.left, my=e.clientY-r.top;
        const[wx,wy]=tlS2W(mx,my);
        tlTr.s=Math.max(.5,Math.min(5000,tlTr.s*f));
        const[nx,ny]=tlW2S(wx,wy);
        tlTr.x+=(mx-nx)/tlTr.s; tlTr.y-=(my-ny)/tlTr.s;
        drawTimeline();
    },{passive:false});
    tlCanvas.addEventListener('mousedown',e=>{tlDrag={sx:e.clientX,sy:e.clientY,tx:tlTr.x,ty:tlTr.y};tlTooltip.style.display='none';});
    tlCanvas.addEventListener('mouseup',()=>{tlDrag=null;});
    tlCanvas.addEventListener('mousemove',onTLMove);
    tlCanvas.addEventListener('mouseleave',()=>{tlDrag=null;tlHover=null;tlTooltip.style.display='none';drawTimeline();});
    tlInit=true;
    resizeTimeline();
    window.addEventListener('resize',()=>{
        if(document.getElementById('timeline-pane').style.display!=='none') resizeTimeline();
    });
}

function resizeTimeline(){
    if(!tlInit)return;
    const w=document.getElementById('tlWrap');
    tlCanvas.width=w.clientWidth; tlCanvas.height=w.clientHeight;
    tlFit();
    drawTimeline();
}

function drawTimeline(){
    if(!tlLayout)return;
    const W=tlCanvas.width, H=tlCanvas.height;
    const{pos,gens,maxGen}=tlLayout;
    tlCtx.clearRect(0,0,W,H);
    tlCtx.fillStyle='#0d0d1a'; tlCtx.fillRect(0,0,W,H);

    // ── score grid lines (Y uses sqrt transform; labels show real score) ───
    tlCtx.font='11px system-ui';
    [0,.05,.1,.2,.35,.5,.7,1].forEach(sc=>{
        // transformed position: sqrt(sc)*2-1
        const wy=Math.sqrt(sc)*2-1;
        const[,sy]=tlW2S(0,wy);
        if(sy<0||sy>H)return;
        const[lx]=tlW2S(-1,wy),[rx]=tlW2S(1,wy);
        tlCtx.strokeStyle='#1e1e2e'; tlCtx.lineWidth=.8;
        tlCtx.beginPath();tlCtx.moveTo(Math.max(lx,TL_PAD.l-4),sy);tlCtx.lineTo(Math.min(rx,W),sy);tlCtx.stroke();
        tlCtx.fillStyle='#555'; tlCtx.textAlign='right';
        tlCtx.fillText(sc.toFixed(2), Math.min(lx-5, TL_PAD.l-4), sy+4);
    });
    // ── generation labels ──────────────────────────────────────────────────
    tlCtx.textAlign='center'; tlCtx.fillStyle='#555'; tlCtx.font='11px system-ui';
    gens.forEach(gen=>{
        const cx=maxGen>0?gen/maxGen*2-1:0;
        const[sx,sy]=tlW2S(cx,-1.0);  // just below score=0
        if(sx<0||sx>W)return;
        tlCtx.fillText('g'+gen, sx, Math.min(sy+18, H-4));
    });
    // ── y-axis title ───────────────────────────────────────────────────────
    tlCtx.save();
    tlCtx.translate(10,H/2); tlCtx.rotate(-Math.PI/2);
    tlCtx.textAlign='center'; tlCtx.fillStyle='#666'; tlCtx.font='12px system-ui';
    tlCtx.fillText('Score',0,0);
    tlCtx.restore();

    // ── edges ──────────────────────────────────────────────────────────────
    const MC={mutation:'#9b59b6', crossover:'#1abc9c', best:'#e2b96f'};
    function mCol(m){ const s=(m||'').toLowerCase();
        return s.includes('mutation')?MC.mutation:s.includes('crossover')?MC.crossover:s.includes('best')?MC.best:'#334'; }

    function arrowhead(x,y,dx,dy,sz){
        const len=Math.hypot(dx,dy); if(len<.001)return;
        const ux=dx/len,uy=dy/len,px2=-uy,py2=ux;
        tlCtx.beginPath();
        tlCtx.moveTo(x,y);
        tlCtx.lineTo(x-ux*sz+px2*sz*.45, y-uy*sz+py2*sz*.45);
        tlCtx.lineTo(x-ux*sz-px2*sz*.45, y-uy*sz-py2*sz*.45);
        tlCtx.closePath();tlCtx.fill();
    }

    DIV_EDGES.forEach(([pid,cid])=>{
        const p=pos[pid],c=pos[cid];
        if(!p||!c)return;
        // adjacent generations only
        if(c.node.gen!==p.node.gen+1)return;
        const[px,py]=tlW2S(p.wx,p.wy),[cx2,cy]=tlW2S(c.wx,c.wy);
        const col=mCol(c.node.method);
        const isBest=(c.node.method||'').toLowerCase().includes('best');
        tlCtx.fillStyle=col;

        if(isBest){
            tlCtx.globalAlpha=.9; tlCtx.strokeStyle=col; tlCtx.lineWidth=2.8;
            tlCtx.beginPath();tlCtx.moveTo(px,py);tlCtx.lineTo(cx2,cy);tlCtx.stroke();
            tlCtx.globalAlpha=1;
            tlCtx.beginPath();tlCtx.arc(px,py,5,0,Math.PI*2);tlCtx.fill();
            arrowhead(cx2,cy,cx2-px,cy-py,11);
        } else {
            tlCtx.globalAlpha=.65; tlCtx.strokeStyle=col; tlCtx.lineWidth=1.1;
            tlCtx.beginPath();tlCtx.moveTo(px,py);
            const mx2=(px+cx2)/2;
            tlCtx.bezierCurveTo(mx2,py,mx2,cy,cx2,cy);
            tlCtx.stroke();
            tlCtx.globalAlpha=.8;
            arrowhead(cx2,cy,cx2-mx2,0,5);
        }
        tlCtx.globalAlpha=1;
    });

    // ── legend ─────────────────────────────────────────────────────────────
    const legend2=[
        ['mutation (curved)',  MC.mutation,  false],
        ['crossover (curved)', MC.crossover, false],
        ['best-of (straight)', MC.best,      true ],
    ];
    let lx=W-10, ly=14;
    tlCtx.font='10px system-ui'; tlCtx.textAlign='right';
    legend2.forEach(([label,col,isBest])=>{
        tlCtx.fillStyle=col; tlCtx.strokeStyle=col;
        if(isBest){
            tlCtx.lineWidth=2.2;
            tlCtx.beginPath();tlCtx.moveTo(lx-50,ly+1);tlCtx.lineTo(lx-10,ly+1);tlCtx.stroke();
            tlCtx.beginPath();tlCtx.arc(lx-50,ly+1,3,0,Math.PI*2);tlCtx.fill();
            tlCtx.fillStyle=col; arrowhead(lx-10,ly+1,40,0,7);
        } else {
            tlCtx.lineWidth=1;
            tlCtx.beginPath();tlCtx.moveTo(lx-50,ly+1);
            const lmx=(lx-50+lx-10)/2;
            tlCtx.bezierCurveTo(lmx,ly+1,lmx,ly+1,lx-10,ly+1);
            tlCtx.stroke();
            tlCtx.fillStyle=col; arrowhead(lx-10,ly+1,40,0,5);
        }
        tlCtx.fillStyle='#777'; tlCtx.textAlign='right';
        tlCtx.fillText(label,lx-53,ly+5);
        ly+=17;
    });

    // ── nodes ──────────────────────────────────────────────────────────────
    const sorted=[...DIV_NODES].sort((a,b)=>a.score-b.score);
    sorted.forEach(node=>{
        const p=pos[node.id]; if(!p)return;
        const[sx,sy]=tlW2S(p.wx,p.wy);
        if(sx<-20||sx>W+20||sy<-20||sy>H+20)return;
        const r=Math.max(4,node.score*12+4);
        const col=GEN_COLORS_TL[node.gen%GEN_COLORS_TL.length];
        const isH=node===tlHover;
        if(isH){tlCtx.beginPath();tlCtx.arc(sx,sy,r+5,0,Math.PI*2);tlCtx.fillStyle='#ffffff33';tlCtx.fill();}
        tlCtx.beginPath();tlCtx.arc(sx,sy,r,0,Math.PI*2);
        tlCtx.fillStyle=col+(isH?'ff':'aa');tlCtx.fill();
        const ring={OK:'#4f4',EXTRA_CARD:'#fc4',EXTRA_PILE:'#fa4',TRIVIAL:'#f84',IMPOSSIBLE:'#f44',UNKNOWN:'#555',ERROR:'#322'}[node.verdict]||'#555';
        tlCtx.beginPath();tlCtx.arc(sx,sy,r,0,Math.PI*2);
        tlCtx.strokeStyle=ring;tlCtx.lineWidth=isH?2:.7;tlCtx.stroke();
    });
}

function findTLNode(mx,my){
    if(!tlLayout)return null;
    let best=null,bd=22*22;
    for(const{wx,wy,node}of Object.values(tlLayout.pos)){
        const[sx,sy]=tlW2S(wx,wy);
        const d2=(mx-sx)**2+(my-sy)**2;
        const r=Math.max(4,node.score*12+4)+5;
        if(d2<r*r&&d2<bd){bd=d2;best=node;}
    }
    return best;
}

function onTLMove(e){
    const rect=tlCanvas.getBoundingClientRect();
    const mx=e.clientX-rect.left,my=e.clientY-rect.top;
    if(tlDrag){
        tlTr.x=tlDrag.tx+(e.clientX-tlDrag.sx)/tlTr.s;
        tlTr.y=tlDrag.ty-(e.clientY-tlDrag.sy)/tlTr.s;
        drawTimeline();return;
    }
    const node=findTLNode(mx,my);
    if(node!==tlHover){tlHover=node;drawTimeline();}
    if(node){
        tlCanvas.style.cursor='pointer';
        showTooltip(tlTooltip,node,mx,my,tlCanvas.width,tlCanvas.height);
    }else{
        tlCanvas.style.cursor='crosshair';
        tlTooltip.style.display='none';
    }
}
function resetTimeline(){tlFit();drawTimeline();}
"""

# ── HTML helpers ──────────────────────────────────────────────────────────────

def win_color(wr):
    r = int(255*(1-wr)); g = int(200*wr+55)
    return f"rgb({r},{g},60)"

def origin_badge(method):
    m = (method or "").lower()
    if "random"   in m: return '<span class="badge badge-random">rnd</span>'
    if "mutation" in m: return '<span class="badge badge-mutation">mut</span>'
    if "crossover"in m: return '<span class="badge badge-crossover">xo</span>'
    if "best"     in m: return '<span class="badge badge-best">best</span>'
    return ""

def verdict_label(v):
    labels = {VERDICT_OK:"OK", VERDICT_EXTRA_CARD:"+card", VERDICT_EXTRA_PILE:"+pile",
              VERDICT_TRIVIAL:"trivial", VERDICT_IMPOSSIBLE:"impossible",
              VERDICT_UNKNOWN:"unknown", VERDICT_ERROR:"error"}
    return f'<span class="vlabel vlabel-{v}">{labels.get(v,v)}</span>'

def card_html(node):
    wr=node["win_rate"]; mv=node["avg_moves"]; cu=node["avg_card_usage"]
    pu=node["avg_pile_usage"]; ex=node["exhausted_rate"]
    verdict=node["verdict"]; score=node["score"]
    b64=node["b64_thumb"]; name=node["name"]; node_id=node["id"]

    bar_w=f"{wr*100:.1f}%"; bar_col=win_color(wr)
    meta=[f'<strong style="color:{bar_col}">{wr*100:.0f}%</strong> win']
    meta.append(f"{mv:.0f}mv"); meta.append(f"{cu*100:.0f}%cu"); meta.append(f"{pu*100:.0f}%pu")
    if ex>0.05: meta.append(f'<span style="color:#a55">{ex*100:.0f}%ex</span>')

    parents = ""

    img = (f'<img id="gimg-{node_id}" src="data:image/png;base64,{b64}" alt="{name}">'
           if b64 else
           '<div style="height:70px;background:#111;display:flex;align-items:center;'
           'justify-content:center;color:#555;font-size:.6rem;">render failed</div>')

    is_trivial = 1 if verdict==VERDICT_TRIVIAL else 0
    return (
        f'<div class="card verdict-{verdict}" data-score="{score:.4f}" data-trivial="{is_trivial}">\n'
        f'  {img}\n  <div class="card-body">\n'
        f'    <div class="game-name" title="{name} (score {score:.3f})">'
        f'<span class="score-pip"></span>{origin_badge(node["method"])}'
        f'{verdict_label(verdict)} {name}</div>\n'
        f'    <div class="win-bar-wrap"><div class="win-bar" style="width:{bar_w};background:{bar_col}"></div></div>\n'
        f'    <div class="meta">{"&middot;".join(meta)}'
        f'{"<br><span style=color:#444>"+parents+"</span>" if parents else ""}'
        f'</div>\n  </div>\n</div>'
    )


def make_exp_nav(current_id: str, siblings: list[dict]) -> str:
    """siblings: list of {id, filename, summary}"""
    if not siblings:
        return ""
    btns = []
    for s in siblings:
        sm  = s["summary"]
        lbl = f"{s['id']}  ·  {sm['n_gens']}g  ·  best {sm['best']:.2f}  ·  {sm['ok_count']} OK"
        if s["id"] == current_id:
            btns.append(f'<span class="exp-btn active">{lbl}</span>')
        else:
            btns.append(f'<a href="{s["filename"]}" class="exp-btn">{lbl}</a>')
    return ('<div id="exp-nav"><span class="elabel">Experiment:</span>'
            + "".join(btns) + '</div>')


def build_index_html(siblings: list[dict], out_path: str):
    """Simple index page linking to all trial galleries."""
    cards = []
    for s in siblings:
        sm = s["summary"]
        cards.append(
            f'<a href="{s["filename"]}" style="display:block;background:#16213e;border-radius:8px;'
            f'padding:18px 22px;border:1px solid #2a2a4a;text-decoration:none;color:#eee;'
            f'transition:border-color .15s" onmouseover="this.style.borderColor=\'#e2b96f\'" '
            f'onmouseout="this.style.borderColor=\'#2a2a4a\'">'
            f'<div style="font-size:1.1rem;font-weight:700;color:#e2b96f;margin-bottom:8px">'
            f'Trial {sm["id"]}</div>'
            f'<div style="font-size:.8rem;color:#aaa;line-height:1.8">'
            f'{sm["n_gens"]} generations &nbsp;·&nbsp; {sm["n_games"]} games<br>'
            f'Best score: <strong style="color:#4c4">{sm["best"]:.3f}</strong> &nbsp;·&nbsp; '
            f'Last-gen avg: {sm["last_avg"]:.3f} &nbsp;·&nbsp; '
            f'{sm["ok_count"]} OK verdict</div></a>'
        )
    grid = '<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:14px">' + "".join(cards) + '</div>'
    html = (
        f'<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">'
        f'<title>SolitaireGDL Experiments</title>'
        f'<style>*{{box-sizing:border-box;margin:0;padding:0}}'
        f'body{{font-family:system-ui,sans-serif;background:#1a1a2e;color:#eee;padding:30px}}'
        f'h1{{font-size:1.4rem;color:#e2b96f;margin-bottom:20px}}</style></head><body>'
        f'<h1>SolitaireGDL Experiments</h1>{grid}</body></html>'
    )
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Index written to: {out_path}")


def build_html(data: dict, out_path: str, siblings: list[dict] | None = None):
    trial_id = data["trial_id"]
    nodes    = data["nodes"]
    edges    = data["edges"]

    # Group nodes by gen
    from collections import defaultdict
    by_gen = defaultdict(list)
    for n in nodes: by_gen[n["gen"]].append(n)

    # Gallery blocks
    gen_blocks = []
    for gen_idx in sorted(by_gen):
        gen_nodes = by_gen[gen_idx]
        gen_nodes.sort(key=lambda n: -n["score"])
        cards = [card_html(n) for n in gen_nodes]
        ok_count = sum(1 for n in gen_nodes if n["verdict"]==VERDICT_OK)
        avg_sc   = sum(n["score"] for n in gen_nodes)/len(gen_nodes) if gen_nodes else 0
        stats_str= (f"{len(cards)} games &nbsp;&middot;&nbsp; avg score {avg_sc:.3f} &nbsp;&middot;&nbsp; {ok_count} OK")
        gen_blocks.append(
            f'<div class="gen-block">'
            f'<div class="gen-header">'
            f'<span class="gen-title">g{gen_idx}</span>'
            f'<span class="gen-stats">{stats_str}</span>'
            f'<span class="gen-visible-count"></span></div>'
            f'<div class="grid">{"".join(cards)}</div></div>'
        )

    # Slim nodes for JS (no thumbnails)
    slim_keys = ('id','name','gen','score','verdict','win_rate','avg_moves','method','x2','y2','x3','y3','z3')
    slim      = [{k:n[k] for k in slim_keys} for n in nodes]
    print("  Computing 3D score field...")
    score_field_3d  = compute_score_field_3d(nodes)

    nodes_json      = json.dumps(slim)
    edges_json      = json.dumps(edges)
    colors_json     = json.dumps(GEN_COLORS)
    score_field_json= json.dumps(score_field_3d)

    js = (GALLERY_JS + DIVERSITY_2D_JS + DIVERSITY_3D_JS + SCORE_FIELD_JS + TIMELINE_JS)\
         .replace("__GEN_COLORS__", colors_json)

    toolbar = """
<div id="toolbar">
  <span id="toolbar-title">Gallery</span>
  <div class="ctrl-group">
    <label>Min score</label>
    <input id="score-slider" type="range" min="0" max="1" step="0.01" value="0" oninput="setThreshold(this.value)">
    <span id="score-val">0.00</span>
  </div>
  <button class="tb-btn" id="trivial-btn" onclick="toggleTrivial()">Hide trivial</button>
  <span id="gen-counts"></span>
</div>"""

    nav_bar = make_exp_nav(trial_id, siblings or [])

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Trial {trial_id}</title>
<style>{CSS}</style>
<script src="https://cdn.jsdelivr.net/npm/three@0.148.0/build/three.min.js"></script>
</head>
<body>
{nav_bar}
<div id="tabs">
  <button class="tab-btn active"  data-tab="gallery"      onclick="switchTab('gallery')">Gallery</button>
  <button class="tab-btn"         data-tab="diversity2d"  onclick="switchTab('diversity2d')">Diversity 2D</button>
  <button class="tab-btn"         data-tab="diversity3d"  onclick="switchTab('diversity3d')">Diversity 3D</button>
  <button class="tab-btn"         data-tab="heatmap"      onclick="switchTab('heatmap')">Score Field</button>
  <button class="tab-btn"         data-tab="timeline"     onclick="switchTab('timeline')">Timeline</button>
</div>

<!-- Gallery -->
<div id="gallery-pane">{toolbar}{"".join(gen_blocks)}</div>

<!-- Diversity 2D -->
<div id="diversity2d-pane" class="div-pane-inner" style="display:none">
  <div class="div-toolbar">
    <span class="label">Diversity Space 2D</span>
    <span class="desc">MDS on pairwise rule diffs &nbsp;&middot;&nbsp; size=score &nbsp;&middot;&nbsp; ring=verdict</span>
    <span id="chips2d" style="display:flex;gap:5px;flex-wrap:wrap"></span>
    <button class="tb-btn" onclick="reset2D()">Reset view</button>
  </div>
  <div class="div-canvas-wrap" id="wrap2d">
    <canvas id="cv2d" style="cursor:crosshair"></canvas>
    <div class="div-tooltip" id="tt2d"></div>
  </div>
</div>

<!-- Diversity 3D -->
<div id="diversity3d-pane" class="div-pane-inner" style="display:none">
  <div class="div-toolbar">
    <span class="label">Diversity Space 3D</span>
    <span class="desc">drag=rotate &nbsp;&middot;&nbsp; scroll=zoom &nbsp;&middot;&nbsp; size=score</span>
    <span id="chips3d" style="display:flex;gap:5px;flex-wrap:wrap"></span>
    <button class="tb-btn" onclick="reset3D()">Reset view</button>
  </div>
  <div class="div-canvas-wrap" id="wrap3d">
    <canvas id="cv3d"></canvas>
    <div class="div-tooltip" id="tt3d"></div>
  </div>
</div>

<!-- Score Field 3D -->
<div id="heatmap-pane" class="div-pane-inner" style="display:none">
  <div class="div-toolbar">
    <span class="label">Score Field 3D</span>
    <span class="desc">
      Nadaraya-Watson score field in 3D rule space &nbsp;&middot;&nbsp;
      black=0 &nbsp; white=1.0 &nbsp;&middot;&nbsp;
      density-invariant: s(p) = &sum;K(d)s<sub>i</sub> / &sum;K(d) &nbsp;&middot;&nbsp;
      drag=rotate &nbsp; scroll=zoom
    </span>
    <button class="tb-btn" onclick="resetSF()">Reset view</button>
  </div>
  <div class="div-canvas-wrap" id="sfWrap">
    <canvas id="sfCanvas"></canvas>
    <div class="div-tooltip" id="sfTooltip"></div>
  </div>
</div>

<!-- Timeline -->
<div id="timeline-pane" class="div-pane-inner" style="display:none">
  <div class="div-toolbar">
    <span class="label">Evolution Timeline</span>
    <span class="desc">Y = score &nbsp;&middot;&nbsp; X = generation &nbsp;&middot;&nbsp; edges: green=improvement &nbsp; red=decline &nbsp; gray=neutral &nbsp;&middot;&nbsp; size = score &nbsp;&middot;&nbsp; ring = verdict</span>
    <button class="tb-btn" onclick="resetTimeline()">Reset view</button>
  </div>
  <div class="div-canvas-wrap" id="tlWrap">
    <canvas id="tlCanvas" style="cursor:crosshair"></canvas>
    <div class="div-tooltip" id="tlTooltip"></div>
  </div>
</div>

<script>
const DIV_NODES   = {nodes_json};
const DIV_EDGES   = {edges_json};
const SCORE_FIELD = {score_field_json};
</script>
<script>{js}</script>
</body>
</html>"""

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"\nGallery written to: {out_path}")


# ── Main ─────────────────────────────────────────────────────────────────────

def process_one(trial_dir, cache_dir, filter_gens, force):
    generations = find_generations(trial_dir)
    if filter_gens:
        generations = [g for g in generations if g in filter_gens]
    print(f"\n=== Trial: {os.path.basename(trial_dir)}  ({len(generations)} gens) ===")
    return compute_trial_data(trial_dir, generations, cache_dir, force=force)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path", help="Single trial dir OR workspace dir containing multiple trials")
    ap.add_argument("--out",       default=None, help="Output path (single trial only)")
    ap.add_argument("--gens",      default=None, help="Comma-separated gens e.g. 0,1,5")
    ap.add_argument("--cache-dir", default=os.path.join(os.path.dirname(__file__), "cache"))
    ap.add_argument("--force",     action="store_true", help="Recompute even if cache exists")
    args = ap.parse_args()

    workspace    = os.path.abspath(args.path)
    cache_dir    = args.cache_dir
    results_dir  = os.path.dirname(os.path.abspath(__file__))
    filter_gens  = {f"g{g.strip()}" for g in args.gens.split(",")} if args.gens else None

    pygame.init(); pygame.font.init()
    pygame.display.set_mode((1,1))
    TextureRepo.load_textures()

    # Detect: workspace (multiple trials) or single trial dir
    trial_dirs = find_trial_dirs(workspace)
    if not trial_dirs:
        # Given path IS a trial dir
        trial_dirs = [workspace]

    print(f"Found {len(trial_dirs)} trial(s): {[os.path.basename(d) for d in trial_dirs]}")

    # ── Process all trials ────────────────────────────────────────────────────
    all_data: list[dict] = []
    for td in trial_dirs:
        all_data.append(process_one(td, cache_dir, filter_gens, args.force))

    # ── Build sibling list for nav bar ────────────────────────────────────────
    siblings = []
    for data in all_data:
        tid      = data["trial_id"]
        filename = f"trial_{tid}_gallery.html"
        siblings.append({"id": tid, "filename": filename, "summary": trial_summary(data)})

    # ── Generate per-trial HTMLs ──────────────────────────────────────────────
    for data in all_data:
        tid      = data["trial_id"]
        out_path = args.out if (len(all_data) == 1 and args.out) else \
                   os.path.join(results_dir, f"trial_{tid}_gallery.html")
        build_html(data, out_path, siblings=siblings)

    # ── Generate index ────────────────────────────────────────────────────────
    if len(all_data) > 1:
        index_path = os.path.join(results_dir, "index.html")
        build_index_html(siblings, index_path)


if __name__ == "__main__":
    main()
