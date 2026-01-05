#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
سیستم جامع مدیریت انبار و حسابداری با روش FIFO
نسخه Flask
"""

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file
import sqlite3
import datetime
import os
import io
import json

try:
    import jdatetime
except ImportError:
    print("Installing jdatetime...")
    os.system('pip install jdatetime')
    import jdatetime

app = Flask(__name__)
app.secret_key = 'nyto-warehouse-secret-key-2024'

# مسیر دیتابیس
DB_PATH = os.environ.get('DB_PATH', 'data/warehouse.db')


# ==================== توابع کمکی تاریخ ====================
def get_persian_today():
    return jdatetime.date.today()

def gregorian_to_persian(gregorian_str):
    try:
        if isinstance(gregorian_str, str):
            gdate = datetime.date.fromisoformat(gregorian_str)
        else:
            gdate = gregorian_str
        jdate = jdatetime.date.fromgregorian(date=gdate)
        return jdate.strftime("%Y/%m/%d")
    except:
        return str(gregorian_str)

def persian_to_gregorian(year, month, day):
    try:
        jdate = jdatetime.date(int(year), int(month), int(day))
        gdate = jdate.togregorian()
        return gdate.isoformat()
    except:
        return datetime.date.today().isoformat()

def get_persian_months():
    return ["فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
            "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند"]

def format_number(num):
    """فرمت عدد با کاما"""
    try:
        return f"{int(num):,}"
    except:
        return str(num)


# ==================== کلاس مدیریت دیتابیس ====================
class DBManager:
    def __init__(self, db_path=None):
        self.db_path = db_path or DB_PATH
        os.makedirs(os.path.dirname(self.db_path) if os.path.dirname(self.db_path) else '.', exist_ok=True)
        self.create_tables()
    
    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def create_tables(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # 1. جدول محصولات
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                color TEXT DEFAULT '',
                barcode TEXT DEFAULT '',
                stock REAL DEFAULT 0
            )
        ''')
        
        # 2. جدول ورودی‌ها
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS inflows (
                id INTEGER PRIMARY KEY,
                product_id INTEGER,
                quantity REAL NOT NULL,
                remaining REAL NOT NULL,
                buy_price REAL NOT NULL,
                inflow_date TEXT NOT NULL,
                dollar_rate REAL DEFAULT 0,
                FOREIGN KEY (product_id) REFERENCES products(id)
            )
        ''')
        
        # 3. جدول مراکز فروش
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sales_centers (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                shipping_type TEXT DEFAULT 'manual',
                shipping_percent REAL DEFAULT 0,
                shipping_min REAL DEFAULT 0,
                shipping_max REAL DEFAULT 0,
                shipping_fixed REAL DEFAULT 0
            )
        ''')
        
        # 4. جدول دسته‌بندی کمیسیون
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS commission_categories (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                description TEXT DEFAULT ''
            )
        ''')
        
        # 5. جدول کمیسیون‌ها
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS commissions (
                id INTEGER PRIMARY KEY,
                center_id INTEGER,
                category_id INTEGER,
                commission_percent REAL DEFAULT 0,
                FOREIGN KEY (center_id) REFERENCES sales_centers(id),
                FOREIGN KEY (category_id) REFERENCES commission_categories(id),
                UNIQUE(center_id, category_id)
            )
        ''')
        
        # 6. جدول ارتباط محصول و دسته‌بندی
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS product_categories (
                product_id INTEGER,
                category_id INTEGER,
                PRIMARY KEY (product_id),
                FOREIGN KEY (product_id) REFERENCES products(id),
                FOREIGN KEY (category_id) REFERENCES commission_categories(id)
            )
        ''')
        
        # 7. جدول خروجی‌ها
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS outflows (
                id INTEGER PRIMARY KEY,
                product_id INTEGER,
                center_id INTEGER,
                quantity REAL NOT NULL,
                sell_price REAL NOT NULL,
                cogs_unit REAL NOT NULL,
                commission_amount REAL DEFAULT 0,
                shipping_cost REAL DEFAULT 0,
                outflow_date TEXT NOT NULL,
                order_number TEXT DEFAULT '',
                is_returned INTEGER DEFAULT 0,
                is_paid INTEGER DEFAULT 0,
                FOREIGN KEY (product_id) REFERENCES products(id),
                FOREIGN KEY (center_id) REFERENCES sales_centers(id)
            )
        ''')
        
        # 8. جدول تسویه حساب‌ها
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS settlements (
                id INTEGER PRIMARY KEY,
                center_id INTEGER,
                amount REAL NOT NULL,
                settlement_date TEXT NOT NULL,
                description TEXT DEFAULT '',
                FOREIGN KEY (center_id) REFERENCES sales_centers(id)
            )
        ''')
        
        # 9. جدول تراکنش‌های نقدی
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS cash_transactions (
                id INTEGER PRIMARY KEY,
                transaction_type TEXT NOT NULL,
                amount REAL NOT NULL,
                source TEXT DEFAULT '',
                description TEXT DEFAULT '',
                transaction_date TEXT NOT NULL
            )
        ''')
        
        # مراکز پیش‌فرض
        default_centers = [
            ('نایتو', 'manual', 0, 0, 0, 0),
            ('اسنپ شاپ', 'percent', 7, 20000, 150000, 0),
            ('دیجی کالا', 'percent', 7, 20000, 150000, 0)
        ]
        for center in default_centers:
            try:
                cursor.execute('''
                    INSERT OR IGNORE INTO sales_centers 
                    (name, shipping_type, shipping_percent, shipping_min, shipping_max, shipping_fixed)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', center)
            except:
                pass
        
        # Migration برای دیتابیس‌های قدیمی
        migrations = [
            ("ALTER TABLE inflows ADD COLUMN remaining REAL DEFAULT 0", 
             "UPDATE inflows SET remaining = quantity WHERE remaining = 0 OR remaining IS NULL"),
            ("ALTER TABLE inflows ADD COLUMN dollar_rate REAL DEFAULT 0", None),
            ("ALTER TABLE products ADD COLUMN barcode TEXT DEFAULT ''", None),
            ("ALTER TABLE outflows ADD COLUMN order_number TEXT DEFAULT ''", None),
            ("ALTER TABLE outflows ADD COLUMN is_returned INTEGER DEFAULT 0", None),
            ("ALTER TABLE outflows ADD COLUMN is_paid INTEGER DEFAULT 0", None),
        ]
        
        for alter_query, update_query in migrations:
            try:
                cursor.execute(alter_query)
                if update_query:
                    cursor.execute(update_query)
            except:
                pass
        
        conn.commit()
        conn.close()
    
    def execute_query(self, query, params=()):
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(query, params)
            conn.commit()
            result = cursor.fetchall()
            return result
        except sqlite3.Error as e:
            print(f"Database Error: {e}")
            return None
        finally:
            conn.close()
    
    def execute_insert(self, query, params=()):
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(query, params)
            conn.commit()
            return cursor.lastrowid
        except sqlite3.Error as e:
            print(f"Database Error: {e}")
            return None
        finally:
            conn.close()
    
    # ==================== محصولات ====================
    def get_products(self, stock_filter="all", search=""):
        query = "SELECT id, name, color, barcode, stock FROM products WHERE 1=1"
        params = []
        
        if stock_filter == "available":
            query += " AND stock > 0"
        elif stock_filter == "unavailable":
            query += " AND stock <= 0"
        
        if search:
            query += " AND (name LIKE ? OR barcode LIKE ?)"
            params.extend([f"%{search}%", f"%{search}%"])
        
        query += " ORDER BY name"
        return self.execute_query(query, params)
    
    def get_product(self, product_id):
        result = self.execute_query("SELECT * FROM products WHERE id = ?", (product_id,))
        return result[0] if result else None
    
    def add_product(self, name, color="", barcode=""):
        product_id = self.execute_insert(
            "INSERT INTO products (name, color, barcode, stock) VALUES (?, ?, ?, 0)",
            (name, color, barcode)
        )
        if not barcode and product_id:
            auto_barcode = f"200{product_id:010d}"
            self.execute_query("UPDATE products SET barcode = ? WHERE id = ?", (auto_barcode, product_id))
        return product_id
    
    def update_product(self, product_id, name, color, barcode):
        self.execute_query(
            "UPDATE products SET name=?, color=?, barcode=? WHERE id=?",
            (name, color, barcode, product_id)
        )
    
    def delete_product(self, product_id):
        inflows = self.execute_query("SELECT COUNT(*) as cnt FROM inflows WHERE product_id = ?", (product_id,))
        outflows = self.execute_query("SELECT COUNT(*) as cnt FROM outflows WHERE product_id = ?", (product_id,))
        
        if (inflows and inflows[0]['cnt'] > 0) or (outflows and outflows[0]['cnt'] > 0):
            return False, "این کالا دارای ورودی یا خروجی است"
        
        self.execute_query("DELETE FROM products WHERE id=?", (product_id,))
        return True, "کالا حذف شد"
    
    # ==================== ورودی‌ها ====================
    def add_inflow(self, product_id, quantity, buy_price, inflow_date, dollar_rate=0):
        self.execute_insert(
            "INSERT INTO inflows (product_id, quantity, remaining, buy_price, inflow_date, dollar_rate) VALUES (?, ?, ?, ?, ?, ?)",
            (product_id, quantity, quantity, buy_price, inflow_date, dollar_rate)
        )
        self.execute_query(
            "UPDATE products SET stock = stock + ? WHERE id = ?",
            (quantity, product_id)
        )
    
    def get_inflows(self, start_date=None, end_date=None, product_id=None):
        query = """
            SELECT i.id, i.product_id, p.name, p.color, i.quantity, i.buy_price, 
                   i.inflow_date, i.remaining, i.dollar_rate
            FROM inflows i 
            JOIN products p ON i.product_id = p.id
            WHERE 1=1
        """
        params = []
        if start_date:
            query += " AND i.inflow_date >= ?"
            params.append(start_date)
        if end_date:
            query += " AND i.inflow_date <= ?"
            params.append(end_date)
        if product_id:
            query += " AND i.product_id = ?"
            params.append(product_id)
        query += " ORDER BY i.inflow_date DESC"
        return self.execute_query(query, params)
    
    def delete_inflow(self, inflow_id):
        inflow = self.execute_query("SELECT product_id, quantity, remaining FROM inflows WHERE id = ?", (inflow_id,))
        if not inflow:
            return False, "ورودی یافت نشد"
        
        product_id, quantity, remaining = inflow[0]['product_id'], inflow[0]['quantity'], inflow[0]['remaining']
        
        if remaining < quantity:
            return False, "از این ورودی استفاده شده"
        
        self.execute_query("DELETE FROM inflows WHERE id = ?", (inflow_id,))
        self.execute_query("UPDATE products SET stock = stock - ? WHERE id = ?", (quantity, product_id))
        return True, "ورودی حذف شد"
    
    # ==================== خروجی‌ها ====================
    def calculate_fifo_cost(self, product_id, quantity):
        inflows = self.execute_query(
            "SELECT id, remaining, buy_price FROM inflows WHERE product_id = ? AND remaining > 0 ORDER BY inflow_date ASC",
            (product_id,)
        )
        
        if not inflows:
            return 0, []
        
        total_cost = 0
        remaining_qty = quantity
        used_inflows = []
        
        for row in inflows:
            if remaining_qty <= 0:
                break
            use_qty = min(row['remaining'], remaining_qty)
            total_cost += use_qty * row['buy_price']
            remaining_qty -= use_qty
            used_inflows.append((row['id'], use_qty))
        
        if remaining_qty > 0:
            return None, []
        
        return total_cost / quantity, used_inflows
    
    def add_outflow(self, product_id, center_id, quantity, sell_price, cogs_unit, commission, shipping, outflow_date, order_number=""):
        _, used_inflows = self.calculate_fifo_cost(product_id, quantity)
        
        for inflow_id, use_qty in used_inflows:
            self.execute_query(
                "UPDATE inflows SET remaining = remaining - ? WHERE id = ?",
                (use_qty, inflow_id)
            )
        
        self.execute_insert(
            """INSERT INTO outflows 
               (product_id, center_id, quantity, sell_price, cogs_unit, commission_amount, shipping_cost, outflow_date, order_number)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (product_id, center_id, quantity, sell_price, cogs_unit, commission, shipping, outflow_date, order_number)
        )
        
        self.execute_query(
            "UPDATE products SET stock = stock - ? WHERE id = ?",
            (quantity, product_id)
        )
    
    def get_outflows(self, start_date=None, end_date=None, center_id=None, is_returned=None, is_paid=None):
        query = """
            SELECT o.id, o.product_id, p.name, p.color, sc.name as center_name, o.quantity, o.sell_price, o.cogs_unit, 
                   o.commission_amount, o.shipping_cost, o.outflow_date, o.order_number, o.is_returned, o.is_paid, o.center_id
            FROM outflows o
            JOIN products p ON o.product_id = p.id
            JOIN sales_centers sc ON o.center_id = sc.id
            WHERE 1=1
        """
        params = []
        if start_date:
            query += " AND o.outflow_date >= ?"
            params.append(start_date)
        if end_date:
            query += " AND o.outflow_date <= ?"
            params.append(end_date)
        if center_id:
            query += " AND o.center_id = ?"
            params.append(center_id)
        if is_returned is not None:
            query += " AND o.is_returned = ?"
            params.append(1 if is_returned else 0)
        if is_paid is not None:
            query += " AND o.is_paid = ?"
            params.append(1 if is_paid else 0)
        query += " ORDER BY o.outflow_date DESC"
        return self.execute_query(query, params)
    
    def toggle_outflow_return(self, outflow_id):
        outflow = self.execute_query("SELECT is_returned, product_id, quantity FROM outflows WHERE id = ?", (outflow_id,))
        if outflow:
            is_returned = outflow[0]['is_returned']
            product_id = outflow[0]['product_id']
            quantity = outflow[0]['quantity']
            new_status = 0 if is_returned else 1
            self.execute_query("UPDATE outflows SET is_returned = ? WHERE id = ?", (new_status, outflow_id))
            if new_status == 1:
                self.execute_query("UPDATE products SET stock = stock + ? WHERE id = ?", (quantity, product_id))
            else:
                self.execute_query("UPDATE products SET stock = stock - ? WHERE id = ?", (quantity, product_id))
    
    def toggle_outflow_paid(self, outflow_id):
        outflow = self.execute_query("SELECT is_paid FROM outflows WHERE id = ?", (outflow_id,))
        if outflow:
            new_status = 0 if outflow[0]['is_paid'] else 1
            self.execute_query("UPDATE outflows SET is_paid = ? WHERE id = ?", (new_status, outflow_id))
    
    def delete_outflow(self, outflow_id):
        outflow = self.execute_query("SELECT product_id, quantity, is_returned FROM outflows WHERE id = ?", (outflow_id,))
        if not outflow:
            return False, "خروجی یافت نشد"
        
        if not outflow[0]['is_returned']:
            self.execute_query("UPDATE products SET stock = stock + ? WHERE id = ?", 
                             (outflow[0]['quantity'], outflow[0]['product_id']))
        
        self.execute_query("DELETE FROM outflows WHERE id = ?", (outflow_id,))
        return True, "خروجی حذف شد"
    
    # ==================== مراکز فروش ====================
    def get_centers(self):
        return self.execute_query(
            "SELECT id, name, shipping_type, shipping_percent, shipping_min, shipping_max, shipping_fixed FROM sales_centers ORDER BY name"
        )
    
    def get_center(self, center_id):
        result = self.execute_query("SELECT * FROM sales_centers WHERE id = ?", (center_id,))
        return result[0] if result else None
    
    def add_center(self, name, shipping_type='manual', shipping_percent=0, shipping_min=0, shipping_max=0, shipping_fixed=0):
        self.execute_insert(
            "INSERT INTO sales_centers (name, shipping_type, shipping_percent, shipping_min, shipping_max, shipping_fixed) VALUES (?, ?, ?, ?, ?, ?)",
            (name, shipping_type, shipping_percent, shipping_min, shipping_max, shipping_fixed)
        )
    
    def update_center(self, center_id, name, shipping_type, shipping_percent, shipping_min, shipping_max, shipping_fixed):
        self.execute_query(
            "UPDATE sales_centers SET name=?, shipping_type=?, shipping_percent=?, shipping_min=?, shipping_max=?, shipping_fixed=? WHERE id=?",
            (name, shipping_type, shipping_percent, shipping_min, shipping_max, shipping_fixed, center_id)
        )
    
    # ==================== کمیسیون ====================
    def get_categories(self):
        return self.execute_query("SELECT id, name, description FROM commission_categories ORDER BY name")
    
    def add_category(self, name, description=""):
        self.execute_insert(
            "INSERT INTO commission_categories (name, description) VALUES (?, ?)",
            (name, description)
        )
    
    def get_commissions(self):
        return self.execute_query("""
            SELECT c.id, sc.name as center_name, cc.name as category_name, c.commission_percent, c.center_id, c.category_id
            FROM commissions c
            JOIN sales_centers sc ON c.center_id = sc.id
            JOIN commission_categories cc ON c.category_id = cc.id
            ORDER BY sc.name, cc.name
        """)
    
    def set_commission(self, center_id, category_id, percent):
        self.execute_query(
            "INSERT OR REPLACE INTO commissions (center_id, category_id, commission_percent) VALUES (?, ?, ?)",
            (center_id, category_id, percent)
        )
    
    def get_product_commission(self, center_id, product_id):
        cat = self.execute_query("SELECT category_id FROM product_categories WHERE product_id = ?", (product_id,))
        if not cat:
            return 0
        comm = self.execute_query(
            "SELECT commission_percent FROM commissions WHERE center_id = ? AND category_id = ?",
            (center_id, cat[0]['category_id'])
        )
        return comm[0]['commission_percent'] if comm else 0
    
    def set_product_category(self, product_id, category_id):
        self.execute_query(
            "INSERT OR REPLACE INTO product_categories (product_id, category_id) VALUES (?, ?)",
            (product_id, category_id)
        )
    
    # ==================== تسویه ====================
    def add_settlement(self, center_id, amount, settlement_date, description=""):
        self.execute_insert(
            "INSERT INTO settlements (center_id, amount, settlement_date, description) VALUES (?, ?, ?, ?)",
            (center_id, amount, settlement_date, description)
        )
    
    def get_settlements(self, center_id=None):
        if center_id:
            return self.execute_query("""
                SELECT s.id, sc.name as center_name, s.amount, s.settlement_date, s.description
                FROM settlements s JOIN sales_centers sc ON s.center_id = sc.id
                WHERE s.center_id = ?
                ORDER BY s.settlement_date DESC
            """, (center_id,))
        return self.execute_query("""
            SELECT s.id, sc.name as center_name, s.amount, s.settlement_date, s.description
            FROM settlements s JOIN sales_centers sc ON s.center_id = sc.id
            ORDER BY s.settlement_date DESC
        """)
    
    def delete_settlement(self, settlement_id):
        self.execute_query("DELETE FROM settlements WHERE id = ?", (settlement_id,))
    
    # ==================== حساب نقدی ====================
    def add_cash_transaction(self, trans_type, amount, source, description, trans_date):
        self.execute_insert(
            "INSERT INTO cash_transactions (transaction_type, amount, source, description, transaction_date) VALUES (?, ?, ?, ?, ?)",
            (trans_type, amount, source, description, trans_date)
        )
    
    def get_cash_transactions(self, trans_type=None):
        if trans_type and trans_type != "all":
            return self.execute_query(
                "SELECT id, transaction_type, amount, source, description, transaction_date FROM cash_transactions WHERE transaction_type = ? ORDER BY transaction_date DESC, id DESC",
                (trans_type,)
            )
        return self.execute_query(
            "SELECT id, transaction_type, amount, source, description, transaction_date FROM cash_transactions ORDER BY transaction_date DESC, id DESC"
        )
    
    def delete_cash_transaction(self, trans_id):
        self.execute_query("DELETE FROM cash_transactions WHERE id = ?", (trans_id,))
    
    def get_cash_summary(self):
        deposits = self.execute_query("SELECT COALESCE(SUM(amount), 0) as total FROM cash_transactions WHERE transaction_type = 'deposit'")
        withdraws = self.execute_query("SELECT COALESCE(SUM(amount), 0) as total FROM cash_transactions WHERE transaction_type = 'withdraw'")
        total_deposits = deposits[0]['total'] if deposits else 0
        total_withdraws = withdraws[0]['total'] if withdraws else 0
        return total_deposits, total_withdraws, total_deposits - total_withdraws
    
    # ==================== داشبورد ====================
    def get_dashboard_stats(self):
        stats = {}
        
        result = self.execute_query("""
            SELECT 
                COALESCE(SUM(quantity * sell_price), 0) as revenue,
                COALESCE(SUM(quantity * cogs_unit), 0) as cogs,
                COALESCE(SUM(commission_amount), 0) as commission,
                COALESCE(SUM(shipping_cost), 0) as shipping
            FROM outflows WHERE is_returned = 0
        """)
        if result:
            stats['revenue'] = result[0]['revenue']
            stats['cogs'] = result[0]['cogs']
            stats['commission'] = result[0]['commission']
            stats['shipping'] = result[0]['shipping']
            stats['profit'] = stats['revenue'] - stats['cogs'] - stats['commission'] - stats['shipping']
        else:
            stats['revenue'] = stats['cogs'] = stats['commission'] = stats['shipping'] = stats['profit'] = 0
        
        result = self.execute_query("SELECT COALESCE(SUM(stock), 0) as total FROM products")
        stats['total_stock'] = result[0]['total'] if result else 0
        
        result = self.execute_query("SELECT COALESCE(SUM(remaining * buy_price), 0) as total FROM inflows WHERE remaining > 0")
        stats['inventory_value'] = result[0]['total'] if result else 0
        
        result = self.execute_query("SELECT COALESCE(SUM(amount), 0) as total FROM settlements")
        stats['total_settled'] = result[0]['total'] if result else 0
        
        deposits, withdraws, balance = self.get_cash_summary()
        stats['cash_deposits'] = deposits
        stats['cash_withdraws'] = withdraws
        stats['cash_balance'] = balance
        
        return stats
    
    def get_center_debts(self):
        return self.execute_query("""
            SELECT 
                sc.id,
                sc.name,
                COALESCE(SUM(CASE WHEN o.is_returned = 0 THEN o.quantity * o.sell_price ELSE 0 END), 0) as total_sales,
                COALESCE(SUM(CASE WHEN o.is_returned = 0 THEN o.commission_amount ELSE 0 END), 0) as total_commission,
                COALESCE(SUM(CASE WHEN o.is_returned = 0 THEN o.shipping_cost ELSE 0 END), 0) as total_shipping,
                COALESCE((SELECT SUM(amount) FROM settlements WHERE center_id = sc.id), 0) as settled
            FROM sales_centers sc
            LEFT JOIN outflows o ON sc.id = o.center_id AND o.is_paid = 0
            GROUP BY sc.id
        """)


