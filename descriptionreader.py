import json
import os
from colorama import Fore, Style, init

init(autoreset=True)

def color_section(title, color=Fore.CYAN):
    print(f"{color}{Style.BRIGHT}{'='*10} {title} {'='*10}{Style.RESET_ALL}")

def color_text(text, color=Fore.WHITE):
    print(f"{color}{text}{Style.RESET_ALL}")

def list_result_files(directory, filter_name=None, filter_bot=None):
    files = []
    for fname in os.listdir(directory):
        if fname.endswith('.json'):
            path = os.path.join(directory, fname)
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                if (not filter_name or filter_name.lower() in str(data.get('name', '')).lower()) and \
                   (not filter_bot or filter_bot.lower() in str(data.get('bot', '')).lower()):
                    files.append((fname, data))
            except Exception:
                continue
    return files

def load_prompt():
    with open("prompt.txt", "r", encoding="utf-8") as f:
        return f.read()

def build_full_description(data, prompt_template):
    game_name = data.get("name", "")
    game_desc = data.get("description", "")
    # Fill in the placeholders in the prompt
    prompt_filled = prompt_template.replace("{game_name}", game_name).replace("{game_desc}", game_desc)
    return prompt_filled

def highlight_description(desc: str):
    for line in desc.splitlines():
        lstrip = line.lstrip()
        if lstrip.lower().startswith("goal") or "win" in lstrip.lower():
            print(Fore.YELLOW + Style.BRIGHT + line)
        elif lstrip.lower().startswith("setup") or "deal" in lstrip.lower():
            print(Fore.CYAN + Style.BRIGHT + line)
        elif lstrip.lower().startswith("move") or "action" in lstrip.lower():
            print(Fore.MAGENTA + Style.BRIGHT + line)
        elif lstrip.strip() == "":
            print()
        else:
            print(Fore.GREEN + line)

def print_file(idx, files, prompt_template):
    fname, data = files[idx]
    os.system('cls' if os.name == 'nt' else 'clear')
    color_section(f"File {idx}: {fname}", Fore.MAGENTA)
    color_text(f"Name: {data.get('name', '')}", Fore.LIGHTBLACK_EX)
    color_text(f"Bot: {data.get('bot', '')}", Fore.LIGHTBLACK_EX)
    color_text(f"Sample Count: {data.get('sample_count', '')}", Fore.LIGHTBLACK_EX)
    color_section("DESCRIPTION + PROMPT", Fore.YELLOW)
    full_desc = build_full_description(data, prompt_template)
    highlight_description(full_desc)
    print(Fore.LIGHTBLACK_EX + '-'*60)

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--dir', default='results', help='Directory to search for result files')
    parser.add_argument('--name', help='Filter by game name')
    parser.add_argument('--bot', help='Filter by bot name')
    args = parser.parse_args()

    files = list_result_files(args.dir, args.name, args.bot)
    if not files:
        print("No result files found with the given filters.")
        return

    prompt_template = load_prompt()

    print(Fore.CYAN + Style.BRIGHT + "Available files:")
    for idx, (fname, data) in enumerate(files):
        print(f"{Fore.YELLOW}{idx}: {Fore.WHITE}{fname} {Fore.LIGHTBLACK_EX}({data.get('name','')}, {data.get('bot','')}, {data.get('sample_count','')} samples)")
    print()

    idx = 0
    while True:
        print_file(idx, files, prompt_template)
        inp = input(Fore.LIGHTCYAN_EX + f"Viewing file {idx}. Enter index to view, n/p for next/prev, q to quit: " + Style.RESET_ALL).strip().lower()
        if inp == "q":
            break
        elif inp == "n":
            idx = (idx + 1) % len(files)
        elif inp == "p":
            idx = (idx - 1) % len(files)
        elif inp.isdigit() and 0 <= int(inp) < len(files):
            idx = int(inp)
        else:
            print(Fore.RED + "Invalid input." + Style.RESET_ALL)

if __name__ == "__main__":
    main()