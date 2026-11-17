/**
 * Savyant Systems - Dynamic Sales Order Form Controller
 * Implements Part 7 Requirements:
 * - Dynamic rows addition & deletion
 * - Live product price & stock fetching
 * - Real-time calculations (Item Amount, Subtotal, Discount, Grand Total)
 * - Validation & Duplicate Product Detection
 * - Duplicate submission prevention
 */

// Global product catalog cache (populated by backend template)
let productCatalog = {};

function initOrderForm(catalogData) {
    if (catalogData) {
        productCatalog = catalogData;
    }
    
    // Wire existing rows
    const rows = document.querySelectorAll('.order-item-row');
    rows.forEach(row => attachRowListeners(row));

    // Wire discount input
    const discountInput = document.getElementById('discount_percentage');
    if (discountInput) {
        discountInput.addEventListener('input', calculateOrderTotals);
    }

    // Initial calculation
    calculateOrderTotals();
}

function attachRowListeners(row) {
    const productSelect = row.querySelector('.product-select');
    const quantityInput = row.querySelector('.quantity-input');
    const removeBtn = row.querySelector('.btn-remove-row');

    if (productSelect) {
        productSelect.addEventListener('change', function () {
            onProductSelected(row, this.value);
        });
    }

    if (quantityInput) {
        quantityInput.addEventListener('input', function () {
            calculateRowAmount(row);
            calculateOrderTotals();
        });
    }

    if (removeBtn) {
        removeBtn.addEventListener('click', function () {
            removeRow(row);
        });
    }
}

function onProductSelected(row, productId) {
    const priceDisplay = row.querySelector('.rate-display');
    const stockDisplay = row.querySelector('.stock-display');
    const rateInput = row.querySelector('.rate-hidden');

    if (!productId) {
        priceDisplay.textContent = '₹0.00';
        stockDisplay.textContent = '-';
        if (rateInput) rateInput.value = '0.00';
        calculateRowAmount(row);
        calculateOrderTotals();
        return;
    }

    // If present in catalog cache, use it immediately
    if (productCatalog[productId]) {
        updateRowProductInfo(row, productCatalog[productId]);
    } else {
        // Otherwise fetch dynamically via API as mandated by Part 7
        fetch(`/products/${productId}/info`)
            .then(res => res.json())
            .then(data => {
                productCatalog[productId] = data;
                updateRowProductInfo(row, data);
            })
            .catch(err => {
                console.error("Failed to fetch product info:", err);
            });
    }
}

function updateRowProductInfo(row, product) {
    const priceDisplay = row.querySelector('.rate-display');
    const stockDisplay = row.querySelector('.stock-display');
    const rateInput = row.querySelector('.rate-hidden');

    const price = parseFloat(product.price) || 0.0;
    priceDisplay.textContent = '₹' + price.toFixed(2);
    if (rateInput) rateInput.value = price.toFixed(2);

    const stock = parseInt(product.stock_quantity) || 0;
    if (stock <= 5) {
        stockDisplay.innerHTML = `<span class="badge badge-danger" title="Low Stock">${stock} available</span>`;
    } else {
        stockDisplay.innerHTML = `<span class="badge badge-secondary">${stock} available</span>`;
    }

    calculateRowAmount(row);
    calculateOrderTotals();
}

function calculateRowAmount(row) {
    const rateInput = row.querySelector('.rate-hidden');
    const quantityInput = row.querySelector('.quantity-input');
    const amountDisplay = row.querySelector('.amount-display');

    const rate = parseFloat(rateInput ? rateInput.value : 0) || 0.0;
    const qty = parseInt(quantityInput.value) || 0;

    const amount = qty * rate;
    amountDisplay.textContent = '₹' + amount.toFixed(2);
}

function calculateOrderTotals() {
    let subtotal = 0.0;
    const rows = document.querySelectorAll('.order-item-row');

    rows.forEach(row => {
        const rateInput = row.querySelector('.rate-hidden');
        const quantityInput = row.querySelector('.quantity-input');
        const rate = parseFloat(rateInput ? rateInput.value : 0) || 0.0;
        const qty = parseInt(quantityInput ? quantityInput.value : 0) || 0;
        subtotal += (qty * rate);
    });

    const discountInput = document.getElementById('discount_percentage');
    let discountPct = parseFloat(discountInput ? discountInput.value : 0) || 0.0;

    if (discountPct < 0) discountPct = 0;
    if (discountPct > 20) discountPct = 20;

    const discountAmount = subtotal * (discountPct / 100.0);
    const grandTotal = Math.max(0, subtotal - discountAmount);

    document.getElementById('subtotal-display').textContent = '₹' + subtotal.toFixed(2);
    document.getElementById('discount-display').textContent = '₹' + discountAmount.toFixed(2);
    document.getElementById('grand-total-display').textContent = '₹' + grandTotal.toFixed(2);
}

function addRow() {
    const tbody = document.getElementById('order-items-body');
    const template = document.getElementById('row-template');
    
    // Clone template content
    const newRow = template.content.cloneNode(true).querySelector('tr');
    tbody.appendChild(newRow);

    attachRowListeners(newRow);
    updateRemoveButtons();
}

function removeRow(row) {
    const rows = document.querySelectorAll('.order-item-row');
    if (rows.length <= 1) {
        alert("An order must contain at least one item.");
        return;
    }
    row.remove();
    updateRemoveButtons();
    calculateOrderTotals();
}

function updateRemoveButtons() {
    const rows = document.querySelectorAll('.order-item-row');
    const removeButtons = document.querySelectorAll('.btn-remove-row');
    removeButtons.forEach(btn => {
        btn.disabled = (rows.length <= 1);
    });
}

function validateOrderForm(form) {
    const customerSelect = form.querySelector('#customer_id');
    if (!customerSelect.value) {
        alert("Please select a customer.");
        customerSelect.focus();
        return false;
    }

    const rows = document.querySelectorAll('.order-item-row');
    if (rows.length === 0) {
        alert("An order requires at least one product item.");
        return false;
    }

    const seenProducts = new Set();
    for (let i = 0; i < rows.length; i++) {
        const row = rows[i];
        const select = row.querySelector('.product-select');
        const qtyInput = row.querySelector('.quantity-input');

        const productId = select.value;
        const qty = parseInt(qtyInput.value) || 0;

        if (!productId) {
            alert(`Row ${i + 1}: Please select a product.`);
            select.focus();
            return false;
        }

        if (seenProducts.has(productId)) {
            alert(`Row ${i + 1}: Duplicate product selected. Each product can only appear once per order.`);
            select.focus();
            return false;
        }
        seenProducts.add(productId);

        if (qty <= 0) {
            alert(`Row ${i + 1}: Quantity must be at least 1.`);
            qtyInput.focus();
            return false;
        }
    }

    const discountInput = document.getElementById('discount_percentage');
    const discount = parseFloat(discountInput.value) || 0;
    if (discount < 0 || discount > 20) {
        alert("Discount percentage must be between 0% and 20%.");
        discountInput.focus();
        return false;
    }

    return true;
}