# ایجاد instance دیتابیس
db = DBManager()


# ==================== Context Processors ====================
@app.context_processor
def utility_processor():
    return {
        'format_number': format_number,
        'gregorian_to_persian': gregorian_to_persian,
        'persian_months': get_persian_months(),
        'today': get_persian_today()
    }


# ==================== روت‌های اصلی ====================
@app.route('/')
def dashboard():
    stats = db.get_dashboard_stats()
    debts = db.get_center_debts()
    return render_template('dashboard.html', stats=stats, debts=debts)


# ==================== محصولات ====================
@app.route('/products')
def products():
    stock_filter = request.args.get('filter', 'all')
    search = request.args.get('search', '')
    products_list = db.get_products(stock_filter, search)
    return render_template('products.html', products=products_list, filter=stock_filter, search=search)

@app.route('/products/add', methods=['POST'])
def add_product():
    name = request.form.get('name', '').strip()
    color = request.form.get('color', '').strip()
    barcode = request.form.get('barcode', '').strip()
    
    if name:
        db.add_product(name, color, barcode)
        flash('کالا با موفقیت اضافه شد', 'success')
    else:
        flash('نام کالا الزامی است', 'error')
    
    return redirect(url_for('products'))

@app.route('/products/edit/<int:product_id>', methods=['POST'])
def edit_product(product_id):
    name = request.form.get('name', '').strip()
    color = request.form.get('color', '').strip()
    barcode = request.form.get('barcode', '').strip()
    
    if name:
        db.update_product(product_id, name, color, barcode)
        flash('کالا ویرایش شد', 'success')
    
    return redirect(url_for('products'))

