from __future__ import annotations
from typing import TypeVar, Callable
from itertools import permutations

class DiffPoint:
    def __init__(self, amount: int, max: int) -> None:
        assert 0 <= amount and amount <= max and max > 0
        self.amount = amount
        self.max = max

    def __str__(self) -> str:
        return f'({self.amount}/{self.max})'

class Diffs:
    def __init__(self) -> None:
        self.history: list[DiffPoint] = []
    
    def get_amount(self) -> int:
        return sum(diff.amount for diff in self.history)
    
    def get_max(self) -> int:
        return sum(diff.max for diff in self.history)
    
    def get_diff_points(self) -> int:
        return sum(1 if diff.amount > 0 else 0 for diff in self.history)
    
    def get_max_diff_points(self) -> int:
        return len(self.history)
    
    def get_normalized_diff(self) -> float:
        return self.get_amount() / self.get_max()
    
    def get_sum_normalized_diff(self) -> float:
        return sum(diff.amount/diff.max for diff in self.history)
    
    def get_sum_normalized_diff_normalized(self) -> float:
        return sum(diff.amount/diff.max for diff in self.history) / len(self.history)
    
    def get_normalized_diff_points(self) -> float:
        return self.get_diff_points() / self.get_max_diff_points()
    
    def add_set_diff(self, set1: set, set2: set) -> Diffs:
        amount = len(set1 - set2) + len(set2 - set1)
        max = len(set1) + len(set2)
        if max == 0:
            return self.add(0, 1)
        return self.add(amount, max)
    
    K = TypeVar('K')
    V = TypeVar('V')
    def add_dict_diff(self, dict1: dict[K, V], dict2: dict[K, V], val_diff: Callable[[V, V], Diffs]) -> Diffs:
        diff = Diffs()
        keys1, keys2 = set(dict1.keys()), set(dict2.keys())
        diff.add_set_diff(keys1, keys2)
        for key in keys1.intersection(keys2):
            diff.merge(val_diff(dict1[key], dict2[key]))
        return self.merge(diff)
    
    T = TypeVar('T')
    @staticmethod
    def _get_ordered_deep_list_diff(list1: list[T], list2: list[T], item_diff_func: Callable[[T, T], Diffs], order:list[int]|None=None) -> Diffs:
        diff = Diffs()
        indices: list[int] = list(range(max(len(list1), len(list2)))) if order is None else order
        for i in indices:
            if i < len(list1) and i < len(list2):
                diff.merge(item_diff_func(list1[i], list2[i]))
            else:
                diff.add(0, 1)
        return diff
    
    G = TypeVar('G')
    def add_deep_list_diff(self, list1: list[G], list2: list[G], item_diff_func: Callable[[G, G], Diffs], minimizer_metric: Callable[[Diffs], float], accept_shuffled: bool, greedy: bool) -> Diffs:
        diff = Diffs()
        if greedy and accept_shuffled:
            diff_matrix: list[tuple[Diffs, int, int]] = []
            for i, item1 in enumerate(list1):
                for j, item2 in enumerate(list2):
                    diff_matrix.append((item_diff_func(item1, item2), i, j))
            used1: set[int] = set()
            used2: set[int] = set()
            diff_matrix.sort(key=lambda d: minimizer_metric(d[0]))
            for diff_between, i, j in diff_matrix:
                if i not in used1 and j not in used2:
                    diff.merge(diff_between)
                    used1.add(i)
                    used2.add(j)
        else:
            indices = list(range(max(len(list1), len(list2))))
            orders: list[list[int]] = [indices] if not accept_shuffled else [list(perm) for perm in permutations(indices)]
            diff.merge(min([Diffs._get_ordered_deep_list_diff(list1, list2, item_diff_func, order) for order in orders], key=lambda d: minimizer_metric(d)))
        return self.merge(diff)
    
    def add_count_diff(self, count1, count2) -> Diffs:
        assert count1 >= 0 and count2 >= 0
        if max(count1, count2) == 0:
            return self.add(0, 1)
        return self.add(abs(count1 - count2), max(count1, count2))

    def add(self, val: int, max: int) -> Diffs:
        self.history.append(DiffPoint(val, max))
        return self
    
    def merge(self, other: Diffs) -> Diffs:
        for abs_diff in other.history:
            self.add(abs_diff.amount, abs_diff.max)
        return self
    
    @staticmethod
    def get_merged(diffs: list[Diffs]) -> Diffs:
        ret = Diffs()
        for diff in diffs:
            ret.merge(diff)
        return ret
    
    def __str__(self) -> str:
        return ','.join([str(abs_diff) for abs_diff in self.history])