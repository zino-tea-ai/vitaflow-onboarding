from typing import List, Any, Callable, Optional


def sort_list(
    data: List[Any],
    key: Optional[Callable] = None,
    reverse: bool = False
) -> List[Any]:
    """通螨排序函数
    
    Args:
        data: 要排序的列表
        key: 排序键函数 (可选)
        reverse: 是否降序排列，默认升序
    
    Returns:
        排序后的新列表
    """
    return sorted(data, key=key, reverse=reverse)


def quick_sort(arr: List[int]) -> List[int]:
    """快速排序实现"""
    if len(arr) <= 1:
        return arr
    pivot = arr[len(arr) // 2]
    left = [x for x in arr if x < pivot]
    middle = [x for x in arr if x == pivot]
    right = [x for x in arr if x > pivot]
    return quick_sort(left) + middle + quick_sort(right)


if __name__ == "__main__":
    test = [64, 34, 25, 12, 22, 11, 90]
    print(f"原始: {test}")
    print(f"排序: {sort_list(test)}")
    print(f"快排: {quick_sort(test)}")