@app.route('/products/delete/<int:product_id>', methods=['POST'])
def delete_product(product_id):
    success, msg = db.delete_product(product_id)
    flash(msg, 'success' if success else 'error')
    return redirect(url_for('products'))


# ==================== ورودی‌ها ====================
@app.route('/inflows')
def inflows():
    products_list = db.get_products()
    categories = db.get_categories()
    inflows_list = db.get_inflows()
    return render_template('inflows.html', products=products_list, categories=categories, inflows=inflows_list)

@app.route('/inflows/add', methods=['POST'])
def add_inflow():
    product_id = request.form.get('product_id', type=int)
    quantity = request.form.get('quantity', type=float)
    buy_price = request.form.get('buy_price', type=float)
    dollar_rate = request.form.get('dollar_rate', 0, type=float)
    year = request.form.get('year', type=int)
    month = request.form.get('month', type=int)
    day = request.form.get('day', type=int)
    
    if product_id and quantity and buy_price:
        inflow_date = persian_to_gregorian(year, month, day)
        db.add_inflow(product_id, quantity, buy_price, inflow_date, dollar_rate)
        flash('ورودی ثبت شد', 'success')
    else:
        flash('اطلاعات ناقص است', 'error')
    
    return redirect(url_for('inflows'))

@app.route('/inflows/delete/<int:inflow_id>', methods=['POST'])
def delete_inflow(inflow_id):
    success, msg = db.delete_inflow(inflow_id)
    flash(msg, 'success' if success else 'error')
    return redirect(url_for('inflows'))


