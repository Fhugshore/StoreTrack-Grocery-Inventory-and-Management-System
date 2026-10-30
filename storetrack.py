import sqlite3
import hashlib
import secrets
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, date
from pathlib import Path
import csv

APP_NAME = "StoreTrack"
DB_PATH = Path(__file__).with_name("storetrack.db")

def hash_password(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 180_000).hex()
    return salt, digest

def verify_password(password, salt, expected):
    return hash_password(password, salt)[1] == expected

class StoreTrackDB:
    def __init__(self, path=DB_PATH):
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.setup()

    def setup(self):
        c = self.conn.cursor()
        c.executescript("""
        CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL,
            salt TEXT NOT NULL, password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'Staff', active INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS products(
            id INTEGER PRIMARY KEY, sku TEXT UNIQUE NOT NULL, name TEXT NOT NULL,
            category TEXT DEFAULT '', quantity INTEGER NOT NULL DEFAULT 0,
            min_quantity INTEGER NOT NULL DEFAULT 5, cost REAL NOT NULL DEFAULT 0,
            price REAL NOT NULL DEFAULT 0, expiration TEXT DEFAULT '',
            supplier TEXT DEFAULT '', updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS sales(
            id INTEGER PRIMARY KEY, sold_at TEXT NOT NULL, customer TEXT DEFAULT '',
            total REAL NOT NULL, payment_method TEXT DEFAULT 'Cash', user_id INTEGER,
            FOREIGN KEY(user_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS sale_items(
            id INTEGER PRIMARY KEY, sale_id INTEGER NOT NULL, product_id INTEGER NOT NULL,
            product_name TEXT NOT NULL, quantity INTEGER NOT NULL, unit_price REAL NOT NULL,
            line_total REAL NOT NULL,
            FOREIGN KEY(sale_id) REFERENCES sales(id),
            FOREIGN KEY(product_id) REFERENCES products(id)
        );
        CREATE TABLE IF NOT EXISTS purchases(
            id INTEGER PRIMARY KEY, ordered_at TEXT NOT NULL, supplier TEXT NOT NULL,
            product_id INTEGER, product_name TEXT NOT NULL, quantity INTEGER NOT NULL,
            unit_cost REAL NOT NULL, status TEXT NOT NULL DEFAULT 'Ordered',
            notes TEXT DEFAULT '', user_id INTEGER,
            FOREIGN KEY(product_id) REFERENCES products(id),
            FOREIGN KEY(user_id) REFERENCES users(id)
        );
        """)
        self.conn.commit()
        if not self.conn.execute("SELECT 1 FROM users LIMIT 1").fetchone():
            salt, digest = hash_password("admin123")
            self.conn.execute("INSERT INTO users(username,salt,password_hash,role) VALUES(?,?,?,'Admin')",
                              ("admin", salt, digest))
            self.conn.commit()

    def rows(self, sql, params=()):
        return self.conn.execute(sql, params).fetchall()

    def one(self, sql, params=()):
        return self.conn.execute(sql, params).fetchone()

    def run(self, sql, params=()):
        cur = self.conn.execute(sql, params)
        self.conn.commit()
        return cur

    def close(self):
        self.conn.close()

