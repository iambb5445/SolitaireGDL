import os
import json

RESULTS_DIR = "results"

def get_base_name(filename):
    # Remove timestamp and sample count, keep game and bot
    # Example: "Klondike_DFSBot_1749860054_1000samples.json" -> "Klondike_DFSBot"
    parts = filename.split('_')
    if len(parts) < 4:
        return None
    return '_'.join(parts[:-2])

def find_newer_1sample_files(files):
    # Map base_name -> (filename, description)
    one_sample = {}
    for fname in files:
        if fname.endswith("1samples.json"):
            base = get_base_name(fname)
            if base:
                with open(os.path.join(RESULTS_DIR, fname), encoding="utf-8") as f:
                    data = json.load(f)
                desc = data.get("description", "")
                one_sample[base] = desc
    return one_sample

def swap_descriptions():
    files = [f for f in os.listdir(RESULTS_DIR) if f.endswith(".json")]
    one_sample_descs = find_newer_1sample_files(files)
    for fname in files:
        if fname.endswith("1000samples.json"):
            base = get_base_name(fname)
            if base and base in one_sample_descs:
                path = os.path.join(RESULTS_DIR, fname)
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
                old_desc = data.get("description", "")
                new_desc = one_sample_descs[base]
                if old_desc != new_desc:
                    data["description"] = new_desc
                    with open(path, "w", encoding="utf-8") as f:
                        json.dump(data, f, indent=4)
                    print(f"Updated description in {fname}")
                else:
                    print(f"No change needed for {fname}")

if __name__ == "__main__":
    swap_descriptions()