# ==================== خروجی‌ها ====================
@app.route('/outflows')
def outflows():
    products_list = db.get_products(stock_filter="available")
    centers = db.get_centers()
    outflows_list = db.get_outflows()
    return render_template('outflows.html', products=products_list, centers=centers, outflows=outflows_list)

@app.route('/outflows/add', methods=['POST'])
def add_outflow():
    product_id = request.form.get('product_id', type=int)
    center_id = request.form.get('center_id', type=int)
    quantity = request.form.get('quantity', type=float)
    sell_price = request.form.get('sell_price', type=float)
    commission = request.form.get('commission', 0, type=float)
    shipping = request.form.get('shipping', 0, type=float)
    order_number = request.form.get('order_number', '').strip()
    year = request.form.get('year', type=int)
    month = request.form.get('month', type=int)
    day = request.form.get('day', type=int)
    
    if product_id and center_id and quantity and sell_price:
        cogs_unit, _ = db.calculate_fifo_cost(product_id, quantity)
        if cogs_unit is not None:
            outflow_date = persian_to_gregorian(year, month, day)
            db.add_outflow(product_id, center_id, quantity, sell_price, cogs_unit, commission, shipping, outflow_date, order_number)
            flash('خروجی ثبت شد', 'success')
        else:
            flash('موجودی کافی نیست', 'error')
    else:
        flash('اطلاعات ناقص است', 'error')
    
    return redirect(url_for('outflows'))

