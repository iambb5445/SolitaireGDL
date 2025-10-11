from parser import Parser
from diffs import Diffs
import os
from game import Game
import pandas as pd
import numpy as np
import seaborn as sns
import matplotlib.pyplot as plt

class HeatmapConfig:
    GameLabel = False
    FamilyLabel = True
    FamilyRectangle = True 
    Save = True

if __name__ == '__main__':
    game_family_dirs = [
        'games\\klondike_family',
        'games\\spider_family',
        'games\\pairing_family',
        'games\\freecell_family',
    ]
    exclude = [
        'games\\klondike_family\\miniklondike.sgdl',
        'games\\klondike_family\\miniwestcliff.sgdl',
        'games\\spider_family\\minispider.sgdl',
        'games\\freecell_family\\power.sgdl',
    ]
    family_names = ['Klondike', 'Spider', 'Pairing', 'Free Cell']
    families: list[list[Game]] = []
    for family_dir in game_family_dirs:
        filenames = [os.path.join(family_dir, filename) for filename in os.listdir(family_dir)]
        families.append([Parser.from_file(filename, None, False, True) for filename in filenames if filename not in exclude])
    games: list[Game] = [game for family in families for game in family]
    names: list[str] = [game.name for game in games]
    print(len(games))
    print(names)
    diff_matrix = np.zeros((len(games), len(games)))
    for i in range(len(games)):
        for j in range(len(games)):
            diff = games[i].diff(games[j], True, Diffs.get_sum_normalized_diff_normalized)
            diff_matrix[i][j] = diff.get_sum_normalized_diff_normalized()
            # diff_points[i][j] = diff.get_normalized_diff_points()

    # heatmap

    import matplotlib
    matplotlib.rcParams['pdf.fonttype'] = 42
    matplotlib.rcParams['ps.fonttype'] = 42
    plt.figure(figsize=(10, 8))
    ticks = names if HeatmapConfig.GameLabel else []
    sns.set(font_scale=1.4)
    sns.heatmap(diff_matrix, cmap="coolwarm", xticklabels=ticks, yticklabels=ticks, annot=False, cbar=True, square=True)
    for i, family in enumerate(families):
        start_idx = sum(len(f) for f in families[:i])
        end_idx = start_idx + len(family)
        if HeatmapConfig.FamilyRectangle:
            plt.gca().add_patch(plt.Rectangle((start_idx, start_idx), len(family), len(family),  # type: ignore
                                            color='red', fill=False, lw=2))
        if HeatmapConfig.FamilyLabel:
            plt.text((start_idx + end_idx) / 2, len(games) + 0.75, family_names[i], ha='center', va='center', fontsize=18, 
                color='black')
            plt.text(-0.5, (start_idx + end_idx) / 2, family_names[i], rotation='vertical', ha='right', va='center', fontsize=18, 
                color='black')
    # plt.title("Distance Matrix Heatmap")
    if HeatmapConfig.Save:
        plt.savefig('variant_heatmap.pdf',dpi=300, bbox_inches='tight',pad_inches=0)
    else:
        plt.show()
    quit()


    from sklearn.manifold import MDS

    mds = MDS(n_components=2, dissimilarity="precomputed", random_state=42)
    mds_coords = mds.fit_transform(diff_matrix)

    plt.figure(figsize=(10, 8))
    colors = ['red' if game in families[0] else 'blue' if game in families[1] else 'green' if game in families[2] else 'yellow' for game in games]
    plt.scatter(mds_coords[:, 0], mds_coords[:, 1], c=colors, marker='o')

    for i, game in enumerate(games):
        plt.annotate(game.name, (mds_coords[i, 0], mds_coords[i, 1]), fontsize=9)

    plt.title("MDS Projection")
    plt.xlabel("MDS Dimension 1")
    plt.ylabel("MDS Dimension 2")
    plt.show()