import json
import os
import sys
from keyboard import is_pressed

# ANSI escape codes for colors
RED = '\033[91m'
GREEN = '\033[92m'
RESET = '\033[0m'

def display_sample(sample, index, total):
    os.system('cls' if os.name == 'nt' else 'clear')  # Clear the console
    print(f"{GREEN}Sample {index + 1} of {total}:{RESET}\n")
    print(f"{GREEN}Current State View:{RESET}")
    print(sample["current_state_view"])
    # print(f"{GREEN}Current Game View:{RESET}")
    # print(sample["current_game_view"])
    print(f"{GREEN}Action:{RESET} {sample['action']}")
    print(f"{GREEN}Summary:{RESET} {sample['summary']}")
    print(f"{GREEN}Is Valid:{RESET} {RED if not sample['is_valid'] else GREEN}{sample['is_valid']}{RESET}")
    print(f"{GREEN}Next State View:{RESET}")
    print(sample["next_state_view"] if sample["next_state_view"] else f"{RED}None{RESET}")
    # print(f"{GREEN}Next Game View:{RESET}")
    # print(sample["next_game_view"] if sample["next_game_view"] else f"{RED}None{RESET}")
    print("-" * 80)
    print(f"Use the {GREEN}left{RESET} and {GREEN}right{RESET} arrow keys to navigate. Press {RED}Esc{RESET} to exit.")

if __name__ == '__main__':
    dataset_filename = sys.argv[1]
    try:
        # Open and read the JSON file
        with open(dataset_filename, 'r') as file:
            data = json.load(file)

        print(data['description'])
        input("Press any key to continue")
        samples = data.get("samples", [])
        total_samples = len(samples)

        if total_samples == 0:
            print(f"{RED}No samples found in the JSON file.{RESET}")
        else:
            current_index = 0
            display_sample(samples[current_index], current_index, total_samples)

            while True:
                if is_pressed('right'):
                    current_index = (current_index + 1) % total_samples
                    display_sample(samples[current_index], current_index, total_samples)
                    while is_pressed('right'):  # Wait for key release
                        pass
                elif is_pressed('left'):
                    current_index = (current_index - 1) % total_samples
                    display_sample(samples[current_index], current_index, total_samples)
                    while is_pressed('left'):  # Wait for key release
                        pass
                elif is_pressed('esc'):
                    print(f"{RED}Exiting...{RESET}")
                    break

    except FileNotFoundError:
        print(f"{RED}Error: The file '{dataset_filename}' was not found.{RESET}")
    except json.JSONDecodeError:
        print(f"{RED}Error: Failed to decode JSON from the file '{dataset_filename}'.{RESET}")
    except ImportError:
        print(f"{RED}Error: The 'keyboard' module is not installed. Install it using 'pip install keyboard'.{RESET}")
