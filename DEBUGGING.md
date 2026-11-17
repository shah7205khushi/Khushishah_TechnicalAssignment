# Debugging Exercise Write-up (Part 13)

## 1. Overview & Problem Statement
In technical assessment Part 13, the following Python function was provided to calculate the total amount for an order from a list of line items:

```python
def calculate_total(items):
    total = 0
    for item in items:
        amount = item['qty'] * item['rate']
        total = amount
    return total
```

When tested with input:
```python
items = [{'qty': 2, 'rate': 100}, {'qty': 3, 'rate': 50}]
```
The expected total is `350` (`2 * 100 + 3 * 50 = 200 + 150 = 350`), but the function returned `150`.

---

## 2. Root Cause Analysis

### Primary Bug: Reassignment Instead of Accumulation
Inside the `for` loop, line 5 performs an assignment rather than an accumulation:
```python
total = amount
```
On each iteration, the previous value of `total` is overwritten by the current line item's amount. As a result, the function disregards all preceding line items and returns solely the amount of the very last item in the list (`3 * 50 = 150`).

To fix this, the value must be accumulated:
```python
total += amount
```

---

## 3. Unhandled Edge Cases & Deficiencies

Beyond the primary accumulation bug, the original snippet has critical flaws that prevent it from being safe for production financial transactions:

1. **Floating-Point Representation Drift**:
   Using standard Python floats (`float`) for monetary rates results in binary IEEE 754 precision inaccuracies (e.g., `0.1 + 0.2 = 0.30000000000000004`). In financial and sales order systems, all amounts must use fixed-point arithmetic (`decimal.Decimal`) and standard half-up rounding (`ROUND_HALF_UP`) quantized to two decimal places (`0.01`).

2. **Empty List Input**:
   Calling `calculate_total([])` technically returns `0`, but in the original code it is returned as an untyped integer `0` instead of a standardized financial monetary object (`Decimal('0.00')`).

3. **`None` or Invalid Container Type**:
   If `items` is `None` or not an iterable list/tuple (e.g. integer, string, boolean), the loop raises an unhandled `TypeError` with an unhelpful system trace.

4. **Invalid Line Item Structure (Non-Dictionary Items)**:
   If the list contains elements that are not dictionaries (e.g., `[{"qty": 2, "rate": 100}, "invalid"]`), accessing `item['qty']` raises an unhandled `TypeError: string indices must be integers`.

5. **Missing Keys (`KeyError`)**:
   If an item dictionary lacks the required key `'qty'` or `'rate'`, Python raises an unhandled `KeyError`. The function should validate the presence of both keys and raise an explicit, readable error indicating which item at which index failed validation.

6. **Invalid or Malformed Data Types**:
   If quantity is non-integer (e.g., `"two"`) or rate is non-numeric (e.g., `"N/A"`), type conversion fails. Explicit validation ensures informative error messages.

7. **Negative Quantities or Rates**:
   Sales order line items cannot have negative quantities or negative unit rates. Negative values would silently subtract money from the order total, opening vulnerabilities to financial tampering or accidental corruption.

---

## 4. Refactored Production Solution

