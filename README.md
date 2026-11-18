# Savyant Systems — Sales Order & Inventory Management System

A production-ready, full-stack web application designed for small trading businesses to manage master customer and product data, create dynamic multi-line sales orders, maintain strict inventory consistency under concurrency, generate business reports, and expose authenticated REST APIs.

Built for the **Savyant Systems Technical Assignment (Fresher / Trainee Software Developer)**.

---

## Table of Contents
1. [Core Features](#core-features)
2. [Technology Stack](#technology-stack)
3. [System Architecture](#system-architecture)
4. [Database Design & Relationships](#database-design--relationships)
5. [Concurrency & Inventory Consistency](#concurrency--inventory-consistency)
6. [Prerequisites & Local Setup](#prerequisites--local-setup)
7. [Default Sample Accounts](#default-sample-accounts)
8. [Automated Testing (Pytest)](#automated-testing-pytest)
9. [REST API Documentation](#rest-api-documentation)
10. [Standalone SQL Queries](#standalone-sql-queries)
11. [Assumptions & Scope Limits](#assumptions--scope-limits)

---

## Core Features

- **Role-Based Authentication & Access Control**:
  - **Admin**: Full master data management (CRUD customers & products), manual stock adjustments, view and manage all orders, view executive sales & stock reports, CSV bulk import.
  - **Sales User**: View active customers & products, create/edit their own draft orders, confirm/cancel their orders.
  - **IDOR Protection**: Sales users cannot access, edit, confirm, or cancel another user's order by tampering with URLs or order IDs.
- **Customer & Product Master Data**:
  - Real-time search, category filters, and active/inactive status filters.
  - **Safe Deletion Protection**: Cannot delete customers or products referenced in existing orders or stock ledger; the system safely prompts deactivation instead.
  - Admin stock adjustments with mandatory audit reason.
- **Dynamic Sales Order Creation (Vanilla JavaScript)**:
  - Dynamic client-side line item addition/removal without page refresh.
  - Live price and stock availability lookup via asynchronous `fetch()`.
  - Real-time client calculations with strict backend validation.
  - Duplicate product rejection within the same order.
  - Historical rate snapshotting: item unit price is fixed upon order creation so future product price updates do not alter past orders.
  - Tiered discount validation (0% to 20%).
- **Strict Concurrency-Safe Inventory Control**:
  - Order state machine: `Draft` $\rightarrow$ `Confirmed` $\rightarrow$ `Cancelled`.
  - All-or-nothing stock availability check at the moment of confirmation.
  - Atomic inventory deduction during confirmation and inventory restoration during cancellation.
  - Idempotent confirmation/cancellation preventing duplicate deductions or restorations.
  - Concurrency safety using pessimistic row locking (`SELECT ... FOR UPDATE`) with sorted product IDs to eliminate deadlocks.
  - Complete stock audit trail (`StockMovement` table) tracking opening stock, order confirmations, order cancellations, and manual adjustments.
- **Bulk CSV Product Import**:
  - Admin-only bulk import with all-or-nothing transactional rollback.
  - Detailed row-by-row error reporting identifying exact line numbers and validation failures.
- **Business Reporting**:
  - Customer Sales Summary with custom date range filtering, 0-order customer inclusion, and multi-line deduplication.
  - Product Sales Summary (confirmed orders only, gross revenue before discount).
  - Low Stock Alert Report with customizable threshold.
  - Stock Movement History ledger with timestamps and audit reasons.
- **Authenticated REST APIs**:
  - Fully featured JSON API matching the web application's business rules and permissions.

---

## Technology Stack

- **Backend**: Python 3.13, Flask 3.x, Flask-SQLAlchemy 3.x, Werkzeug (Password Hashing)
- **Database**: MySQL / MariaDB (Port 3306, InnoDB Storage Engine)
- **Database Driver**: PyMySQL
- **Frontend**: Semantic HTML5, Custom Responsive CSS3, Vanilla JavaScript (ES6+ `fetch` API, no heavy frameworks)
- **Automated Testing**: Pytest 9.x (66 passing test cases covering all 9 mandatory scenarios)
- **Version Control**: Git (Feature branch workflow, meaningful atomic commits)

---

## System Architecture

The application adopts a clean, modular Model-View-Service-Controller (MVSC) architecture:

```text
tech_ass/
├── app/
│   ├── models/              # SQLAlchemy ORM entity models
│   │   ├── user.py          # User authentication and roles
│   │   ├── customer.py      # Customer master entity
│   │   ├── product.py       # Product master entity
│   │   ├── order.py         # SalesOrder and SalesOrderItem
│   │   └── stock_movement.py# Inventory audit ledger
│   ├── routes/              # Blueprint controllers handling HTTP requests
│   │   ├── auth.py          # Login, logout, session management
│   │   ├── customers.py     # Customer CRUD & safe deletion
│   │   ├── products.py      # Product CRUD, stock adjust & CSV import
│   │   ├── orders.py        # Order creation, edit, confirm & cancel
│   │   ├── reports.py       # Business analytics reports
│   │   └── api.py           # Authenticated REST API endpoints
│   ├── services/            # Pure business logic layer
│   │   ├── order_service.py # Financial calculations & concurrency-safe stock updates
│   │   ├── csv_service.py   # Bulk import parsing & validation
│   │   └── report_service.py# SQL aggregation queries & analytics
│   ├── static/              # Static assets
│   │   ├── css/style.css    # Clean, professional responsive UI
│   │   └── js/              # Vanilla JavaScript modules
│   │       ├── main.js      # Global UI interactions and modals
│   │       └── order_form.js# Dynamic order item table & live calculations
│   └── templates/           # Jinja2 HTML templates
├── debugging_exercise/      # Part 13 debugging exercise
│   └── calculate_total.py   # Bug-fixed, hardened calculation function
├── sample_data/             # Sample CSV files
│   ├── sample_valid.csv     # Valid product CSV file
│   └── sample_invalid.csv   # Invalid product CSV file (demonstrates rollback)
├── sql/
│   ├── schema.sql           # Complete DDL script for database creation
│   ├── seed_data.sql        # Seed script with users, products, customers
│   └── queries.sql          # 5 Standalone SQL analytical queries
├── tests/                   # Pytest automated test suite (66 tests)
├── .env.example             # Template environment variables
├── requirements.txt         # Pinned Python package dependencies
├── run.py                   # Application entry point
├── DEBUGGING.md             # Written analysis of debugging exercise
└── AI_USAGE.md              # Part 14 AI usage disclosure
```

---

## Database Design & Relationships

The database is built on MariaDB / MySQL using the **InnoDB** storage engine to support ACID transactions, row-level locks, and foreign key integrity.

### Entity Relationship Overview

1. **`users`**:
   - `id` (PK, INT AUTO_INCREMENT), `name`, `email` (UNIQUE), `password_hash`, `role` (`admin` | `sales_user`), `created_at`.
2. **`customers`**:
   - `id` (PK, INT AUTO_INCREMENT), `name`, `email`, `mobile`, `city`, `status` (`active` | `inactive`), `created_at`, `updated_at`.
   - Indexes on `name`, `email`, `mobile`, and `status`.
3. **`products`**:
   - `id` (PK, INT AUTO_INCREMENT), `product_code` (UNIQUE), `name`, `category`, `price` (`DECIMAL(10,2)`), `stock_quantity` (INT, CHECK $\ge 0$), `status` (`active` | `inactive`), `created_at`, `updated_at`.
   - Indexes on `product_code`, `name`, `category`, and `status`.
4. **`sales_orders`**:
   - `id` (PK, INT AUTO_INCREMENT), `order_number` (UNIQUE), `customer_id` (FK $\rightarrow$ `customers.id`), `user_id` (FK $\rightarrow$ `users.id`), `order_date`, `status` (`draft` | `confirmed` | `cancelled`), `discount_percentage` (`DECIMAL(5,2)`), `subtotal` (`DECIMAL(10,2)`), `discount_amount` (`DECIMAL(10,2)`), `grand_total` (`DECIMAL(10,2)`), `created_at`, `updated_at`.
5. **`sales_order_items`**:
   - `id` (PK, INT AUTO_INCREMENT), `sales_order_id` (FK $\rightarrow$ `sales_orders.id`), `product_id` (FK $\rightarrow$ `products.id`), `quantity` (INT), `rate` (`DECIMAL(10,2)`), `amount` (`DECIMAL(10,2)`).
   - Rate is frozen upon item creation as a historical price snapshot.
6. **`stock_movements`**:
   - `id` (PK, INT AUTO_INCREMENT), `product_id` (FK $\rightarrow$ `products.id`), `movement_type` (`OPENING_STOCK` | `ORDER_CONFIRM` | `ORDER_CANCEL` | `MANUAL_ADJUSTMENT`), `quantity_change` (INT, signed), `sales_order_id` (FK nullable $\rightarrow$ `sales_orders.id`), `reason` (VARCHAR), `created_by` (FK $\rightarrow$ `users.id`), `created_at`.

### Key Design Decisions
- **Monetary Precision**: All monetary values (`price`, `rate`, `amount`, `subtotal`, `grand_total`) are stored as `DECIMAL(10, 2)` and calculated in Python using `decimal.Decimal` with `ROUND_HALF_UP` to prevent IEEE 754 binary floating-point drift.
- **Safe Deletion Policy**: `ON DELETE RESTRICT` is enforced. In application logic, before deleting a customer or product, the system checks for referencing records in `sales_orders`, `sales_order_items`, and `stock_movements`. If found, the deletion is blocked with a clear warning explaining that the record should be deactivated instead of deleted.

---

## Concurrency & Inventory Consistency

Managing inventory across concurrent sales operations requires strict consistency guarantees. The application enforces this in `app/services/order_service.py`:

```
                       ┌────────────────────────────────────────┐
                       │ User requests Order Confirmation       │
                       └───────────────────┬────────────────────┘
                                           │
                                           ▼
                       ┌────────────────────────────────────────┐
                       │ Begin ACID Database Transaction        │
                       └───────────────────┬────────────────────┘
                                           │
                                           ▼
                       ┌────────────────────────────────────────┐
                       │ Fetch & Sort Product IDs Ascending     │
                       │ (Guarantees Deadlock Prevention)       │
                       └───────────────────┬────────────────────┘
                                           │
                                           ▼
                       ┌────────────────────────────────────────┐
                       │ Execute SELECT ... FOR UPDATE          │
                       │ (Acquires Exclusive Row-Level Locks)   │
                       └───────────────────┬────────────────────┘
                                           │
                     ┌─────────────────────┴─────────────────────┐
                     │                                           │
       [All Stock >= Ordered]                      [Any Stock < Ordered]
                     │                                           │
                     ▼                                           ▼
   ┌───────────────────────────────────┐       ┌───────────────────────────────────┐
   │ 1. Deduct stock from each product │       │ 1. Rollback Database Transaction  │
   │ 2. Insert StockMovement ledger    │       │ 2. Return HTTP 400 with details of│
   │ 3. Update Order status: Confirmed │       │    insufficient items             │
   │ 4. Commit Database Transaction    │       └───────────────────────────────────┘
   └───────────────────────────────────┘
```

1. **Deadlock Prevention via Canonical Ordering**:
   When multiple orders attempt to lock products A and B concurrently, one transaction locking A then B while another locks B then A would cause a deadlock. To eliminate this, the application sorts all product IDs in ascending numerical order (`sorted(product_ids)`) before querying with exclusive locks.
2. **Pessimistic Row-Level Locking (`SELECT ... FOR UPDATE`)**:
   During order confirmation, SQLAlchemy executes `query.with_for_update()` on the sorted product rows. This prevents any other concurrent transaction from reading or mutating those products' stock until the transaction finishes.
3. **All-or-Nothing Availability Validation**:
   If even one product in a multi-item order lacks sufficient stock, the entire confirmation fails, the transaction is rolled back, and stock remains unchanged.
4. **Idempotent State Machine**:
   - `Draft` $\rightarrow$ `Confirmed`: Stock deducted, movement recorded.
   - Calling confirm on an already `Confirmed` order returns a no-op success without re-deducting stock.
   - `Confirmed` $\rightarrow$ `Cancelled`: Stock restored, movement recorded.
   - Calling cancel on an already `Cancelled` order returns a no-op success without re-restoring stock.
   - `Draft` $\rightarrow$ `Cancelled`: Status changed; no stock changes occur because draft orders do not reserve stock.

---

## Prerequisites & Local Setup

### 1. Prerequisites
- **Python 3.10+** (Tested on Python 3.13)
- **MySQL / MariaDB** (e.g., via XAMPP or native service on port 3306)
- **Git**

### 2. Clone or Extract the Repository
```bash
cd D:\tech_ass
```

### 3. Create and Activate Virtual Environment
```bash
python -m venv venv

# Windows (PowerShell):
.\venv\Scripts\Activate.ps1

# Windows (Command Prompt):
.\venv\Scripts\activate.bat

# Linux / macOS:
source venv/bin/activate
```

### 4. Install Dependencies
```bash
pip install -r requirements.txt
```

### 5. Environment Configuration
Copy `.env.example` to `.env` and verify database settings:
```ini
FLASK_APP=run.py
FLASK_ENV=development
SECRET_KEY=savyant_inventory_secure_dev_key_2026
DATABASE_URL=mysql+pymysql://root:@localhost:3306/savyant_inventory_db
```

### 6. Database Initialization
Ensure your MySQL/MariaDB service is running on port 3306. Run the schema and seed scripts using the MySQL CLI or phpMyAdmin:

```bash
# Using MySQL Command Line Client (adjust path if needed):
mysql -u root -e "CREATE DATABASE IF NOT EXISTS savyant_inventory_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
mysql -u root savyant_inventory_db < sql/schema.sql
mysql -u root savyant_inventory_db < sql/seed_data.sql
```

### 7. Run the Application
```bash
python run.py
```
The application will start on: **`http://localhost:5000`**

---

## Default Sample Accounts

| Role | Email Address | Password | Permissions |
|:---|:---|:---|:---|
| **Admin** | `admin@savyant.com` | `Admin@123` | Full access to master data, stock adjustments, all orders, CSV import, and analytics reports. |
| **Sales User** | `sales@savyant.com` | `Sales@123` | Can view active products & customers; can create, manage, confirm, and cancel their own sales orders. |

---

## Automated Testing (Pytest)

The test suite contains **66 comprehensive automated test cases** covering every critical business rule and all 9 required testing scenarios from the specification.

### Running the Tests
```bash
# Run all tests with verbose output:
python -m pytest -v

# Run specific test modules:
python -m pytest tests/test_inventory.py -v   # Concurrency and stock tests
python -m pytest tests/test_orders.py -v      # Order calculation and IDOR tests
python -m pytest tests/test_csv_import.py -v  # CSV all-or-nothing import tests
python -m pytest tests/test_debugging.py -v   # Debugging exercise unit tests
```

### Mandatory Scenario Test Mapping

| # | Mandatory Scenario (PDF Page 13) | Test Function | Test File |
|:---:|:---|:---|:---|
| 1 | Order with multiple items and discount | `test_order_with_multiple_items_and_discount` | `tests/test_orders.py` |
| 2 | Zero or negative quantity rejected | `test_zero_or_negative_quantity_rejected` | `tests/test_orders.py` |
| 3 | Discount outside 0–20% rejected | `test_discount_outside_0_to_20_rejected` | `tests/test_orders.py` |
| 4 | Confirmation with sufficient stock | `test_confirmation_with_sufficient_stock` | `tests/test_inventory.py` |
| 5 | Confirmation with one insufficient-stock item | `test_confirmation_with_one_insufficient_stock_item` | `tests/test_inventory.py` |
| 6 | Repeated confirmation (idempotent) | `test_repeated_confirmation_does_not_deduct_stock_again` | `tests/test_inventory.py` |
| 7 | Cancellation of Confirmed order restores stock | `test_cancellation_of_confirmed_order_restores_stock_once` | `tests/test_inventory.py` |
| 8 | Sales User accesses another user's order (IDOR) | `test_sales_user_cannot_access_another_users_order` | `tests/test_orders.py` |
| 9 | CSV containing an invalid row imports nothing | `test_csv_containing_invalid_row_imports_nothing` | `tests/test_csv_import.py` |

---

## REST API Documentation

All API endpoints are prefixed with `/api/` and return standard JSON responses with appropriate HTTP status codes (`200 OK`, `201 Created`, `400 Bad Request`, `401 Unauthorized`, `403 Forbidden`, `404 Not Found`).

Authentication can be supplied via active session cookie (after logging in) or via **HTTP Basic Authentication** (`Authorization: Basic <base64(email:password)>`).

### 1. Authenticate / Login
- **Endpoint**: `POST /api/auth/login`
- **Request Body**:
  ```json
  {
    "email": "sales@savyant.com",
    "password": "Sales@123"
  }
  ```
- **Response (`200 OK`)**:
  ```json
  {
    "message": "Login successful.",
    "user": {
      "id": 2,
      "name": "Jane Smith",
      "email": "sales@savyant.com",
      "role": "sales_user"
    }
  }
  ```

### 2. List Products
- **Endpoint**: `GET /api/products?search=Keyboard&page=1&per_page=10`
- **Response (`200 OK`)**:
  ```json
  {
    "products": [
      {
        "id": 1,
        "product_code": "PRD-001",
        "name": "Mechanical Gaming Keyboard",
        "category": "Accessories",
        "price": "2499.00",
        "stock_quantity": 45,
        "status": "active"
      }
    ],
    "total": 1,
    "page": 1,
    "pages": 1
  }
  ```

### 3. Create Draft Sales Order
- **Endpoint**: `POST /api/orders`
- **Request Body**:
  ```json
  {
    "customer_id": 1,
    "discount_percentage": 10.0,
    "items": [
      {"product_id": 1, "quantity": 2},
      {"product_id": 2, "quantity": 3}
    ]
  }
  ```
- **Response (`201 Created`)**:
  ```json
  {
    "message": "Sales order created successfully as draft.",
    "order": {
      "id": 5,
      "order_number": "SO-20261118-0005",
      "customer_id": 1,
      "status": "draft",
      "subtotal": "6497.00",
      "discount_percentage": "10.00",
      "discount_amount": "649.70",
      "grand_total": "5847.30",
      "items": [
        {"product_id": 1, "product_name": "Mechanical Keyboard", "quantity": 2, "rate": "2499.00", "amount": "4998.00"},
        {"product_id": 2, "product_name": "Wireless Mouse", "quantity": 3, "rate": "499.00", "amount": "1497.00"}
      ]
    }
  }
  ```

### 4. Retrieve Order Details
- **Endpoint**: `GET /api/orders/5`
- **Response (`200 OK`)**: Returns complete order and line item breakdown.
- **Security**: Returns `403 Forbidden` if a Sales User attempts to view an order belonging to another sales representative.

### 5. Confirm Order & Deduct Stock
- **Endpoint**: `POST /api/orders/5/confirm`
- **Response (`200 OK`)**:
  ```json
  {
    "message": "Order SO-20261118-0005 confirmed successfully and stock deducted.",
    "status": "confirmed"
  }
  ```
- **Error (`400 Bad Request`)**: Returned if any item has insufficient stock:
  ```json
  {
    "error": "Insufficient stock for product 'Mechanical Keyboard'. Requested: 50, Available: 45."
  }
  ```

### 6. Cancel Order & Restore Stock
- **Endpoint**: `POST /api/orders/5/cancel`
- **Response (`200 OK`)**:
  ```json
  {
    "message": "Order SO-20261118-0005 cancelled successfully and stock restored.",
    "status": "cancelled"
  }
  ```

---

## Standalone SQL Queries

All five queries specified in Part 9 are provided in [`sql/queries.sql`](file:///d:/tech_ass/sql/queries.sql):

1. **Top three customers by Confirmed order grand total**:
   Aggregates sum of `grand_total` on `sales_orders` where `status = 'confirmed'` grouped by customer.
2. **Top three products by quantity sold in Confirmed orders**:
   Joins `sales_order_items`, `products`, and `sales_orders` filtering for `status = 'confirmed'`.
3. **Customers who have never placed any order**:
   Uses `LEFT JOIN sales_orders ON customers.id = sales_orders.customer_id WHERE sales_orders.id IS NULL`.
4. **Month-wise Confirmed sales totals, grouped by year and month**:
   Extracts `YEAR(order_date)` and `DATE_FORMAT(order_date, '%M')` on confirmed orders.
5. **Products below a supplied stock threshold**:
   Selects products where `stock_quantity < :threshold` ordered by stock ascending.

---

## Assumptions & Scope Limits

Per the official assignment specification:
1. **Single Currency & Single Stock Location**: All financial values are calculated in INR (`₹`) across a single central inventory warehouse.
2. **Whole Number Quantities**: Product stock and line item order quantities are strictly integers.
3. **Out of Scope**: Payment gateways, shipping logistics, tax/GST calculations, and purchase order supplier workflows were excluded per project guidelines.
4. **Reporting Scope**: Sales summary reports strictly reflect **Confirmed** orders. Draft or Cancelled orders are excluded from revenue totals.