@app.route('/outflows/toggle_return/<int:outflow_id>', methods=['POST'])
def toggle_return(outflow_id):
    db.toggle_outflow_return(outflow_id)
    flash('وضعیت برگشت تغییر کرد', 'success')
    return redirect(url_for('outflows'))

@app.route('/outflows/toggle_paid/<int:outflow_id>', methods=['POST'])
def toggle_paid(outflow_id):
    db.toggle_outflow_paid(outflow_id)
    flash('وضعیت پرداخت تغییر کرد', 'success')
    return redirect(url_for('outflows'))

@app.route('/outflows/delete/<int:outflow_id>', methods=['POST'])
def delete_outflow(outflow_id):
    success, msg = db.delete_outflow(outflow_id)
    flash(msg, 'success' if success else 'error')
    return redirect(url_for('outflows'))


# ==================== مراکز فروش ====================
@app.route('/centers')
def centers():
    centers_list = db.get_centers()
    return render_template('centers.html', centers=centers_list)

@app.route('/centers/add', methods=['POST'])
def add_center():
    name = request.form.get('name', '').strip()
    shipping_type = request.form.get('shipping_type', 'manual')
    shipping_percent = request.form.get('shipping_percent', 0, type=float)
    shipping_min = request.form.get('shipping_min', 0, type=float)
    shipping_max = request.form.get('shipping_max', 0, type=float)
    shipping_fixed = request.form.get('shipping_fixed', 0, type=float)
    
    if name:
        db.add_center(name, shipping_type, shipping_percent, shipping_min, shipping_max, shipping_fixed)
        flash('مرکز فروش اضافه شد', 'success')
    
    return redirect(url_for('centers'))

