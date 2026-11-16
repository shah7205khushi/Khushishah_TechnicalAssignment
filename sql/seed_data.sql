-- ========================================================
-- SAVYANT SYSTEMS TECHNICAL ASSESSMENT: SAMPLE SEED DATA
-- Database: savyant_inventory_db
-- ========================================================

USE savyant_inventory_db;

-- 1. Insert Initial Users
-- Passwords:
-- admin@savyant.com  => Admin@123
-- sales@savyant.com  => Sales@123
INSERT INTO users (id, name, email, password_hash, role, created_at)
VALUES 
(1, 'System Administrator', 'admin@savyant.com', 'scrypt:32768:8:1$TucGSbr3zkC7LhQP$dda06ce6265cb7029c800e14565ed20a79feb32dd209a7df6151cd979261fb73fc615bcaf119c5badb36ef75c9b20a283981c7cb845d1d7e279aa6c0f79c66cf', 'admin', NOW()),
(2, 'Sarah Sales', 'sales@savyant.com', 'scrypt:32768:8:1$ZKscS994JxNT8APD$dcff6797f73913b831ad66f5f62b44a655bd465302f7a9ed94e5f1979cf4f03022274aad497ef218907f7d7c978938b0b3eec62c00e20601ad5edfe91923b728', 'sales_user', NOW())
ON DUPLICATE KEY UPDATE name=VALUES(name);

-- 2. Insert Customers
INSERT INTO customers (id, name, email, mobile, city, status, created_at)
VALUES
(1, 'Acme Retail Solutions', 'purchasing@acmeretail.com', '9876543210', 'Mumbai', 'active', NOW()),
(2, 'TechCore Enterprises', 'procurement@techcore.in', '9811223344', 'Bengaluru', 'active', NOW()),
(3, 'Nexus Trading Co', 'nexus.orders@gmail.com', '9988776655', 'Delhi', 'active', NOW()),
(4, 'Zenith Infotech', 'zenith.purchase@zenith.com', '9765432109', 'Pune', 'active', NOW()),
(5, 'Dormant Enterprise', 'contact@dormant.com', '9123456780', 'Chennai', 'inactive', NOW())
ON DUPLICATE KEY UPDATE name=VALUES(name);

-- 3. Insert Products
INSERT INTO products (id, product_code, name, category, price, stock_quantity, status, created_at)
VALUES
(1, 'PRD-001', 'Ergonomic Mechanical Keyboard', 'Accessories', 1500.00, 45, 'active', NOW()),
(2, 'PRD-002', 'Wireless Optical Mouse', 'Accessories', 500.00, 80, 'active', NOW()),
(3, 'PRD-003', '27-inch 4K IPS Monitor', 'Displays', 22000.00, 15, 'active', NOW()),
(4, 'PRD-004', 'USB-C Multiport Hub', 'Accessories', 1800.00, 30, 'active', NOW()),
(5, 'PRD-005', 'Noise-Cancelling Headset', 'Audio', 3500.00, 25, 'active', NOW()),
(6, 'PRD-006', 'High-Speed HDMI 2.1 Cable', 'Cables', 450.00, 5, 'active', NOW()),
(7, 'PRD-007', 'Discontinued Legacy Adapter', 'Adapters', 250.00, 0, 'inactive', NOW())
ON DUPLICATE KEY UPDATE name=VALUES(name);

-- 4. Insert Initial Opening Stock Movements
INSERT INTO stock_movements (product_id, movement_type, quantity_change, related_order_id, reason, created_by, created_at)
VALUES
(1, 'OPENING_STOCK', 45, NULL, 'Initial system opening stock', 1, NOW()),
(2, 'OPENING_STOCK', 80, NULL, 'Initial system opening stock', 1, NOW()),
(3, 'OPENING_STOCK', 15, NULL, 'Initial system opening stock', 1, NOW()),
(4, 'OPENING_STOCK', 30, NULL, 'Initial system opening stock', 1, NOW()),
(5, 'OPENING_STOCK', 25, NULL, 'Initial system opening stock', 1, NOW()),
(6, 'OPENING_STOCK', 5,  NULL, 'Initial system opening stock', 1, NOW());