class StoreTrackApp:
    def __init__(self, root):
        self.root = root
        self.db = StoreTrackDB()
        self.user = None
        self.cart = []
        self.root.title(APP_NAME + " — Grocery Store Inventory and Management")
        self.root.geometry("1180x740")
        self.root.minsize(980, 620)
        self.style = ttk.Style()
        try:
            self.style.theme_use("clam")
        except tk.TclError:
            pass
        self.style.configure("Treeview", rowheight=27)
        self.style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"))
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.show_login()

    def clear(self):
        for child in self.root.winfo_children():
            child.destroy()

    def show_login(self):
        self.clear()
        frame = ttk.Frame(self.root, padding=36)
        frame.place(relx=.5, rely=.48, anchor="center")
        ttk.Label(frame, text="StoreTrack", font=("Segoe UI", 26, "bold")).grid(row=0, column=0, columnspan=2, pady=(0, 4))
        ttk.Label(frame, text="Grocery Store Inventory and Management System").grid(row=1, column=0, columnspan=2, pady=(0, 24))
        ttk.Label(frame, text="Username").grid(row=2, column=0, sticky="w", pady=6)
        self.login_user = ttk.Entry(frame, width=30)
        self.login_user.grid(row=2, column=1, pady=6)
        ttk.Label(frame, text="Password").grid(row=3, column=0, sticky="w", pady=6)
        self.login_pass = ttk.Entry(frame, width=30, show="•")
        self.login_pass.grid(row=3, column=1, pady=6)
        ttk.Button(frame, text="Log in", command=self.login).grid(row=4, column=0, columnspan=2, sticky="ew", pady=(16, 8))
        ttk.Label(frame, text="First-run login: admin  |  password: admin123", foreground="#666").grid(row=5, column=0, columnspan=2)
        self.login_pass.bind("<Return>", lambda e: self.login())
        self.login_user.focus_set()

    def login(self):
        username = self.login_user.get().strip()
        password = self.login_pass.get()
        user = self.db.one("SELECT * FROM users WHERE username=? AND active=1", (username,))
        if user and verify_password(password, user["salt"], user["password_hash"]):
            self.user = user
            self.show_main()
        else:
            messagebox.showerror("Login failed", "Incorrect username or password, or the account is inactive.")

    def show_main(self):
        self.clear()
        top = ttk.Frame(self.root, padding=(14, 10))
        top.pack(fill="x")
        ttk.Label(top, text="StoreTrack", font=("Segoe UI", 19, "bold")).pack(side="left")
        ttk.Label(top, text=f"Signed in: {self.user['username']} ({self.user['role']})").pack(side="right", padx=8)
        ttk.Button(top, text="Log out", command=self.logout).pack(side="right")
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self.dashboard_tab = ttk.Frame(self.notebook, padding=12)
        self.inventory_tab = ttk.Frame(self.notebook, padding=12)
        self.sales_tab = ttk.Frame(self.notebook, padding=12)
        self.purchases_tab = ttk.Frame(self.notebook, padding=12)
        self.reports_tab = ttk.Frame(self.notebook, padding=12)
        self.users_tab = ttk.Frame(self.notebook, padding=12)
        for tab, title in [(self.dashboard_tab, "Dashboard"), (self.inventory_tab, "Inventory"),
                           (self.sales_tab, "Sales"), (self.purchases_tab, "Supplier & Purchasing"),
                           (self.reports_tab, "Reports"), (self.users_tab, "Users")]:
            self.notebook.add(tab, text=title)
        self.build_dashboard()
        self.build_inventory()
        self.build_sales()
        self.build_purchases()
        self.build_reports()
        self.build_users()
        if self.user["role"] != "Admin":
            self.notebook.tab(self.users_tab, state="disabled")

    def logout(self):
        self.user = None
        self.cart = []
        self.show_login()

    def build_dashboard(self):
        f = self.dashboard_tab
        ttk.Label(f, text="Overview", font=("Segoe UI", 17, "bold")).pack(anchor="w", pady=(0, 12))
        cards = ttk.Frame(f)
        cards.pack(fill="x")
        self.stat_labels = {}
        for key, title in [("products","Products"),("stock","Units in stock"),("low","Low-stock items"),("sales","Sales today"),("payables","Open purchases")]:
            card = ttk.LabelFrame(cards, text=title, padding=16)
            card.pack(side="left", fill="both", expand=True, padx=(0, 8))
            label = ttk.Label(card, text="—", font=("Segoe UI", 18, "bold"))
            label.pack()
            self.stat_labels[key] = label
        ttk.Label(f, text="Low-stock / expiring items", font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(24, 8))
        self.alert_tree = self.make_tree(f, [("sku","SKU",100),("name","Product",260),("quantity","Qty",80),("min_quantity","Minimum",90),("expiration","Expiration",120),("alert","Alert",180)])
        ttk.Button(f, text="Refresh dashboard", command=self.refresh_dashboard).pack(anchor="e", pady=8)
        self.refresh_dashboard()

    def refresh_dashboard(self):
        if not hasattr(self, "stat_labels"): return
        today = date.today().isoformat()
        values = {
            "products": self.db.one("SELECT COUNT(*) n FROM products")["n"],
            "stock": self.db.one("SELECT COALESCE(SUM(quantity),0) n FROM products")["n"],
            "low": self.db.one("SELECT COUNT(*) n FROM products WHERE quantity<=min_quantity")["n"],
            "sales": self.db.one("SELECT COALESCE(SUM(total),0) n FROM sales WHERE substr(sold_at,1,10)=?", (today,))["n"],
            "payables": self.db.one("SELECT COUNT(*) n FROM purchases WHERE status IN ('Ordered','Received - unpaid')")["n"]
        }
        for k, v in values.items():
            self.stat_labels[k].configure(text=f"₱{v:,.2f}" if k == "sales" else str(v))
        self.fill_tree(self.alert_tree, [])
        rows = self.db.rows("SELECT *, CASE WHEN quantity<=min_quantity THEN 'LOW STOCK' ELSE 'EXPIRING SOON' END alert FROM products WHERE quantity<=min_quantity OR (expiration<>'' AND expiration<=?) ORDER BY quantity ASC", ((date.today().replace(day=1)).isoformat(),))
        for r in rows:
            self.alert_tree.insert("", "end", values=(r["sku"],r["name"],r["quantity"],r["min_quantity"],r["expiration"],"LOW STOCK" if r["quantity"]<=r["min_quantity"] else "CHECK EXPIRATION"))

    def make_tree(self, parent, columns):
        wrap = ttk.Frame(parent)
        wrap.pack(fill="both", expand=True)
        ids = [c[0] for c in columns]
        tree = ttk.Treeview(wrap, columns=ids, show="headings")
        for cid, title, width in columns:
            tree.heading(cid, text=title)
            tree.column(cid, width=width, minwidth=50, anchor="w")
        vs = ttk.Scrollbar(wrap, orient="vertical", command=tree.yview)
        hs = ttk.Scrollbar(wrap, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=vs.set, xscrollcommand=hs.set)
        tree.grid(row=0, column=0, sticky="nsew")
        vs.grid(row=0, column=1, sticky="ns")
        hs.grid(row=1, column=0, sticky="ew")
        wrap.rowconfigure(0, weight=1); wrap.columnconfigure(0, weight=1)
        return tree

    def fill_tree(self, tree, rows):
        for item in tree.get_children(): tree.delete(item)
        for row in rows:
            tree.insert("", "end", values=tuple(row))

    def build_inventory(self):
        f = self.inventory_tab
        bar = ttk.Frame(f); bar.pack(fill="x", pady=(0, 10))
        ttk.Label(bar, text="Product inventory", font=("Segoe UI", 15, "bold")).pack(side="left")
        ttk.Button(bar, text="Add product", command=self.product_dialog).pack(side="right", padx=4)
        ttk.Button(bar, text="Edit selected", command=self.edit_product).pack(side="right", padx=4)
        ttk.Button(bar, text="Delete selected", command=self.delete_product).pack(side="right", padx=4)
        searchbar = ttk.Frame(f); searchbar.pack(fill="x", pady=(0, 8))
        ttk.Label(searchbar, text="Search SKU / name / category").pack(side="left")
        self.inv_search = tk.StringVar()
        ent = ttk.Entry(searchbar, textvariable=self.inv_search, width=35); ent.pack(side="left", padx=8)
        ent.bind("<KeyRelease>", lambda e: self.refresh_inventory())
        ttk.Button(searchbar, text="Refresh", command=self.refresh_inventory).pack(side="left")
        self.inventory_tree = self.make_tree(f, [("id","ID",45),("sku","SKU",100),("name","Product",210),("category","Category",120),("quantity","Qty",60),("min_quantity","Min Qty",75),("cost","Cost",90),("price","Price",90),("expiration","Expiration",105),("supplier","Supplier",150)])
        self.refresh_inventory()

    def refresh_inventory(self):
        if not hasattr(self, "inventory_tree"): return
        q = f"%{self.inv_search.get().strip()}%"
        rows = self.db.rows("SELECT id,sku,name,category,quantity,min_quantity,cost,price,expiration,supplier FROM products WHERE sku LIKE ? OR name LIKE ? OR category LIKE ? ORDER BY name", (q,q,q))
        self.fill_tree(self.inventory_tree, [(r["id"],r["sku"],r["name"],r["category"],r["quantity"],r["min_quantity"],f'{r["cost"]:.2f}',f'{r["price"]:.2f}',r["expiration"],r["supplier"]) for r in rows])

    def selected_id(self, tree):
        sel = tree.selection()
        if not sel:
            messagebox.showinfo("Select a row", "Please select a row first.")
            return None
        return int(tree.item(sel[0], "values")[0])

    def product_dialog(self, product_id=None):
        old = self.db.one("SELECT * FROM products WHERE id=?", (product_id,)) if product_id else None
        win = tk.Toplevel(self.root); win.title("Edit product" if old else "Add product"); win.transient(self.root); win.grab_set()
        fields = [("SKU","sku"),("Product name","name"),("Category","category"),("Quantity","quantity"),("Minimum quantity","min_quantity"),("Unit cost (₱)","cost"),("Selling price (₱)","price"),("Expiration (YYYY-MM-DD)","expiration"),("Supplier","supplier")]
        vars_ = {}
        for i,(label,key) in enumerate(fields):
            ttk.Label(win,text=label).grid(row=i,column=0,sticky="w",padx=12,pady=5)
            v=tk.StringVar(value=str(old[key] if old and old[key] is not None else (0 if key in ("quantity","min_quantity","cost","price") else "")))
            vars_[key]=v; ttk.Entry(win,textvariable=v,width=34).grid(row=i,column=1,padx=12,pady=5)
        def save():
            try:
                sku=vars_["sku"].get().strip(); name=vars_["name"].get().strip()
                if not sku or not name: raise ValueError("SKU and product name are required.")
                qty=int(vars_["quantity"].get()); minimum=int(vars_["min_quantity"].get())
                cost=float(vars_["cost"].get()); price=float(vars_["price"].get())
                if qty<0 or minimum<0 or cost<0 or price<0: raise ValueError("Quantity and prices cannot be negative.")
                exp=vars_["expiration"].get().strip()
                if exp: datetime.strptime(exp,"%Y-%m-%d")
                data=(sku,name,vars_["category"].get().strip(),qty,minimum,cost,price,exp,vars_["supplier"].get().strip(),datetime.now().isoformat(timespec="seconds"))
                if old:
                    self.db.run("UPDATE products SET sku=?,name=?,category=?,quantity=?,min_quantity=?,cost=?,price=?,expiration=?,supplier=?,updated_at=? WHERE id=?", data+(product_id,))
                else:
                    self.db.run("INSERT INTO products(sku,name,category,quantity,min_quantity,cost,price,expiration,supplier,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)",data)
                self.refresh_inventory(); self.refresh_dashboard(); win.destroy()
            except sqlite3.IntegrityError:
                messagebox.showerror("Duplicate SKU","That SKU already exists.",parent=win)
            except (ValueError, TypeError) as e:
                messagebox.showerror("Invalid product",str(e),parent=win)
        ttk.Button(win,text="Save product",command=save).grid(row=len(fields),column=0,columnspan=2,pady=12)

    def edit_product(self):
        pid=self.selected_id(self.inventory_tree)
        if pid is not None: self.product_dialog(pid)

    def delete_product(self):
        pid=self.selected_id(self.inventory_tree)
        if pid is None: return
        if not messagebox.askyesno("Confirm delete","Delete this product? Products used in sales or purchases cannot be deleted."): return
        try:
            self.db.run("DELETE FROM products WHERE id=?",(pid,))
            self.refresh_inventory(); self.refresh_dashboard()
        except sqlite3.IntegrityError:
            messagebox.showerror("Cannot delete","This product has sales or purchase history. Keep it for audit purposes.")

    def build_sales(self):
        f=self.sales_tab
        ttk.Label(f,text="Record customer purchase",font=("Segoe UI",15,"bold")).pack(anchor="w",pady=(0,8))
        form=ttk.Frame(f); form.pack(fill="x")
        ttk.Label(form,text="Customer (optional)").grid(row=0,column=0,sticky="w",padx=4,pady=4)
        self.customer_var=tk.StringVar()
        ttk.Entry(form,textvariable=self.customer_var,width=28).grid(row=0,column=1,padx=4,pady=4)
        ttk.Label(form,text="Payment").grid(row=0,column=2,padx=4)
        self.payment_var=tk.StringVar(value="Cash")
        ttk.Combobox(form,textvariable=self.payment_var,values=["Cash","GCash","Card","Bank transfer","Other"],state="readonly",width=18).grid(row=0,column=3,padx=4)
        ttk.Label(form,text="Product").grid(row=1,column=0,sticky="w",padx=4,pady=4)
        self.sale_product_var=tk.StringVar()
        self.sale_product_combo=ttk.Combobox(form,textvariable=self.sale_product_var,state="readonly",width=42)
        self.sale_product_combo.grid(row=1,column=1,padx=4,pady=4)
        ttk.Label(form,text="Qty").grid(row=1,column=2,padx=4)
        self.sale_qty_var=tk.StringVar(value="1")
        ttk.Entry(form,textvariable=self.sale_qty_var,width=8).grid(row=1,column=3,padx=4)
        ttk.Button(form,text="Add to sale",command=self.add_to_cart).grid(row=1,column=4,padx=8)
        self.cart_tree=self.make_tree(f,[("sku","SKU",100),("name","Product",300),("qty","Qty",80),("price","Unit price",120),("total","Line total",130)])
        bottom=ttk.Frame(f); bottom.pack(fill="x",pady=8)
        self.cart_total_label=ttk.Label(bottom,text="Total: ₱0.00",font=("Segoe UI",14,"bold")); self.cart_total_label.pack(side="left")
        ttk.Button(bottom,text="Remove selected",command=self.remove_cart_item).pack(side="right",padx=4)
        ttk.Button(bottom,text="Complete sale",command=self.complete_sale).pack(side="right",padx=4)
        self.refresh_sale_products()

    def refresh_sale_products(self):
        if not hasattr(self,"sale_product_combo"): return
        self.product_choices={}
        rows=self.db.rows("SELECT id,sku,name,quantity,price FROM products ORDER BY name")
        vals=[]
        for r in rows:
            label=f'{r["sku"]} — {r["name"]} (stock: {r["quantity"]}, ₱{r["price"]:.2f})'
            vals.append(label); self.product_choices[label]=dict(r)
        self.sale_product_combo["values"]=vals
        if vals and not self.sale_product_var.get(): self.sale_product_var.set(vals[0])

    def add_to_cart(self):
        label=self.sale_product_var.get()
        if label not in self.product_choices: messagebox.showwarning("Choose product","Add products to inventory first."); return
        try: qty=int(self.sale_qty_var.get())
        except ValueError: messagebox.showerror("Invalid quantity","Quantity must be a whole number."); return
        p=self.product_choices[label]
        if qty<=0: messagebox.showerror("Invalid quantity","Quantity must be greater than zero."); return
        already=sum(x["qty"] for x in self.cart if x["id"]==p["id"])
        if already+qty>p["quantity"]: messagebox.showerror("Insufficient stock",f'Only {p["quantity"]} unit(s) available.'); return
        found=next((x for x in self.cart if x["id"]==p["id"]),None)
        if found: found["qty"]+=qty
        else: self.cart.append({"id":p["id"],"sku":p["sku"],"name":p["name"],"qty":qty,"price":p["price"]})
        self.refresh_cart()

    def refresh_cart(self):
        self.fill_tree(self.cart_tree,[(x["sku"],x["name"],x["qty"],f'₱{x["price"]:.2f}',f'₱{x["qty"]*x["price"]:.2f}') for x in self.cart])
        self.cart_total_label.configure(text=f'Total: ₱{sum(x["qty"]*x["price"] for x in self.cart):,.2f}')

    def remove_cart_item(self):
        sel=self.cart_tree.selection()
        if not sel: return
        idx=self.cart_tree.index(sel[0])
        if 0<=idx<len(self.cart): self.cart.pop(idx)
        self.refresh_cart()

    def complete_sale(self):
        if not self.cart: messagebox.showinfo("Empty sale","Add at least one item."); return
        total=round(sum(x["qty"]*x["price"] for x in self.cart),2)
        try:
            self.db.conn.execute("BEGIN")
            cur=self.db.conn.execute("INSERT INTO sales(sold_at,customer,total,payment_method,user_id) VALUES(?,?,?,?,?)",
                    (datetime.now().isoformat(timespec="seconds"),self.customer_var.get().strip(),total,self.payment_var.get(),self.user["id"]))
            sale_id=cur.lastrowid
            for x in self.cart:
                p=self.db.conn.execute("SELECT quantity FROM products WHERE id=?",(x["id"],)).fetchone()
                if not p or p["quantity"]<x["qty"]: raise ValueError(f'Insufficient stock for {x["name"]}.')
                self.db.conn.execute("INSERT INTO sale_items(sale_id,product_id,product_name,quantity,unit_price,line_total) VALUES(?,?,?,?,?,?)",
                    (sale_id,x["id"],x["name"],x["qty"],x["price"],round(x["qty"]*x["price"],2)))
                self.db.conn.execute("UPDATE products SET quantity=quantity-?,updated_at=? WHERE id=?",(x["qty"],datetime.now().isoformat(timespec="seconds"),x["id"]))
            self.db.conn.commit()
        except Exception as e:
            self.db.conn.rollback(); messagebox.showerror("Sale failed",str(e)); return
        messagebox.showinfo("Sale complete",f"Sale #{sale_id} recorded.\nTotal: ₱{total:,.2f}")
        self.cart=[]; self.customer_var.set(""); self.refresh_cart(); self.refresh_inventory(); self.refresh_sale_products(); self.refresh_dashboard(); self.refresh_reports()

    def build_purchases(self):
        f=self.purchases_tab
        ttk.Label(f,text="Supplier and purchase orders",font=("Segoe UI",15,"bold")).pack(anchor="w",pady=(0,8))
        form=ttk.LabelFrame(f,text="Record purchase order / delivery",padding=10); form.pack(fill="x",pady=(0,10))
        self.po_supplier=tk.StringVar(); self.po_product=tk.StringVar(); self.po_qty=tk.StringVar(value="1"); self.po_cost=tk.StringVar(value="0.00"); self.po_status=tk.StringVar(value="Ordered"); self.po_notes=tk.StringVar()
        ttk.Label(form,text="Supplier").grid(row=0,column=0,sticky="w",padx=4,pady=4); ttk.Entry(form,textvariable=self.po_supplier,width=22).grid(row=0,column=1,padx=4,pady=4)
        ttk.Label(form,text="Product").grid(row=0,column=2,sticky="w",padx=4,pady=4); self.po_combo=ttk.Combobox(form,textvariable=self.po_product,state="readonly",width=30); self.po_combo.grid(row=0,column=3,padx=4,pady=4)
        ttk.Label(form,text="Quantity").grid(row=1,column=0,sticky="w",padx=4,pady=4); ttk.Entry(form,textvariable=self.po_qty,width=12).grid(row=1,column=1,padx=4,pady=4,sticky="w")
        ttk.Label(form,text="Unit cost (₱)").grid(row=1,column=2,sticky="w",padx=4,pady=4); ttk.Entry(form,textvariable=self.po_cost,width=14).grid(row=1,column=3,padx=4,pady=4,sticky="w")
        ttk.Label(form,text="Status").grid(row=2,column=0,sticky="w",padx=4,pady=4); ttk.Combobox(form,textvariable=self.po_status,values=["Ordered","Received - inspect","Received - unpaid","Paid","Discrepancy / damaged"],state="readonly",width=20).grid(row=2,column=1,padx=4,pady=4)
        ttk.Label(form,text="Notes / discrepancies").grid(row=2,column=2,sticky="w",padx=4,pady=4); ttk.Entry(form,textvariable=self.po_notes,width=32).grid(row=2,column=3,padx=4,pady=4)
        ttk.Button(form,text="Save purchase record",command=self.save_purchase).grid(row=3,column=0,columnspan=4,pady=8)
        self.purchase_tree=self.make_tree(f,[("id","ID",50),("date","Date",145),("supplier","Supplier",150),("product","Product",210),("qty","Qty",60),("cost","Unit cost",100),("status","Status",170),("notes","Notes",220)])
        ttk.Button(f,text="Mark selected delivery received (adds stock)",command=self.receive_purchase).pack(anchor="e",pady=8)
        self.refresh_purchase_products(); self.refresh_purchases()

    def refresh_purchase_products(self):
        if not hasattr(self,"po_combo"): return
        self.po_choices={}
        vals=[]
        for r in self.db.rows("SELECT id,sku,name,cost FROM products ORDER BY name"):
            label=f'{r["sku"]} — {r["name"]}'
            vals.append(label); self.po_choices[label]=dict(r)
        self.po_combo["values"]=vals
        if vals and not self.po_product.get(): self.po_product.set(vals[0])

    def save_purchase(self):
        supplier=self.po_supplier.get().strip(); label=self.po_product.get()
        if not supplier: messagebox.showerror("Missing supplier","Enter a supplier name."); return
        if label not in self.po_choices: messagebox.showerror("Missing product","Add/select a product first."); return
        try:
            qty=int(self.po_qty.get()); cost=float(self.po_cost.get())
            if qty<=0 or cost<0: raise ValueError("Quantity must be positive and cost cannot be negative.")
        except ValueError as e: messagebox.showerror("Invalid values",str(e)); return
        p=self.po_choices[label]; status=self.po_status.get()
        cur=self.db.run("INSERT INTO purchases(ordered_at,supplier,product_id,product_name,quantity,unit_cost,status,notes,user_id) VALUES(?,?,?,?,?,?,?,?,?)",
            (datetime.now().isoformat(timespec="seconds"),supplier,p["id"],label,qty,cost,status,self.po_notes.get().strip(),self.user["id"]))
        if status in ("Received - unpaid","Paid"):
            self.db.run("UPDATE products SET quantity=quantity+?,cost=?,supplier=?,updated_at=? WHERE id=?",(qty,cost,supplier,datetime.now().isoformat(timespec="seconds"),p["id"]))
        self.po_notes.set(""); self.refresh_purchases(); self.refresh_inventory(); self.refresh_dashboard()
        messagebox.showinfo("Saved","Purchase record saved.")

    def refresh_purchases(self):
        if not hasattr(self,"purchase_tree"): return
        rows=self.db.rows("SELECT id,ordered_at,supplier,product_name,quantity,unit_cost,status,notes FROM purchases ORDER BY id DESC")
        self.fill_tree(self.purchase_tree,[(r["id"],r["ordered_at"],r["supplier"],r["product_name"],r["quantity"],f'₱{r["unit_cost"]:.2f}',r["status"],r["notes"]) for r in rows])

    def receive_purchase(self):
        pid=self.selected_id(self.purchase_tree)
        if pid is None: return
        po=self.db.one("SELECT * FROM purchases WHERE id=?",(pid,))
        if po["status"] in ("Received - unpaid","Paid"):
            messagebox.showinfo("Already received","This purchase is already recorded as received; stock will not be added again."); return
        if not messagebox.askyesno("Confirm delivery",f'Mark purchase #{pid} as received and add {po["quantity"]} units of {po["product_name"]} to stock?'): return
        self.db.conn.execute("BEGIN")
        try:
            self.db.conn.execute("UPDATE products SET quantity=quantity+?,cost=?,supplier=?,updated_at=? WHERE id=?",
                (po["quantity"],po["unit_cost"],po["supplier"],datetime.now().isoformat(timespec="seconds"),po["product_id"]))
            self.db.conn.execute("UPDATE purchases SET status='Received - unpaid' WHERE id=?",(pid,))
            self.db.conn.commit()
        except Exception as e:
            self.db.conn.rollback(); messagebox.showerror("Update failed",str(e)); return
        self.refresh_purchases(); self.refresh_inventory(); self.refresh_dashboard()

    def build_reports(self):
        f=self.reports_tab
        ttk.Label(f,text="Reports and monitoring",font=("Segoe UI",15,"bold")).pack(anchor="w",pady=(0,8))
        bar=ttk.Frame(f); bar.pack(fill="x",pady=(0,8))
        ttk.Button(bar,text="Refresh reports",command=self.refresh_reports).pack(side="left",padx=(0,6))
        ttk.Button(bar,text="Export sales CSV",command=self.export_sales).pack(side="left",padx=6)
        ttk.Button(bar,text="Export inventory CSV",command=self.export_inventory).pack(side="left",padx=6)
        ttk.Button(bar,text="Export purchases CSV",command=self.export_purchases).pack(side="left",padx=6)
        self.report_summary=ttk.Label(f,text="",font=("Segoe UI",11))
        self.report_summary.pack(anchor="w",pady=8)
        ttk.Label(f,text="Recent sales").pack(anchor="w")
        self.sales_report_tree=self.make_tree(f,[("id","Sale ID",70),("date","Date/time",170),("customer","Customer",180),("payment","Payment",120),("total","Total",110),("items","Items",300)])
        self.refresh_reports()

    def refresh_reports(self):
        if not hasattr(self,"sales_report_tree"): return
        total=self.db.one("SELECT COALESCE(SUM(total),0) n FROM sales")["n"]
        count=self.db.one("SELECT COUNT(*) n FROM sales")["n"]
        low=self.db.one("SELECT COUNT(*) n FROM products WHERE quantity<=min_quantity")["n"]
        openpo=self.db.one("SELECT COALESCE(SUM(quantity*unit_cost),0) n FROM purchases WHERE status IN ('Ordered','Received - unpaid','Received - inspect')")["n"]
        self.report_summary.configure(text=f"All-time sales: ₱{total:,.2f}   |   Transactions: {count}   |   Low-stock products: {low}   |   Estimated open purchase value: ₱{openpo:,.2f}")
        rows=self.db.rows("""SELECT s.id,s.sold_at,s.customer,s.payment_method,s.total,
             COALESCE(GROUP_CONCAT(si.product_name || ' ×' || si.quantity, ', '),'') items
             FROM sales s LEFT JOIN sale_items si ON s.id=si.sale_id
             GROUP BY s.id ORDER BY s.id DESC LIMIT 200""")
        self.fill_tree(self.sales_report_tree,[(r["id"],r["sold_at"],r["customer"],r["payment_method"],f'₱{r["total"]:.2f}',r["items"]) for r in rows])

    def export_rows(self, filename, headers, rows):
        path=Path(__file__).with_name(filename)
        with path.open("w",newline="",encoding="utf-8-sig") as f:
            writer=csv.writer(f); writer.writerow(headers); writer.writerows(rows)
        messagebox.showinfo("Export complete",f"CSV exported to:\n{path}")

    def export_sales(self):
        rows=self.db.rows("SELECT id,sold_at,customer,payment_method,total FROM sales ORDER BY id DESC")
        self.export_rows("storetrack_sales.csv",["Sale ID","Date/time","Customer","Payment method","Total"],[tuple(r) for r in rows])

    def export_inventory(self):
        rows=self.db.rows("SELECT sku,name,category,quantity,min_quantity,cost,price,expiration,supplier FROM products ORDER BY name")
        self.export_rows("storetrack_inventory.csv",["SKU","Product","Category","Quantity","Minimum quantity","Cost","Price","Expiration","Supplier"],[tuple(r) for r in rows])

    def export_purchases(self):
        rows=self.db.rows("SELECT id,ordered_at,supplier,product_name,quantity,unit_cost,status,notes FROM purchases ORDER BY id DESC")
        self.export_rows("storetrack_purchases.csv",["Purchase ID","Date/time","Supplier","Product","Quantity","Unit cost","Status","Notes"],[tuple(r) for r in rows])

    def build_users(self):
        f=self.users_tab
        ttk.Label(f,text="User accounts (Admin only)",font=("Segoe UI",15,"bold")).pack(anchor="w",pady=(0,8))
        form=ttk.LabelFrame(f,text="Create user",padding=10); form.pack(fill="x",pady=(0,10))
        self.new_username=tk.StringVar(); self.new_password=tk.StringVar(); self.new_role=tk.StringVar(value="Staff")
        ttk.Label(form,text="Username").grid(row=0,column=0,padx=4,pady=4); ttk.Entry(form,textvariable=self.new_username,width=20).grid(row=0,column=1,padx=4,pady=4)
        ttk.Label(form,text="Temporary password").grid(row=0,column=2,padx=4,pady=4); ttk.Entry(form,textvariable=self.new_password,width=20,show="•").grid(row=0,column=3,padx=4,pady=4)
        ttk.Label(form,text="Role").grid(row=0,column=4,padx=4,pady=4); ttk.Combobox(form,textvariable=self.new_role,values=["Staff","Admin"],state="readonly",width=12).grid(row=0,column=5,padx=4,pady=4)
        ttk.Button(form,text="Create user",command=self.create_user).grid(row=0,column=6,padx=8)
        self.users_tree=self.make_tree(f,[("id","ID",60),("username","Username",220),("role","Role",130),("active","Active",100)])
        ttk.Button(f,text="Activate / deactivate selected",command=self.toggle_user).pack(anchor="e",pady=8)
        self.refresh_users()

    def refresh_users(self):
        if not hasattr(self,"users_tree"): return
        self.fill_tree(self.users_tree,[tuple(r) for r in self.db.rows("SELECT id,username,role,CASE active WHEN 1 THEN 'Yes' ELSE 'No' END FROM users ORDER BY username")])

    def create_user(self):
        username=self.new_username.get().strip(); password=self.new_password.get()
        if len(username)<3 or len(password)<8:
            messagebox.showerror("Invalid account","Username must be at least 3 characters and password at least 8 characters."); return
        salt,digest=hash_password(password)
        try: self.db.run("INSERT INTO users(username,salt,password_hash,role) VALUES(?,?,?,?)",(username,salt,digest,self.new_role.get()))
        except sqlite3.IntegrityError: messagebox.showerror("Username exists","Choose a different username."); return
        self.new_username.set(""); self.new_password.set(""); self.refresh_users()
        messagebox.showinfo("User created","Account created successfully.")

    def toggle_user(self):
        uid=self.selected_id(self.users_tree)
        if uid is None: return
        target=self.db.one("SELECT * FROM users WHERE id=?",(uid,))
        if target["id"]==self.user["id"]:
            messagebox.showerror("Not allowed","You cannot deactivate your own account while signed in."); return
        self.db.run("UPDATE users SET active=1-active WHERE id=?",(uid,))
        self.refresh_users()

    def on_close(self):
        try: self.db.close()
        finally: self.root.destroy()

def main():
    root=tk.Tk()
    StoreTrackApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
