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
