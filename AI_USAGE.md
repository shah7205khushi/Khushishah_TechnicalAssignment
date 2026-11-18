# AI Usage Disclosure (Part 14)

This document provides transparent disclosure regarding the use of AI tools during the development of the Savyant Systems Sales Order & Inventory Management Technical Assessment, in compliance with **Part 14: AI-Assisted Development**.

---

## 1. Tools Used
- **Primary Tool**: Google Antigravity / Gemini 2.5 Pro (via pair-programming agent environment).

---

## 2. Tasks Where AI Provided Assistance

AI assistance was utilized across the following engineering tasks:
1. **Initial Project Scaffolding**: Structuring the modular Flask application into distinct directories (`models`, `routes`, `services`, `static`, `templates`, and `tests`) following the Model-View-Service-Controller pattern.
2. **Database Schema Design**: Converting the entity relationship requirements into clean SQLAlchemy models and verifying DDL constraints (`DECIMAL(10, 2)` monetary columns, unique indexes, and non-negative stock quantity checks).
3. **Concurrency & Deadlock Prevention Strategy**: Designing the pessimistic row-level locking mechanism (`SELECT ... FOR UPDATE` with product IDs sorted in ascending order) to guarantee deadlock-free, race-condition-free inventory updates.
4. **Pytest Suite Generation**: Assisting in creating comprehensive test cases covering edge cases, especially multi-threaded concurrent order confirmation, safe deletion constraints, IDOR security boundaries, and all-or-nothing CSV rollbacks.
5. **Debugging Exercise & Edge Case Analysis**: Identifying the reassignment accumulator bug in `calculate_total` and constructing edge-case test matrices.

---

## 3. Representative Prompts

Below are three representative prompts used during development:

### Prompt 1 (Concurrency & Inventory Consistency)
> *"Design the order confirmation logic in Flask-SQLAlchemy so that if two users attempt to confirm orders for the same limited inventory simultaneously, the stock never drops below zero and no deadlock occurs if both orders involve multiple overlapping products. Show the row-locking and transaction rollback approach."*

### Prompt 2 (Safe Deletion & Master Data Protection)
> *"Implement safe deletion checks for Customer and Product entities. If a product is referenced in any sales order items or has stock movement ledger records, prevent hard deletion, flash a clear warning directing the user to deactivate the product instead, and return an appropriate HTTP status code."*

### Prompt 3 (All-or-Nothing CSV Import with Row Errors)
> *"Create a CSV import service for products in Flask. It must validate all rows before inserting anything. If any row contains duplicate codes, invalid numbers, negative prices, or missing headers, reject the entire file with all-or-nothing rollback and return a detailed list of row numbers paired with their specific validation error reasons."*

---

## 4. How Generated Code Was Checked & Reviewed

All code generated or suggested by AI was subjected to strict verification before being committed:
1. **Automated Unit & Integration Testing**:
   - A 66-test Pytest suite was executed repeatedly across every feature. Tests specifically validated business logic boundaries, error cases, and database rollbacks.
2. **Manual MySQL Database State Verification**:
   - Every transactional flow (order confirmation, cancellation, manual stock adjustment, CSV import) was cross-checked directly in MariaDB / MySQL using raw queries to verify table rows, signed quantities in `stock_movements`, and stock balance accuracy.
3. **Security & Permission Auditing**:
   - IDOR vulnerabilities were tested by attempting cross-user order URL manipulation (`GET /orders/<id>`, `POST /orders/<id>/confirm`, `POST /orders/<id>/cancel`) as a Sales User.
4. **Interactive Manual Browser Walkthrough**:
   - The UI was tested in the browser: adding/removing dynamic order lines, checking live stock/price lookups, testing duplicate product prevention, and triggering invalid CSV imports.

---

## 5. Issues & Limitations Identified and Corrected

During the verification and code review phases, several issues were caught and corrected:

1. **Deadlock Vulnerability in Multi-Product Concurrent Orders**:
   - *Issue*: Initially, products were fetched and locked in arbitrary order as received from the form. If Order 1 locked Product A then Product B, while Order 2 locked Product B then Product A, MySQL could throw a deadlock error (`OperationalError: 1213`).
   - *Correction*: Sorted product IDs numerically (`sorted(product_ids)`) prior to acquiring `with_for_update()` locks, guaranteeing consistent acquisition order across all concurrent transactions.

2. **Exception Masking in Quantity Validation**:
   - *Issue*: A type conversion `try...except (ValueError, TypeError)` block caught negative quantity errors (`qty <= 0`) and collapsed them into a generic "Quantity must be a valid number" message instead of distinguishing negative quantities.
   - *Correction*: Separated the data type parse from value domain validation so clear messages like "Quantity must be greater than zero" are returned.

3. **Session State Bleeding in Test Client**:
   - *Issue*: In automated testing, an IDOR permission test failed because the Flask test client retained the Admin session cookie from a preceding test step.
   - *Correction*: Explicitly called `client.get('/logout')` before logging in as a second user, ensuring session isolation across test assertions.

4. **Product Sales Summary Aggregating Unconfirmed Orders**:
   - *Issue*: The initial reporting SQL query used a `LEFT JOIN` on `sales_orders` and summed `quantity`, inadvertently counting items from draft orders.
   - *Correction*: Refactored the SQL aggregation using `CASE WHEN sales_orders.status = 'confirmed' THEN quantity ELSE 0 END` to strictly adhere to the requirement that sales reports include confirmed orders only.
