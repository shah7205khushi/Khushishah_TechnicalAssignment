import csv
import io
from decimal import Decimal, InvalidOperation
from app.extensions import db
from app.models.product import Product
from app.models.stock_movement import StockMovement

class CsvService:
    REQUIRED_COLUMNS = [
        'product_code',
        'product_name',
        'category',
        'price',
        'stock_quantity',
        'status'
    ]

    @staticmethod
    def parse_and_validate_csv(file_stream, user):
        """
        Parses and validates a CSV file for bulk product import.
        Requirements (PDF Part 10):
          - Validate required columns and each row.
          - Reject duplicate product codes within the file or already present in DB.
          - Reject invalid numeric values, negative values and invalid statuses.
          - Display row numbers and reasons for errors.
          - If any row is invalid, import nothing (all-or-nothing rollback).
          - Record imported opening stock as stock movements.
        """
        # Read text content safely handling potential UTF-8 BOM
        try:
            if isinstance(file_stream, str):
                content = file_stream
            elif hasattr(file_stream, 'read'):
                raw_bytes = file_stream.read()
                if isinstance(raw_bytes, str):
                    content = raw_bytes
                else:
                    content = raw_bytes.decode('utf-8-sig')
            else:
                return {'success': False, 'errors': [{'row': 0, 'reason': 'Invalid file object received.'}], 'imported_count': 0}
        except UnicodeDecodeError:
            return {'success': False, 'errors': [{'row': 0, 'reason': 'File must be UTF-8 encoded CSV text.'}], 'imported_count': 0}

        csv_file = io.StringIO(content.strip())
        reader = csv.reader(csv_file)

        # 1. Read and validate header row
        try:
            header_row = next(reader)
        except StopIteration:
            return {'success': False, 'errors': [{'row': 1, 'reason': 'The uploaded CSV file is empty.'}], 'imported_count': 0}

        # Normalize headers
        normalized_headers = [h.strip().lower() for h in header_row]
        missing_columns = [col for col in CsvService.REQUIRED_COLUMNS if col not in normalized_headers]

        if missing_columns:
            return {
                'success': False,
                'errors': [{
                    'row': 1,
                    'reason': f"Missing required column(s): {', '.join(missing_columns)}. Expected headers: {', '.join(CsvService.REQUIRED_COLUMNS)}"
                }],
                'imported_count': 0
            }

        # Map column index
        col_idx = {col: normalized_headers.index(col) for col in CsvService.REQUIRED_COLUMNS}

        # 2. Row-by-row validation
        errors = []
        parsed_rows = []
        seen_file_codes = {}

        # Fetch all existing product codes in DB for fast duplicate detection
        existing_db_codes = {
            p[0].upper(): p[0]
            for p in db.session.query(Product.product_code).all()
        }

        row_num = 1  # Header is row 1
        for row in reader:
            row_num += 1

            # Skip entirely empty trailing lines
            if not row or not any(cell.strip() for cell in row):
                continue

            # Ensure row has enough columns
            if len(row) < len(CsvService.REQUIRED_COLUMNS):
                errors.append({
                    'row': row_num,
                    'reason': f"Row has only {len(row)} columns; expected {len(CsvService.REQUIRED_COLUMNS)}."
                })
                continue

            product_code = row[col_idx['product_code']].strip().upper()
            product_name = row[col_idx['product_name']].strip()
            category = row[col_idx['category']].strip()
            price_raw = row[col_idx['price']].strip()
            stock_raw = row[col_idx['stock_quantity']].strip()
            status_raw = row[col_idx['status']].strip().lower()

            # A. Product Code Validation
            if not product_code:
                errors.append({'row': row_num, 'reason': 'product_code cannot be empty.'})
            else:
                # Duplicate in file
                if product_code in seen_file_codes:
                    first_row = seen_file_codes[product_code]
                    errors.append({
                        'row': row_num,
                        'reason': f"Duplicate product code '{product_code}' within the file (first defined at row {first_row})."
                    })
                else:
                    seen_file_codes[product_code] = row_num

                # Duplicate in database
                if product_code in existing_db_codes:
                    errors.append({
                        'row': row_num,
                        'reason': f"Product code '{product_code}' already exists in the database."
                    })

            # B. Product Name Validation
            if not product_name:
                errors.append({'row': row_num, 'reason': 'product_name cannot be empty.'})

            # C. Price Validation
            price = None
            try:
                price = Decimal(price_raw)
                if price < Decimal('0.00'):
                    errors.append({'row': row_num, 'reason': f"Price cannot be negative (received: '{price_raw}')."})
            except (InvalidOperation, ValueError):
                errors.append({'row': row_num, 'reason': f"Price must be a valid numeric value (received: '{price_raw}')."})

            # D. Stock Quantity Validation
            stock_quantity = None
            try:
                stock_quantity = int(stock_raw)
                if stock_quantity < 0:
                    errors.append({'row': row_num, 'reason': f"Stock quantity cannot be negative (received: '{stock_raw}')."})
            except ValueError:
                errors.append({'row': row_num, 'reason': f"Stock quantity must be a whole integer (received: '{stock_raw}')."})

            # E. Status Validation
            if status_raw not in ['active', 'inactive']:
                errors.append({
                    'row': row_num,
                    'reason': f"Invalid status '{status_raw}'. Must be either 'Active' or 'Inactive'."
                })

            if not errors or len([e for e in errors if e['row'] == row_num]) == 0:
                parsed_rows.append({
                    'product_code': product_code,
                    'name': product_name,
                    'category': category or None,
                    'price': price,
                    'stock_quantity': stock_quantity,
                    'status': status_raw
                })

        # 3. All-or-Nothing check: If ANY error occurred, import nothing!
        if errors:
            return {
                'success': False,
                'errors': errors,
                'imported_count': 0
            }

        if not parsed_rows:
            return {
                'success': False,
                'errors': [{'row': 1, 'reason': 'No data rows found in CSV file.'}],
                'imported_count': 0
            }

        # 4. Perform atomic import inside single database transaction
        try:
            for item in parsed_rows:
                product = Product(
                    product_code=item['product_code'],
                    name=item['name'],
                    category=item['category'],
                    price=item['price'],
                    stock_quantity=item['stock_quantity'],
                    status=item['status']
                )
                db.session.add(product)
                db.session.flush()

                # Record opening stock movement if stock > 0
                if item['stock_quantity'] > 0:
                    movement = StockMovement(
                        product_id=product.id,
                        movement_type=StockMovement.TYPE_OPENING,
                        quantity_change=item['stock_quantity'],
                        reason='Initial opening stock imported from CSV',
                        created_by=user.id
                    )
                    db.session.add(movement)

            db.session.commit()
            return {
                'success': True,
                'errors': [],
                'imported_count': len(parsed_rows)
            }

        except Exception as e:
            db.session.rollback()
            return {
                'success': False,
                'errors': [{'row': 0, 'reason': f"Database transaction failed: {str(e)}"}],
                'imported_count': 0
            }