@app.route('/centers/edit/<int:center_id>', methods=['POST'])
def edit_center(center_id):
    name = request.form.get('name', '').strip()
    shipping_type = request.form.get('shipping_type', 'manual')
    shipping_percent = request.form.get('shipping_percent', 0, type=float)
    shipping_min = request.form.get('shipping_min', 0, type=float)
    shipping_max = request.form.get('shipping_max', 0, type=float)
    shipping_fixed = request.form.get('shipping_fixed', 0, type=float)
    
    if name:
        db.update_center(center_id, name, shipping_type, shipping_percent, shipping_min, shipping_max, shipping_fixed)
        flash('مرکز فروش ویرایش شد', 'success')
    
    return redirect(url_for('centers'))


# ==================== کمیسیون ====================
@app.route('/commissions')
def commissions():
    categories = db.get_categories()
    centers = db.get_centers()
    commissions_list = db.get_commissions()
    products_list = db.get_products()
    return render_template('commissions.html', categories=categories, centers=centers, 
                          commissions=commissions_list, products=products_list)

@app.route('/commissions/add_category', methods=['POST'])
def add_category():
    name = request.form.get('name', '').strip()
    description = request.form.get('description', '').strip()
    
    if name:
        db.add_category(name, description)
        flash('دسته‌بندی اضافه شد', 'success')
    
    return redirect(url_for('commissions'))