The refactored implementation is located in [`debugging_exercise/calculate_total.py`](file:///d:/tech_ass/debugging_exercise/calculate_total.py):

```python
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

def calculate_total(items):
    """
    Calculates the total monetary amount for a list of line items.

    Args:
        items (list of dict): List of items, each containing 'qty' and 'rate'.
                              Example: [{'qty': 2, 'rate': 100}, {'qty': 3, 'rate': 50}]

    Returns:
        Decimal: Total amount rounded to 2 decimal places.

    Raises:
        TypeError: If items is not an iterable list, or item is not a dictionary.
        KeyError: If an item is missing 'qty' or 'rate'.
        ValueError: If quantity or rate is negative, or cannot be converted to numeric.
    """
    # 1. Validate container type
    if items is None:
        return Decimal('0.00')

    if not isinstance(items, (list, tuple)):
        raise TypeError(f"Expected items to be a list or tuple, received {type(items).__name__}.")

    # 2. Empty list returns zero
    if len(items) == 0:
        return Decimal('0.00')

    total = Decimal('0.00')

    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise TypeError(f"Item at index {index} must be a dictionary, received {type(item).__name__}.")

        # 3. Check for missing keys
        if "qty" not in item:
            raise KeyError(f"Item at index {index} is missing required key 'qty'.")
        if "rate" not in item:
            raise KeyError(f"Item at index {index} is missing required key 'rate'.")

        raw_qty = item["qty"]
        raw_rate = item["rate"]

        # 4. Validate and parse Quantity
        try:
            qty = int(raw_qty)
        except (ValueError, TypeError):
            raise ValueError(f"Item at index {index} has invalid quantity '{raw_qty}'. Must be an integer.")

        if qty < 0:
            raise ValueError(f"Item at index {index} has negative quantity '{qty}'. Quantity cannot be negative.")

        # 5. Validate and parse Rate
        try:
            rate = Decimal(str(raw_rate))
        except (InvalidOperation, TypeError, ValueError):
            raise ValueError(f"Item at index {index} has invalid rate '{raw_rate}'. Must be a valid numeric amount.")

        if rate < Decimal('0.00'):
            raise ValueError(f"Item at index {index} has negative rate '{rate}'. Rate cannot be negative.")

        # 6. Accumulate item amount (Fixing the bug: use total += amount instead of total = amount)
        item_amount = Decimal(qty) * rate
        total += item_amount

    # 7. Return quantized decimal
    return total.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
```

---

## 5. Comprehensive Test Suite

The test suite in [`tests/test_debugging.py`](file:///d:/tech_ass/tests/test_debugging.py) systematically tests the function against all normal and edge scenarios:

| Test Case | Input | Expected Output / Behavior |
|:---|:---|:---|
| `test_standard_order_calculation` | `[{'qty': 2, 'rate': 100}, {'qty': 3, 'rate': 50}]` | `Decimal('350.00')` (Fixed accumulator bug) |
| `test_single_item` | `[{'qty': 5, 'rate': 25.50}]` | `Decimal('127.50')` |
| `test_floating_point_precision` | `[{'qty': 3, 'rate': 19.99}, {'qty': 7, 'rate': 0.10}]` | `Decimal('60.67')` (No IEEE float drift) |
| `test_empty_list` | `[]` | `Decimal('0.00')` |
| `test_none_input` | `None` | `Decimal('0.00')` |
| `test_zero_quantity_or_rate` | `[{'qty': 0, 'rate': 150}, {'qty': 4, 'rate': 0}]` | `Decimal('0.00')` |
| `test_missing_qty_key` | `[{'rate': 100}]` | Raises `KeyError: 'qty'` |
| `test_missing_rate_key` | `[{'qty': 2}]` | Raises `KeyError: 'rate'` |
| `test_negative_quantity` | `[{'qty': -2, 'rate': 50}]` | Raises `ValueError: ... negative quantity` |
| `test_negative_rate` | `[{'qty': 2, 'rate': -50}]` | Raises `ValueError: ... negative rate` |
| `test_non_numeric_quantity` | `[{'qty': 'two', 'rate': 50}]` | Raises `ValueError: ... invalid quantity` |
| `test_non_numeric_rate` | `[{'qty': 2, 'rate': 'abc'}]` | Raises `ValueError: ... invalid rate` |
| `test_invalid_items_container_type`| `"not a list"` | Raises `TypeError: Expected items to be a list...` |
| `test_invalid_item_element_type` | `[{'qty': 2, 'rate': 50}, "invalid"]` | Raises `TypeError: ... must be a dictionary` |

All 14 tests pass cleanly via `python -m pytest tests/test_debugging.py -v`.
