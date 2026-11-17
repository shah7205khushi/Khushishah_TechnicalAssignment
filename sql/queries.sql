-- ============================================================================
-- SAVYANT SYSTEMS TECHNICAL ASSESSMENT: PART 9 STANDALONE SQL QUERIES
-- Database: savyant_inventory_db
-- ============================================================================

USE savyant_inventory_db;

-- ----------------------------------------------------------------------------
-- QUERY 1: Top three customers by Confirmed order grand total
-- Description: Aggregates grand total of Confirmed orders per customer and 
--              returns the top 3 highest spending customers.
-- ----------------------------------------------------------------------------
SELECT 
    c.id AS customer_id,
    c.name AS customer_name,
    c.email AS customer_email,
    COUNT(so.id) AS confirmed_order_count,
    ROUND(COALESCE(SUM(so.grand_total), 0.00), 2) AS total_confirmed_grand_total
FROM customers c
INNER JOIN sales_orders so 
    ON c.id = so.customer_id
WHERE so.status = 'confirmed'
GROUP BY c.id, c.name, c.email
ORDER BY total_confirmed_grand_total DESC
LIMIT 3;


-- ----------------------------------------------------------------------------
-- QUERY 2: Top three products by quantity sold in Confirmed orders
-- Description: Sums the total quantity ordered for each product across 
--              Confirmed orders, and returns the top 3 best-selling products.
-- ----------------------------------------------------------------------------
SELECT 
    p.id AS product_id,
    p.product_code,
    p.name AS product_name,
    p.category,
    COALESCE(SUM(soi.quantity), 0) AS total_quantity_sold,
    ROUND(COALESCE(SUM(soi.amount), 0.00), 2) AS gross_sales_value
FROM products p
INNER JOIN sales_order_items soi 
    ON p.id = soi.product_id
INNER JOIN sales_orders so 
    ON soi.sales_order_id = so.id
WHERE so.status = 'confirmed'
GROUP BY p.id, p.product_code, p.name, p.category
ORDER BY total_quantity_sold DESC, gross_sales_value DESC
LIMIT 3;


-- ----------------------------------------------------------------------------
-- QUERY 3: Customers who have never placed any order
-- Description: Finds all customers who have zero records in sales_orders table
--              (neither Draft, Confirmed, nor Cancelled).
-- ----------------------------------------------------------------------------
SELECT 
    c.id AS customer_id,
    c.name AS customer_name,
    c.email AS customer_email,
    c.mobile AS customer_mobile,
    c.city AS customer_city,
    c.status AS customer_status
FROM customers c
LEFT JOIN sales_orders so 
    ON c.id = so.customer_id
WHERE so.id IS NULL
ORDER BY c.name ASC;


-- ----------------------------------------------------------------------------
-- QUERY 4: Month-wise Confirmed sales totals, grouped by year and month
-- Description: Aggregates order count, subtotal, discount, and grand total 
--              of Confirmed orders grouped by Year and Month.
-- ----------------------------------------------------------------------------
SELECT 
    YEAR(so.order_date) AS order_year,
    MONTH(so.order_date) AS order_month,
    DATE_FORMAT(so.order_date, '%Y-%m') AS year_month_label,
    COUNT(so.id) AS confirmed_order_count,
    ROUND(SUM(so.subtotal), 2) AS total_subtotal,
    ROUND(SUM(so.discount_amount), 2) AS total_discount_amount,
    ROUND(SUM(so.grand_total), 2) AS total_net_sales
FROM sales_orders so
WHERE so.status = 'confirmed'
GROUP BY YEAR(so.order_date), MONTH(so.order_date), DATE_FORMAT(so.order_date, '%Y-%m')
ORDER BY order_year DESC, order_month DESC;


-- ----------------------------------------------------------------------------
-- QUERY 5: Products below a supplied stock threshold
-- Description: Returns all products with stock_quantity strictly less than 
--              or equal to a given threshold (e.g. threshold = 10).
-- ----------------------------------------------------------------------------
-- Replace @threshold with the desired value (e.g. 10)
SET @threshold = 10;

SELECT 
    p.id AS product_id,
    p.product_code,
    p.name AS product_name,
    p.category,
    p.price,
    p.stock_quantity,
    p.status,
    CASE 
        WHEN p.stock_quantity = 0 THEN 'OUT_OF_STOCK'
        WHEN p.stock_quantity <= 5 THEN 'CRITICAL_LOW'
        ELSE 'LOW_STOCK'
    END AS stock_alert_level
FROM products p
WHERE p.stock_quantity <= @threshold
ORDER BY p.stock_quantity ASC, p.name ASC;