@app.route('/commissions/set', methods=['POST'])
def set_commission():
    center_id = request.form.get('center_id', type=int)
    category_id = request.form.get('category_id', type=int)
    percent = request.form.get('percent', 0, type=float)
    
    if center_id and category_id:
        db.set_commission(center_id, category_id, percent)
        flash('کمیسیون ثبت شد', 'success')
    
    return redirect(url_for('commissions'))

@app.route('/commissions/set_product_category', methods=['POST'])
def set_product_category():
    product_id = request.form.get('product_id', type=int)
    category_id = request.form.get('category_id', type=int)
    
    if product_id and category_id:
        db.set_product_category(product_id, category_id)
        flash('دسته‌بندی محصول ثبت شد', 'success')
    
    return redirect(url_for('commissions'))


# ==================== تسویه حساب ====================
@app.route('/settlements')
def settlements():
    centers = db.get_centers()
    settlements_list = db.get_settlements()
    debts = db.get_center_debts()
    return render_template('settlements.html', centers=centers, settlements=settlements_list, debts=debts)

@app.route('/settlements/add', methods=['POST'])
def add_settlement():
    center_id = request.form.get('center_id', type=int)
    amount = request.form.get('amount', type=float)
    description = request.form.get('description', '').strip()
    year = request.form.get('year', type=int)
    month = request.form.get('month', type=int)
    day = request.form.get('day', type=int)
    
    if center_id and amount:
        settlement_date = persian_to_gregorian(year, month, day)
        db.add_settlement(center_id, amount, settlement_date, description)
        flash('تسویه ثبت شد', 'success')
    
    return redirect(url_for('settlements'))

