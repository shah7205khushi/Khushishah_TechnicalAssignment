import pytest
from decimal import Decimal
from debugging_exercise.calculate_total import calculate_total


class TestCalculateTotal:
    """Comprehensive test suite for calculate_total function (Part 13)."""

    def test_standard_order_calculation(self):
        """Test calculation with multiple valid line items matching prompt example."""
        items = [
            {"qty": 2, "rate": 100},
            {"qty": 3, "rate": 50}
        ]
        # (2 * 100) + (3 * 50) = 200 + 150 = 350
        result = calculate_total(items)
        assert result == Decimal('350.00')

    def test_single_item(self):
        """Test calculation with a single valid line item."""
        items = [{"qty": 5, "rate": 25.50}]
        # 5 * 25.50 = 127.50
        result = calculate_total(items)
        assert result == Decimal('127.50')

    def test_floating_point_precision(self):
        """Test that monetary values do not suffer from float representation errors."""
        items = [
            {"qty": 3, "rate": 19.99},
            {"qty": 7, "rate": 0.10}
        ]
        # 3 * 19.99 = 59.97; 7 * 0.10 = 0.70; Total = 60.67
        result = calculate_total(items)
        assert result == Decimal('60.67')

    def test_empty_list(self):
        """Test that an empty list returns 0.00."""
        result = calculate_total([])
        assert result == Decimal('0.00')

    def test_none_input(self):
        """Test that passing None safely returns 0.00."""
        result = calculate_total(None)
        assert result == Decimal('0.00')

    def test_zero_quantity_or_rate(self):
        """Test items with zero quantity or zero rate."""
        items = [
            {"qty": 0, "rate": 150},
            {"qty": 4, "rate": 0}
        ]
        result = calculate_total(items)
        assert result == Decimal('0.00')

    def test_missing_qty_key(self):
        """Test that missing 'qty' raises a KeyError."""
        items = [{"rate": 100}]
        with pytest.raises(KeyError) as exc_info:
            calculate_total(items)
        assert "qty" in str(exc_info.value)

    def test_missing_rate_key(self):
        """Test that missing 'rate' raises a KeyError."""
        items = [{"qty": 2}]
        with pytest.raises(KeyError) as exc_info:
            calculate_total(items)
        assert "rate" in str(exc_info.value)

    def test_negative_quantity(self):
        """Test that negative quantity raises a ValueError."""
        items = [{"qty": -2, "rate": 50}]
        with pytest.raises(ValueError) as exc_info:
            calculate_total(items)
        assert "negative quantity" in str(exc_info.value).lower()

    def test_negative_rate(self):
        """Test that negative rate raises a ValueError."""
        items = [{"qty": 2, "rate": -50}]
        with pytest.raises(ValueError) as exc_info:
            calculate_total(items)
        assert "negative rate" in str(exc_info.value).lower()

    def test_non_numeric_quantity(self):
        """Test that string or non-numeric quantity raises ValueError."""
        items = [{"qty": "two", "rate": 50}]
        with pytest.raises(ValueError) as exc_info:
            calculate_total(items)
        assert "invalid quantity" in str(exc_info.value).lower()

    def test_non_numeric_rate(self):
        """Test that non-numeric rate raises ValueError."""
        items = [{"qty": 2, "rate": "abc"}]
        with pytest.raises(ValueError) as exc_info:
            calculate_total(items)
        assert "invalid rate" in str(exc_info.value).lower()

    def test_invalid_items_container_type(self):
        """Test that passing invalid container type raises TypeError."""
        with pytest.raises(TypeError) as exc_info:
            calculate_total("not a list")
        assert "Expected items to be a list" in str(exc_info.value)

    def test_invalid_item_element_type(self):
        """Test that non-dict items inside list raise TypeError."""
        items = [{"qty": 2, "rate": 50}, "invalid_item"]
        with pytest.raises(TypeError) as exc_info:
            calculate_total(items)
        assert "must be a dictionary" in str(exc_info.value)
