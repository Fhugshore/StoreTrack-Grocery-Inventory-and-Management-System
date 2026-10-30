# StoreTrack Desktop

StoreTrack is an offline Windows desktop application prototype for a grocery store. It is **not web-based**: it opens as a normal desktop window and stores data locally in a SQLite database (`storetrack.db`) beside the program.

## Features
- Login and admin/staff roles
- Inventory: SKU, product name, category, quantity, minimum stock, cost, selling price, expiration date, supplier
- Low-stock and expiration monitoring on the dashboard
- Sales cart, customer name, payment method, automatic stock deduction
- Supplier purchase records, delivery receipt, stock additions, discrepancy notes
- Reports and CSV exports for sales, inventory, and purchases
- User account creation and activation/deactivation (admin only)

## Requirements
- Windows 10/11
- Python 3.10 or later, with Tkinter (the standard Windows Python installer includes it)
- No internet connection or extra Python packages are required

## Run it
1. Install Python from https://www.python.org/downloads/windows/ if needed. During installation, enable **Add python.exe to PATH**.
2. Extract this folder to a writable location, such as Documents.
3. Double-click `run_storetrack.bat`.

Alternatively, open Command Prompt in this folder and run:
```bat
python storetrack.py
```

## First login
- Username: `admin`
- Password: `admin123`

**Security:** Log in, open Users, create a new administrator account with a strong password, then deactivate the default `admin` account. This is a starter prototype; it does not currently include a built-in password-change screen.

## Data and backups
- All records are stored in `storetrack.db` next to `storetrack.py`.
- Back up the database by closing StoreTrack and copying `storetrack.db` to a safe location.
- CSV exports are written to the same folder.

## Important prototype notes
- This is a functional starter system, not a fully audited production POS.
- Test workflows with sample data before using it for real transactions.
- The app uses Philippine pesos (₱) in the interface.
- Purchase records with status `Received - unpaid` or `Paid` add stock immediately. Use the “Mark selected delivery received” button for orders that are still `Ordered` or `Received - inspect` to avoid adding stock twice.
- Use a consistent SKU for every product.