@app.route('/settlements/delete/<int:settlement_id>', methods=['POST'])
def delete_settlement(settlement_id):
    db.delete_settlement(settlement_id)
    flash('تسویه حذف شد', 'success')
    return redirect(url_for('settlements'))


# ==================== حساب نقدی ====================
@app.route('/cash')
def cash():
    transactions = db.get_cash_transactions()
    deposits, withdraws, balance = db.get_cash_summary()
    return render_template('cash.html', transactions=transactions, 
                          deposits=deposits, withdraws=withdraws, balance=balance)

@app.route('/cash/add', methods=['POST'])
def add_cash_transaction():
    trans_type = request.form.get('type', 'deposit')
    amount = request.form.get('amount', type=float)
    source = request.form.get('source', '').strip()
    description = request.form.get('description', '').strip()
    year = request.form.get('year', type=int)
    month = request.form.get('month', type=int)
    day = request.form.get('day', type=int)
    
    if amount:
        trans_date = persian_to_gregorian(year, month, day)
        db.add_cash_transaction(trans_type, amount, source, description, trans_date)
        flash('تراکنش ثبت شد', 'success')
    
    return redirect(url_for('cash'))

@app.route('/cash/delete/<int:trans_id>', methods=['POST'])
def delete_cash_transaction(trans_id):
    db.delete_cash_transaction(trans_id)
    flash('تراکنش حذف شد', 'success')
    return redirect(url_for('cash'))


# ==================== گزارشات ====================
@app.route('/reports')
def reports():
    stats = db.get_dashboard_stats()
    products_list = db.get_products()
    centers = db.get_centers()
    
    # آمار مراکز
    center_stats = []
    for center in centers:
        result = db.execute_query("""
            SELECT COUNT(*) as count, COALESCE(SUM(quantity), 0) as qty, 
                   COALESCE(SUM(quantity * sell_price), 0) as sales,
                   COALESCE(SUM((quantity * sell_price) - (quantity * cogs_unit) - commission_amount - shipping_cost), 0) as profit
            FROM outflows WHERE center_id = ? AND is_returned = 0
        """, (center['id'],))
        if result:
            center_stats.append({
                'name': center['name'],
                'count': result[0]['count'],
                'qty': result[0]['qty'],
                'sales': result[0]['sales'],
                'profit': result[0]['profit']
            })
    
    return render_template('reports.html', stats=stats, products=products_list, center_stats=center_stats)


# ==================== API برای AJAX ====================
@app.route('/api/fifo_cost/<int:product_id>/<float:quantity>')
def api_fifo_cost(product_id, quantity):
    cogs, _ = db.calculate_fifo_cost(product_id, quantity)
    return jsonify({'cogs': cogs})

@app.route('/api/product_stock/<int:product_id>')
def api_product_stock(product_id):
    product = db.get_product(product_id)
    if product:
        return jsonify({'stock': product['stock']})
    return jsonify({'stock': 0})


# ==================== بکاپ ====================
@app.route('/backup/download')
def download_backup():
    if os.path.exists(DB_PATH):
        return send_file(
            DB_PATH,
            as_attachment=True,
            download_name=f"warehouse_backup_{get_persian_today().strftime('%Y%m%d')}.db"
        )
    flash('فایل دیتابیس یافت نشد', 'error')
    return redirect(url_for('dashboard'))

@app.route('/backup/upload', methods=['POST'])
def upload_backup():
    if 'file' not in request.files:
        flash('فایلی انتخاب نشده', 'error')
        return redirect(url_for('dashboard'))
    
    file = request.files['file']
    if file.filename == '':
        flash('فایلی انتخاب نشده', 'error')
        return redirect(url_for('dashboard'))
    
    if file:
        os.makedirs(os.path.dirname(DB_PATH) if os.path.dirname(DB_PATH) else '.', exist_ok=True)
        file.save(DB_PATH)
        global db
        db = DBManager()
        flash('دیتابیس بازیابی شد', 'success')
    
    return redirect(url_for('dashboard'))


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
