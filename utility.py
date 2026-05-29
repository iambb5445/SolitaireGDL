from enum import StrEnum
from typing import TypeVar, Callable
import random

class TextUtil:
    class TEXT_COLOR(StrEnum):
        Red = '\033[91m'
        Green = '\033[92m'
        Blue = '\033[94m'
        Cyan = '\033[96m'
        White = '\033[97m'
        Yellow = '\033[93m'
        Magenta = '\033[95m'
        Grey = '\033[90m'
        Black = '\033[90m'
        Default = '\033[99m'

    @staticmethod
    def get_colored_text(text: str, color: TEXT_COLOR):
        reset = '\033[0m'
        return color + text + reset
    
class Logger:
    def __init__(self, active: bool, filename: str|None=None, storage_size: int=1):
        self.active = active
        self.static_activate = active
        self.filename = filename
        if filename is not None:
            import os
            # possibly instead of throwing errors, change filename to unique name or None as a fallback option?
            assert not os.path.isfile(filename), f"cannot log in file singe {filename} already exists."
        self.storage = ""
        self.storage_size = storage_size
    
    def info(self, s: str) -> None:
        if self.active:
            if self.filename is None:
                print(s)
            else:
                self.storage += s + "\n"
                if len(self.storage) >= self.storage_size:
                    self.flush_storage()
    
    def flush_storage(self): # this should be manually called from outside if storage size is more than 1
        if self.filename is not None:
            with open(self.filename, "a") as f:
                f.write(self.storage)
                self.storage = ""

    def info_from(self, l: list[str|tuple[Callable, list]]):
        s = ''
        if not self.active:
            return
        for val in l:
            if isinstance(val, str):
                s += val
            else:
                s += val[0](*val[1])
        self.info(s)

    def temp_activate(self):
        self.active = True
    
    def temp_deactivate(self):
        self.active = False

    def revert_activation(self):
        self.active = self.static_activate
    
T = TypeVar('T')
def cast(s: str, type_cast: Callable[..., T], default: T|None=None, supress_error:bool=True) -> T|None:
    try:
        return type_cast(s)
    except ValueError as e:
        if supress_error:
            return default
        raise e
    
G = TypeVar('G')
def get_max_elements(elements: list[G], map_func: Callable[[G], float|int]) -> list[G]:
        values: list[int|float] = [map_func(element) for element in elements]
        max_value: float|int = max(values)
        return [element for element, value in zip(elements, values) if value == max_value]
    
def get_safe_filename(filename: str, timed:bool=False, extension:str|None=None):
    import time
    keepcharacters = (' ','.','_', '-')
    filename = "".join(c for c in filename if c.isalnum() or c in keepcharacters).rstrip()
    if timed:
        filename += f"_{int(time.time())}"
    if extension is not None:
        extension = "".join(c for c in extension if c.isalnum() or c in keepcharacters).rstrip()
        filename += f".{extension}"
    return filename

def get_seed(rnd: random.Random|None, max=10000000):
    if rnd is None:
        rnd = random.Random()
    return rnd.randint(0, max)

# get unique elements without changing the order (only works if T is hashable)
def get_uniques(l: list[T]):
    # return list(set(l)) # may change the order
    return list(dict.fromkeys(l))