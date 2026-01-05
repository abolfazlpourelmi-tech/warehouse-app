#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
سیستم جامع مدیریت انبار و حسابداری با روش FIFO
نسخه کامل Streamlit - با تمام امکانات نسخه دسکتاپ
"""

import streamlit as st
import sqlite3
import datetime
import os
import io
import pandas as pd
from decimal import Decimal

try:
    import jdatetime
except ImportError:
    st.error("لطفاً کتابخانه jdatetime را نصب کنید: pip install jdatetime")
    st.stop()

# تنظیمات صفحه
st.set_page_config(
    page_title="سیستم مدیریت انبار NYTO",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded"
)

# استایل‌های CSS
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Vazirmatn:wght@400;500;700&display=swap');
    
    * {
        font-family: 'Vazirmatn', Tahoma, sans-serif !important;
    }
    
    .main .block-container {
        padding: 1rem 2rem;
    }
    
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border-radius: 15px;
        padding: 1rem;
        color: white;
        text-align: center;
        margin: 0.5rem 0;
    }
    
    .metric-card h3 {
        margin: 0;
        font-size: 0.9rem;
        opacity: 0.9;
    }
    
    .metric-card p {
        margin: 0.5rem 0 0 0;
        font-size: 1.5rem;
        font-weight: bold;
    }
    
    .profit-positive { color: #4CAF50 !important; }
    .profit-negative { color: #F44336 !important; }
    
    .debt-table th { background: #4CAF50; color: white; }
    
    div[data-testid="stMetricValue"] {
        font-size: 1.5rem;
    }
    
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    
    .stTabs [data-baseweb="tab"] {
        padding: 10px 20px;
    }
</style>
""", unsafe_allow_html=True)


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
        jdate = jdatetime.date(year, month, day)
        gdate = jdate.togregorian()
        return gdate.isoformat()
    except:
        return datetime.date.today().isoformat()

def get_persian_months():
    return ["فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
            "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند"]


# ==================== تاریخ شمسی ویجت ====================
def persian_date_input(label, key_prefix, default_date=None):
    """ویجت انتخاب تاریخ شمسی"""
    if default_date is None:
        default_date = get_persian_today()
    
    col1, col2, col3 = st.columns(3)
    with col1:
        year = st.number_input(f"سال", min_value=1390, max_value=1450, 
                               value=default_date.year, key=f"{key_prefix}_year")
    with col2:
        month = st.selectbox(f"ماه", options=range(1, 13), 
                            format_func=lambda x: get_persian_months()[x-1],
                            index=default_date.month-1, key=f"{key_prefix}_month")
    with col3:
        max_day = 31 if month <= 6 else (30 if month <= 11 else 29)
        day = st.number_input(f"روز", min_value=1, max_value=max_day,
                             value=min(default_date.day, max_day), key=f"{key_prefix}_day")
    
    return year, month, day


# ==================== کلاس مدیریت دیتابیس ====================
class DBManager:
    def __init__(self, db_path="warehouse.db"):
        self.db_path = db_path
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.create_tables()
    
    def create_tables(self):
        # 1. جدول محصولات
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                color TEXT DEFAULT '',
                barcode TEXT DEFAULT '',
                stock REAL DEFAULT 0
            )
        ''')
        
        # 2. جدول ورودی‌ها
        self.cursor.execute('''
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
        self.cursor.execute('''
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
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS commission_categories (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                description TEXT DEFAULT ''
            )
        ''')
        
        # 5. جدول کمیسیون‌ها
        self.cursor.execute('''
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
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS product_categories (
                product_id INTEGER,
                category_id INTEGER,
                PRIMARY KEY (product_id),
                FOREIGN KEY (product_id) REFERENCES products(id),
                FOREIGN KEY (category_id) REFERENCES commission_categories(id)
            )
        ''')
        
        # 7. جدول خروجی‌ها
        self.cursor.execute('''
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
        self.cursor.execute('''
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
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS cash_transactions (
                id INTEGER PRIMARY KEY,
                transaction_type TEXT NOT NULL,
                amount REAL NOT NULL,
                source TEXT DEFAULT '',
                description TEXT DEFAULT '',
                transaction_date TEXT NOT NULL
            )
        ''')
        
        # درج مراکز پیش‌فرض
        default_centers = [
            ('نایتو', 'manual', 0, 0, 0, 0),
            ('اسنپ شاپ', 'percent', 7, 20000, 150000, 0),
            ('دیجی کالا', 'percent', 7, 20000, 150000, 0)
        ]
        for center in default_centers:
            try:
                self.cursor.execute('''
                    INSERT OR IGNORE INTO sales_centers 
                    (name, shipping_type, shipping_percent, shipping_min, shipping_max, shipping_fixed)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', center)
            except:
                pass
        
        # ===== Migration برای دیتابیس‌های قدیمی =====
        # اضافه کردن ستون remaining به inflows
        try:
            self.cursor.execute("ALTER TABLE inflows ADD COLUMN remaining REAL DEFAULT 0")
            # مقداردهی اولیه remaining برابر با quantity
            self.cursor.execute("UPDATE inflows SET remaining = quantity WHERE remaining = 0 OR remaining IS NULL")
        except:
            pass
        
        # اضافه کردن ستون dollar_rate به inflows
        try:
            self.cursor.execute("ALTER TABLE inflows ADD COLUMN dollar_rate REAL DEFAULT 0")
        except:
            pass
        
        # اضافه کردن ستون barcode به products
        try:
            self.cursor.execute("ALTER TABLE products ADD COLUMN barcode TEXT DEFAULT ''")
        except:
            pass
        
        # اضافه کردن ستون order_number به outflows
        try:
            self.cursor.execute("ALTER TABLE outflows ADD COLUMN order_number TEXT DEFAULT ''")
        except:
            pass
        
        # اضافه کردن ستون is_returned به outflows
        try:
            self.cursor.execute("ALTER TABLE outflows ADD COLUMN is_returned INTEGER DEFAULT 0")
        except:
            pass
        
        # اضافه کردن ستون is_paid به outflows
        try:
            self.cursor.execute("ALTER TABLE outflows ADD COLUMN is_paid INTEGER DEFAULT 0")
        except:
            pass
        
        self.conn.commit()
    
    def execute_query(self, query, params=()):
        try:
            self.cursor.execute(query, params)
            self.conn.commit()
            return self.cursor.fetchall()
        except sqlite3.Error as e:
            st.error(f"خطای دیتابیس: {e}")
            return None
    
    # ==================== محصولات ====================
    def get_products(self, stock_filter="همه", search=""):
        query = "SELECT id, name, color, barcode, stock FROM products WHERE 1=1"
        params = []
        
        if stock_filter == "موجود":
            query += " AND stock > 0"
        elif stock_filter == "ناموجود":
            query += " AND stock <= 0"
        
        if search:
            query += " AND (name LIKE ? OR barcode LIKE ?)"
            params.extend([f"%{search}%", f"%{search}%"])
        
        query += " ORDER BY name"
        return self.execute_query(query, params)
    
    def add_product(self, name, color="", barcode=""):
        self.execute_query(
            "INSERT INTO products (name, color, barcode, stock) VALUES (?, ?, ?, 0)",
            (name, color, barcode)
        )
        product_id = self.cursor.lastrowid
        # تولید بارکد خودکار
        if not barcode:
            auto_barcode = f"200{product_id:010d}"
            self.execute_query("UPDATE products SET barcode = ? WHERE id = ?", (auto_barcode, product_id))
        return product_id
    
    def update_product(self, product_id, name, color, barcode):
        self.execute_query(
            "UPDATE products SET name=?, color=?, barcode=? WHERE id=?",
            (name, color, barcode, product_id)
        )
    
    def delete_product(self, product_id):
        # بررسی وابستگی‌ها
        inflows = self.execute_query("SELECT COUNT(*) FROM inflows WHERE product_id = ?", (product_id,))
        outflows = self.execute_query("SELECT COUNT(*) FROM outflows WHERE product_id = ?", (product_id,))
        
        if (inflows and inflows[0][0] > 0) or (outflows and outflows[0][0] > 0):
            return False, "این کالا دارای ورودی یا خروجی است و قابل حذف نیست."
        
        self.execute_query("DELETE FROM products WHERE id=?", (product_id,))
        return True, "کالا حذف شد."
    
    # ==================== ورودی‌ها ====================
    def add_inflow(self, product_id, quantity, buy_price, inflow_date, dollar_rate=0, category_id=None):
        self.execute_query(
            "INSERT INTO inflows (product_id, quantity, remaining, buy_price, inflow_date, dollar_rate) VALUES (?, ?, ?, ?, ?, ?)",
            (product_id, quantity, quantity, buy_price, inflow_date, dollar_rate)
        )
        self.execute_query(
            "UPDATE products SET stock = stock + ? WHERE id = ?",
            (quantity, product_id)
        )
        if category_id and category_id > 0:
            self.execute_query(
                "INSERT OR REPLACE INTO product_categories (product_id, category_id) VALUES (?, ?)",
                (product_id, category_id)
            )
    
    def get_inflows(self, start_date=None, end_date=None, product_id=None):
        query = """
            SELECT i.id, i.product_id, p.name, p.color, i.quantity, i.buy_price, i.inflow_date, i.remaining, i.dollar_rate
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
        if product_id and product_id > 0:
            query += " AND i.product_id = ?"
            params.append(product_id)
        query += " ORDER BY i.inflow_date DESC"
        return self.execute_query(query, params)
    
    def update_inflow(self, inflow_id, product_id, quantity, buy_price, inflow_date, dollar_rate):
        # گرفتن اطلاعات قبلی
        old = self.execute_query("SELECT product_id, quantity FROM inflows WHERE id = ?", (inflow_id,))
        if old:
            old_product_id, old_qty = old[0]
            # برگرداندن موجودی قدیمی
            self.execute_query("UPDATE products SET stock = stock - ? WHERE id = ?", (old_qty, old_product_id))
        
        # به‌روزرسانی ورودی
        self.execute_query(
            "UPDATE inflows SET product_id=?, quantity=?, remaining=?, buy_price=?, inflow_date=?, dollar_rate=? WHERE id=?",
            (product_id, quantity, quantity, buy_price, inflow_date, dollar_rate, inflow_id)
        )
        # اضافه کردن موجودی جدید
        self.execute_query("UPDATE products SET stock = stock + ? WHERE id = ?", (quantity, product_id))
    
    def delete_inflow(self, inflow_id):
        # گرفتن اطلاعات
        inflow = self.execute_query("SELECT product_id, quantity, remaining FROM inflows WHERE id = ?", (inflow_id,))
        if not inflow:
            return False, "ورودی یافت نشد."
        
        product_id, quantity, remaining = inflow[0]
        
        # بررسی اینکه آیا از این ورودی استفاده شده
        if remaining < quantity:
            return False, "از این ورودی در خروجی‌ها استفاده شده و قابل حذف نیست."
        
        # حذف و برگرداندن موجودی
        self.execute_query("DELETE FROM inflows WHERE id = ?", (inflow_id,))
        self.execute_query("UPDATE products SET stock = stock - ? WHERE id = ?", (quantity, product_id))
        return True, "ورودی حذف شد."
    
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
        
        for inflow_id, remaining, price in inflows:
            if remaining_qty <= 0:
                break
            use_qty = min(remaining, remaining_qty)
            total_cost += use_qty * price
            remaining_qty -= use_qty
            used_inflows.append((inflow_id, use_qty))
        
        if remaining_qty > 0:
            return None, []
        
        return total_cost / quantity, used_inflows
    
    def calculate_shipping_cost(self, center_id, sell_price, quantity):
        center = self.execute_query(
            "SELECT shipping_type, shipping_percent, shipping_min, shipping_max, shipping_fixed FROM sales_centers WHERE id = ?",
            (center_id,)
        )
        if not center:
            return 0
        
        ship_type, ship_percent, ship_min, ship_max, ship_fixed = center[0]
        
        if ship_type == 'manual':
            return 0
        elif ship_type == 'fixed':
            return ship_fixed
        elif ship_type == 'percent':
            total = sell_price * quantity
            shipping = total * (ship_percent / 100)
            shipping = max(shipping, ship_min)
            if ship_max > 0:
                shipping = min(shipping, ship_max)
            return shipping
        return 0
    
    def get_product_commission(self, center_id, product_id):
        # گرفتن دسته‌بندی محصول
        cat = self.execute_query("SELECT category_id FROM product_categories WHERE product_id = ?", (product_id,))
        if not cat:
            return 0
        category_id = cat[0][0]
        
        # گرفتن کمیسیون
        comm = self.execute_query(
            "SELECT commission_percent FROM commissions WHERE center_id = ? AND category_id = ?",
            (center_id, category_id)
        )
        return comm[0][0] if comm else 0
    
    def add_outflow(self, product_id, center_id, quantity, sell_price, cogs_unit, commission, shipping, outflow_date, order_number=""):
        # کسر از FIFO
        _, used_inflows = self.calculate_fifo_cost(product_id, quantity)
        
        for inflow_id, use_qty in used_inflows:
            self.execute_query(
                "UPDATE inflows SET remaining = remaining - ? WHERE id = ?",
                (use_qty, inflow_id)
            )
        
        # ثبت خروجی
        self.execute_query(
            """INSERT INTO outflows 
               (product_id, center_id, quantity, sell_price, cogs_unit, commission_amount, shipping_cost, outflow_date, order_number)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (product_id, center_id, quantity, sell_price, cogs_unit, commission, shipping, outflow_date, order_number)
        )
        
        # به‌روزرسانی موجودی
        self.execute_query(
            "UPDATE products SET stock = stock - ? WHERE id = ?",
            (quantity, product_id)
        )
    
    def get_outflows(self, start_date=None, end_date=None, product_id=None, center_id=None, is_returned=None, is_paid=None):
        query = """
            SELECT o.id, o.product_id, p.name, p.color, sc.name, o.quantity, o.sell_price, o.cogs_unit, 
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
        if product_id and product_id > 0:
            query += " AND o.product_id = ?"
            params.append(product_id)
        if center_id and center_id > 0:
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
            is_returned, product_id, quantity = outflow[0]
            new_status = 0 if is_returned else 1
            self.execute_query("UPDATE outflows SET is_returned = ? WHERE id = ?", (new_status, outflow_id))
            # برگرداندن یا کسر موجودی
            if new_status == 1:  # برگشت خورد
                self.execute_query("UPDATE products SET stock = stock + ? WHERE id = ?", (quantity, product_id))
            else:  # برگشت لغو شد
                self.execute_query("UPDATE products SET stock = stock - ? WHERE id = ?", (quantity, product_id))
    
    def toggle_outflow_paid(self, outflow_id):
        outflow = self.execute_query("SELECT is_paid FROM outflows WHERE id = ?", (outflow_id,))
        if outflow:
            is_paid = outflow[0][0]
            new_status = 0 if is_paid else 1
            self.execute_query("UPDATE outflows SET is_paid = ? WHERE id = ?", (new_status, outflow_id))
    
    def delete_outflow(self, outflow_id):
        outflow = self.execute_query("SELECT product_id, quantity, is_returned FROM outflows WHERE id = ?", (outflow_id,))
        if not outflow:
            return False, "خروجی یافت نشد."
        
        product_id, quantity, is_returned = outflow[0]
        
        # برگرداندن موجودی (اگر برگشتی نبوده)
        if not is_returned:
            self.execute_query("UPDATE products SET stock = stock + ? WHERE id = ?", (quantity, product_id))
        
        self.execute_query("DELETE FROM outflows WHERE id = ?", (outflow_id,))
        return True, "خروجی حذف شد."
    
    # ==================== مراکز فروش ====================
    def get_centers(self):
        return self.execute_query(
            "SELECT id, name, shipping_type, shipping_percent, shipping_min, shipping_max, shipping_fixed FROM sales_centers ORDER BY name"
        )
    
    def add_center(self, name, shipping_type='manual', shipping_percent=0, shipping_min=0, shipping_max=0, shipping_fixed=0):
        self.execute_query(
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
        self.execute_query(
            "INSERT INTO commission_categories (name, description) VALUES (?, ?)",
            (name, description)
        )
    
    def get_commissions(self):
        return self.execute_query("""
            SELECT c.id, sc.name, cc.name, c.commission_percent, c.center_id, c.category_id
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
    
    def get_product_category(self, product_id):
        result = self.execute_query(
            "SELECT category_id FROM product_categories WHERE product_id = ?",
            (product_id,)
        )
        return result[0][0] if result else None
    
    def set_product_category(self, product_id, category_id):
        self.execute_query(
            "INSERT OR REPLACE INTO product_categories (product_id, category_id) VALUES (?, ?)",
            (product_id, category_id)
        )
    
    # ==================== تسویه ====================
    def add_settlement(self, center_id, amount, settlement_date, description=""):
        self.execute_query(
            "INSERT INTO settlements (center_id, amount, settlement_date, description) VALUES (?, ?, ?, ?)",
            (center_id, amount, settlement_date, description)
        )
    
    def get_settlements(self, center_id=None):
        if center_id and center_id > 0:
            return self.execute_query("""
                SELECT s.id, sc.name, s.amount, s.settlement_date, s.description
                FROM settlements s JOIN sales_centers sc ON s.center_id = sc.id
                WHERE s.center_id = ?
                ORDER BY s.settlement_date DESC
            """, (center_id,))
        return self.execute_query("""
            SELECT s.id, sc.name, s.amount, s.settlement_date, s.description
            FROM settlements s JOIN sales_centers sc ON s.center_id = sc.id
            ORDER BY s.settlement_date DESC
        """)
    
    def delete_settlement(self, settlement_id):
        self.execute_query("DELETE FROM settlements WHERE id = ?", (settlement_id,))
    
    # ==================== حساب نقدی ====================
    def add_cash_transaction(self, trans_type, amount, source, description, trans_date):
        self.execute_query(
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
        deposits = self.execute_query("SELECT COALESCE(SUM(amount), 0) FROM cash_transactions WHERE transaction_type = 'deposit'")
        withdraws = self.execute_query("SELECT COALESCE(SUM(amount), 0) FROM cash_transactions WHERE transaction_type = 'withdraw'")
        total_deposits = deposits[0][0] if deposits else 0
        total_withdraws = withdraws[0][0] if withdraws else 0
        return total_deposits, total_withdraws, total_deposits - total_withdraws
    
    # ==================== داشبورد ====================
    def get_dashboard_stats(self):
        stats = {}
        
        # آمار فروش
        result = self.execute_query("""
            SELECT 
                COALESCE(SUM(quantity * sell_price), 0),
                COALESCE(SUM(quantity * cogs_unit), 0),
                COALESCE(SUM(commission_amount), 0),
                COALESCE(SUM(shipping_cost), 0)
            FROM outflows WHERE is_returned = 0
        """)
        if result and result[0]:
            stats['revenue'] = result[0][0]
            stats['cogs'] = result[0][1]
            stats['commission'] = result[0][2]
            stats['shipping'] = result[0][3]
            stats['profit'] = stats['revenue'] - stats['cogs'] - stats['commission'] - stats['shipping']
        else:
            stats['revenue'] = stats['cogs'] = stats['commission'] = stats['shipping'] = stats['profit'] = 0
        
        # موجودی
        result = self.execute_query("SELECT COALESCE(SUM(stock), 0) FROM products")
        stats['total_stock'] = result[0][0] if result else 0
        
        # ارزش موجودی
        result = self.execute_query("SELECT COALESCE(SUM(remaining * buy_price), 0) FROM inflows WHERE remaining > 0")
        stats['inventory_value'] = result[0][0] if result else 0
        
        # تسویه شده
        result = self.execute_query("SELECT COALESCE(SUM(amount), 0) FROM settlements")
        stats['total_settled'] = result[0][0] if result else 0
        
        # موجودی نقدی
        deposits, withdraws, balance = self.get_cash_summary()
        stats['cash_deposits'] = deposits
        stats['cash_withdraws'] = withdraws
        stats['cash_balance'] = balance
        
        return stats
    
    def get_center_debts(self):
        """محاسبه بدهی هر مرکز فروش"""
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
    
    def get_database_bytes(self):
        self.conn.commit()
        with open(self.db_path, 'rb') as f:
            return f.read()


# ==================== راه‌اندازی ====================
@st.cache_resource
def get_database():
    return DBManager()

db = get_database()


# ==================== سایدبار ====================
with st.sidebar:
    st.markdown("## 📦 سیستم انبارداری")
    st.markdown(f"📅 {get_persian_today().strftime('%Y/%m/%d')}")
    st.markdown("---")
    
    menu = st.radio(
        "منو",
        ["🏠 داشبورد", "📦 مدیریت کالا", "📥 ورودی انبار", "📤 خروجی انبار",
         "🏪 مراکز فروش", "💰 کمیسیون‌ها", "💵 تسویه حساب", "🏦 حساب نقدی",
         "💲 قیمت‌گذاری", "📊 گزارشات", "⚙️ مدیریت داده"],
        label_visibility="collapsed"
    )
    
    st.markdown("---")
    st.markdown("### 💾 بکاپ دیتابیس")
    
    db_bytes = db.get_database_bytes()
    st.download_button(
        label="📥 دانلود",
        data=db_bytes,
        file_name=f"warehouse_{jdatetime.date.today().strftime('%Y%m%d')}.db",
        mime="application/octet-stream"
    )
    
    uploaded_db = st.file_uploader("📤 بازیابی", type=['db'], label_visibility="collapsed")
    if uploaded_db:
        if st.button("⚠️ بازیابی دیتابیس"):
            with open("warehouse.db", "wb") as f:
                f.write(uploaded_db.read())
            st.cache_resource.clear()
            st.rerun()


# ==================== داشبورد ====================
if menu == "🏠 داشبورد":
    st.markdown("# 🏠 داشبورد")
    
    stats = db.get_dashboard_stats()
    
    # ردیف اول - آمار فروش
    st.markdown("### 📊 خلاصه مالی")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("💰 درآمد کل فروش", f"{stats['revenue']:,.0f} تومان")
    with col2:
        st.metric("📦 بهای تمام شده", f"{stats['cogs']:,.0f} تومان")
    with col3:
        st.metric("💳 کمیسیون‌ها", f"{stats['commission']:,.0f} تومان")
    with col4:
        profit_delta = "مثبت" if stats['profit'] >= 0 else "منفی"
        st.metric("📈 سود خالص", f"{stats['profit']:,.0f} تومان", delta=profit_delta)
    
    # ردیف دوم - موجودی
    st.markdown("### 🏪 وضعیت انبار و حساب")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("📦 موجودی انبار", f"{stats['total_stock']:,.0f} واحد")
    with col2:
        st.metric("💎 ارزش موجودی", f"{stats['inventory_value']:,.0f} تومان")
    with col3:
        st.metric("✅ تسویه شده", f"{stats['total_settled']:,.0f} تومان")
    with col4:
        st.metric("🏦 موجودی نقدی", f"{stats['cash_balance']:,.0f} تومان")
    
    # جدول بدهی مراکز
    st.markdown("### 💳 بدهی مراکز فروش")
    debts = db.get_center_debts()
    if debts:
        debt_data = []
        for cid, name, sales, comm, ship, settled in debts:
            receivable = sales - comm - ship
            debt = receivable - settled
            debt_data.append({
                'مرکز فروش': name,
                'کل فروش': f"{sales:,.0f}",
                'کمیسیون+ارسال': f"{comm + ship:,.0f}",
                'قابل دریافت': f"{receivable:,.0f}",
                'تسویه شده': f"{settled:,.0f}",
                'بدهی': f"{debt:,.0f}"
            })
        st.dataframe(pd.DataFrame(debt_data), use_container_width=True, hide_index=True)


# ==================== مدیریت کالا ====================
elif menu == "📦 مدیریت کالا":
    st.markdown("# 📦 مدیریت کالا")
    
    tab1, tab2, tab3 = st.tabs(["➕ افزودن", "📋 لیست کالاها", "✏️ ویرایش/حذف"])
    
    with tab1:
        with st.form("add_product"):
            col1, col2 = st.columns(2)
            with col1:
                name = st.text_input("نام کالا *")
            with col2:
                color = st.text_input("رنگ / مدل")
            barcode = st.text_input("بارکد (خالی = خودکار)")
            
            if st.form_submit_button("➕ افزودن کالا", type="primary"):
                if name:
                    db.add_product(name, color, barcode)
                    st.success("✅ کالا اضافه شد!")
                    st.rerun()
                else:
                    st.error("نام کالا الزامی است!")
    
    with tab2:
        col1, col2 = st.columns(2)
        with col1:
            stock_filter = st.selectbox("فیلتر موجودی", ["همه", "موجود", "ناموجود"])
        with col2:
            search = st.text_input("🔍 جستجو")
        
        products = db.get_products(stock_filter, search)
        if products:
            df = pd.DataFrame(products, columns=['ID', 'نام', 'رنگ', 'بارکد', 'موجودی'])
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("کالایی یافت نشد.")
    
    with tab3:
        products = db.get_products()
        if products:
            selected_id = st.selectbox(
                "انتخاب کالا",
                options=[p[0] for p in products],
                format_func=lambda x: next((f"[{p[0]}] {p[1]} - {p[2]}" for p in products if p[0] == x), str(x))
            )
            
            product = next((p for p in products if p[0] == selected_id), None)
            if product:
                with st.form("edit_product"):
                    col1, col2 = st.columns(2)
                    with col1:
                        edit_name = st.text_input("نام", value=product[1])
                    with col2:
                        edit_color = st.text_input("رنگ", value=product[2] or "")
                    edit_barcode = st.text_input("بارکد", value=product[3] or "")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.form_submit_button("💾 ذخیره", type="primary"):
                            db.update_product(selected_id, edit_name, edit_color, edit_barcode)
                            st.success("✅ ذخیره شد!")
                            st.rerun()
                    with col2:
                        if st.form_submit_button("🗑️ حذف", type="secondary"):
                            success, msg = db.delete_product(selected_id)
                            if success:
                                st.success(msg)
                                st.rerun()
                            else:
                                st.error(msg)


# ==================== ورودی انبار ====================
elif menu == "📥 ورودی انبار":
    st.markdown("# 📥 ورودی انبار")
    
    tab1, tab2, tab3 = st.tabs(["➕ ثبت ورودی", "📋 تاریخچه", "✏️ ویرایش/حذف"])
    
    with tab1:
        products = db.get_products()
        categories = db.get_categories()
        
        if not products:
            st.warning("ابتدا کالا ثبت کنید!")
        else:
            with st.form("add_inflow"):
                product_id = st.selectbox(
                    "انتخاب کالا *",
                    options=[p[0] for p in products],
                    format_func=lambda x: next((f"[{p[0]}] {p[1]} - {p[2]}" for p in products if p[0] == x), str(x))
                )
                
                col1, col2 = st.columns(2)
                with col1:
                    quantity = st.number_input("تعداد *", min_value=0.01, value=1.0, step=1.0)
                with col2:
                    buy_price = st.number_input("قیمت خرید (تومان) *", min_value=0, value=0, step=1000)
                
                col1, col2 = st.columns(2)
                with col1:
                    dollar_rate = st.number_input("نرخ دلار (تومان)", min_value=0, value=0, step=1000)
                with col2:
                    if categories:
                        category_options = [(-1, "بدون دسته‌بندی")] + [(c[0], c[1]) for c in categories]
                        category_id = st.selectbox(
                            "دسته‌بندی کمیسیون",
                            options=[c[0] for c in category_options],
                            format_func=lambda x: next((c[1] for c in category_options if c[0] == x), str(x))
                        )
                    else:
                        category_id = -1
                
                st.markdown("**تاریخ ورودی:**")
                year, month, day = persian_date_input("تاریخ", "inflow")
                
                if st.form_submit_button("➕ ثبت ورودی", type="primary"):
                    if product_id and quantity > 0 and buy_price > 0:
                        inflow_date = persian_to_gregorian(year, month, day)
                        db.add_inflow(product_id, quantity, buy_price, inflow_date, dollar_rate, category_id)
                        st.success("✅ ورودی ثبت شد!")
                        st.rerun()
                    else:
                        st.error("فیلدهای ضروری را پر کنید!")
    
    with tab2:
        st.markdown("**فیلتر تاریخ:**")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("از تاریخ:")
            today = get_persian_today()
            try:
                one_year_ago = jdatetime.date(today.year - 1, today.month, today.day)
            except:
                one_year_ago = jdatetime.date(today.year - 1, today.month, 1)
            start_y, start_m, start_d = persian_date_input("از", "inf_start", one_year_ago)
        with col2:
            st.markdown("تا تاریخ:")
            end_y, end_m, end_d = persian_date_input("تا", "inf_end", today)
        
        start_date = persian_to_gregorian(start_y, start_m, start_d)
        end_date = persian_to_gregorian(end_y, end_m, end_d)
        
        inflows = db.get_inflows(start_date, end_date)
        if inflows:
            data = []
            total = 0
            for i in inflows:
                amount = i[4] * i[5]
                total += amount
                data.append({
                    'ID': i[0],
                    'کد کالا': i[1],
                    'نام کالا': i[2],
                    'رنگ': i[3] or '-',
                    'تعداد': i[4],
                    'قیمت خرید': f"{i[5]:,.0f}",
                    'مبلغ کل': f"{amount:,.0f}",
                    'تاریخ': gregorian_to_persian(i[6]),
                    'باقیمانده': i[7],
                    'نرخ دلار': f"{i[8]:,.0f}" if i[8] else '-'
                })
            st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True)
            st.info(f"📊 جمع کل: {total:,.0f} تومان | تعداد ردیف: {len(data)}")
        else:
            st.info("ورودی یافت نشد.")
    
    with tab3:
        inflows = db.get_inflows()
        if inflows:
            selected_inflow = st.selectbox(
                "انتخاب ورودی",
                options=[i[0] for i in inflows],
                format_func=lambda x: next((f"[{i[0]}] {i[2]} - {gregorian_to_persian(i[6])} - {i[4]} عدد" for i in inflows if i[0] == x), str(x))
            )
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("🗑️ حذف ورودی", type="secondary"):
                    success, msg = db.delete_inflow(selected_inflow)
                    if success:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)


# ==================== خروجی انبار ====================
elif menu == "📤 خروجی انبار":
    st.markdown("# 📤 خروجی انبار")
    
    tab1, tab2, tab3 = st.tabs(["➕ ثبت خروجی", "📋 تاریخچه", "🔄 تغییر وضعیت"])
    
    with tab1:
        products = db.get_products(stock_filter="موجود")
        centers = db.get_centers()
        
        if not products:
            st.warning("کالای موجود نیست!")
        elif not centers:
            st.warning("مرکز فروش ثبت کنید!")
        else:
            with st.form("add_outflow"):
                order_number = st.text_input("شماره سفارش")
                
                product_id = st.selectbox(
                    "انتخاب کالا *",
                    options=[p[0] for p in products],
                    format_func=lambda x: next((f"[{p[0]}] {p[1]} - {p[2]} (موجودی: {p[4]})" for p in products if p[0] == x), str(x))
                )
                
                center_id = st.selectbox(
                    "مرکز فروش *",
                    options=[c[0] for c in centers],
                    format_func=lambda x: next((c[1] for c in centers if c[0] == x), str(x))
                )
                
                col1, col2 = st.columns(2)
                with col1:
                    quantity = st.number_input("تعداد *", min_value=0.01, value=1.0, step=1.0)
                with col2:
                    sell_price = st.number_input("قیمت فروش (تومان) *", min_value=0, value=0, step=1000)
                
                col1, col2 = st.columns(2)
                with col1:
                    commission = st.number_input("کمیسیون (تومان)", min_value=0, value=0, step=1000)
                with col2:
                    shipping = st.number_input("هزینه ارسال (تومان)", min_value=0, value=0, step=1000)
                
                st.markdown("**تاریخ خروجی:**")
                year, month, day = persian_date_input("تاریخ", "outflow")
                
                # نمایش بهای تمام شده
                if product_id and quantity > 0:
                    cogs_unit, _ = db.calculate_fifo_cost(product_id, quantity)
                    if cogs_unit:
                        st.info(f"💰 بهای تمام شده واحد (FIFO): {cogs_unit:,.0f} تومان")
                    else:
                        st.warning("⚠️ موجودی کافی نیست!")
                        cogs_unit = 0
                else:
                    cogs_unit = 0
                
                if st.form_submit_button("➕ ثبت خروجی", type="primary"):
                    if product_id and center_id and quantity > 0 and sell_price > 0:
                        product = next((p for p in products if p[0] == product_id), None)
                        if product and product[4] >= quantity and cogs_unit:
                            outflow_date = persian_to_gregorian(year, month, day)
                            db.add_outflow(product_id, center_id, quantity, sell_price, cogs_unit, commission, shipping, outflow_date, order_number)
                            st.success("✅ خروجی ثبت شد!")
                            st.rerun()
                        else:
                            st.error("⚠️ موجودی کافی نیست!")
                    else:
                        st.error("فیلدهای ضروری را پر کنید!")
    
    with tab2:
        st.markdown("**فیلترها:**")
        col1, col2, col3 = st.columns(3)
        with col1:
            out_filter_return = st.selectbox("وضعیت برگشت", ["همه", "تحویل شده", "برگشت خورده"], key="out_ret")
        with col2:
            out_filter_paid = st.selectbox("وضعیت پرداخت", ["همه", "پرداخت شده", "در انتظار"], key="out_paid")
        with col3:
            centers = db.get_centers()
            center_options = [(-1, "همه مراکز")] + [(c[0], c[1]) for c in centers]
            out_filter_center = st.selectbox(
                "مرکز فروش",
                options=[c[0] for c in center_options],
                format_func=lambda x: next((c[1] for c in center_options if c[0] == x), str(x)),
                key="out_center"
            )
        
        is_returned = None if out_filter_return == "همه" else (out_filter_return == "برگشت خورده")
        is_paid = None if out_filter_paid == "همه" else (out_filter_paid == "پرداخت شده")
        
        outflows = db.get_outflows(
            center_id=out_filter_center if out_filter_center > 0 else None,
            is_returned=is_returned,
            is_paid=is_paid
        )
        
        if outflows:
            data = []
            total_revenue = total_profit = 0
            for o in outflows:
                revenue = o[5] * o[6]
                profit = revenue - (o[5] * o[7]) - o[8] - o[9]
                if not o[12]:  # اگر برگشتی نیست
                    total_revenue += revenue
                    total_profit += profit
                data.append({
                    'ID': o[0],
                    'شماره سفارش': o[11] or '-',
                    'کالا': f"{o[2]}" + (f" - {o[3]}" if o[3] else ""),
                    'مرکز': o[4],
                    'تعداد': o[5],
                    'قیمت فروش': f"{o[6]:,.0f}",
                    'بهای تمام شده': f"{o[7]:,.0f}",
                    'کمیسیون': f"{o[8]:,.0f}",
                    'ارسال': f"{o[9]:,.0f}",
                    'سود': f"{profit:,.0f}",
                    'تاریخ': gregorian_to_persian(o[10]),
                    'برگشتی': '✅' if o[12] else '❌',
                    'پرداخت': '✅' if o[13] else '❌'
                })
            st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True)
            st.info(f"📊 فروش: {total_revenue:,.0f} | سود: {total_profit:,.0f} | تعداد: {len(data)}")
        else:
            st.info("خروجی یافت نشد.")
    
    with tab3:
        outflows = db.get_outflows()
        if outflows:
            selected_outflow = st.selectbox(
                "انتخاب خروجی",
                options=[o[0] for o in outflows],
                format_func=lambda x: next((f"[{o[0]}] {o[11] or '-'} - {o[2]} - {gregorian_to_persian(o[10])}" for o in outflows if o[0] == x), str(x))
            )
            
            outflow = next((o for o in outflows if o[0] == selected_outflow), None)
            if outflow:
                col1, col2, col3 = st.columns(3)
                with col1:
                    status = "برگشت خورده ✅" if outflow[12] else "تحویل شده"
                    if st.button(f"🔄 تغییر به {'تحویل شده' if outflow[12] else 'برگشت خورده'}"):
                        db.toggle_outflow_return(selected_outflow)
                        st.success("وضعیت برگشت تغییر کرد!")
                        st.rerun()
                with col2:
                    status = "پرداخت شده ✅" if outflow[13] else "در انتظار پرداخت"
                    if st.button(f"💰 تغییر به {'در انتظار' if outflow[13] else 'پرداخت شده'}"):
                        db.toggle_outflow_paid(selected_outflow)
                        st.success("وضعیت پرداخت تغییر کرد!")
                        st.rerun()
                with col3:
                    if st.button("🗑️ حذف خروجی", type="secondary"):
                        success, msg = db.delete_outflow(selected_outflow)
                        if success:
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)


# ==================== مراکز فروش ====================
elif menu == "🏪 مراکز فروش":
    st.markdown("# 🏪 مراکز فروش")
    
    tab1, tab2 = st.tabs(["➕ افزودن/ویرایش", "📋 لیست مراکز"])
    
    with tab1:
        with st.form("add_center"):
            name = st.text_input("نام مرکز *")
            
            shipping_type = st.selectbox("نوع محاسبه ارسال", 
                                        options=['manual', 'percent', 'fixed'],
                                        format_func=lambda x: {'manual': 'دستی', 'percent': 'درصدی', 'fixed': 'ثابت'}[x])
            
            col1, col2 = st.columns(2)
            with col1:
                shipping_percent = st.number_input("درصد ارسال", min_value=0.0, max_value=100.0, value=0.0)
                shipping_min = st.number_input("حداقل ارسال", min_value=0, value=0)
            with col2:
                shipping_max = st.number_input("حداکثر ارسال", min_value=0, value=0)
                shipping_fixed = st.number_input("هزینه ثابت", min_value=0, value=0)
            
            if st.form_submit_button("➕ افزودن مرکز", type="primary"):
                if name:
                    db.add_center(name, shipping_type, shipping_percent, shipping_min, shipping_max, shipping_fixed)
                    st.success("✅ مرکز اضافه شد!")
                    st.rerun()
    
    with tab2:
        centers = db.get_centers()
        if centers:
            data = []
            for c in centers:
                data.append({
                    'ID': c[0],
                    'نام': c[1],
                    'نوع ارسال': {'manual': 'دستی', 'percent': 'درصدی', 'fixed': 'ثابت'}.get(c[2], c[2]),
                    'درصد': f"{c[3]}%",
                    'حداقل': f"{c[4]:,.0f}",
                    'حداکثر': f"{c[5]:,.0f}",
                    'ثابت': f"{c[6]:,.0f}"
                })
            st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True)


# ==================== کمیسیون‌ها ====================
elif menu == "💰 کمیسیون‌ها":
    st.markdown("# 💰 تنظیمات کمیسیون")
    
    tab1, tab2, tab3 = st.tabs(["📂 دسته‌بندی‌ها", "⚙️ تنظیم کمیسیون", "🏷️ دسته‌بندی محصولات"])
    
    with tab1:
        with st.form("add_category"):
            col1, col2 = st.columns(2)
            with col1:
                cat_name = st.text_input("نام دسته‌بندی")
            with col2:
                cat_desc = st.text_input("توضیحات")
            if st.form_submit_button("➕ افزودن"):
                if cat_name:
                    db.add_category(cat_name, cat_desc)
                    st.success("✅ اضافه شد!")
                    st.rerun()
        
        categories = db.get_categories()
        if categories:
            df = pd.DataFrame(categories, columns=['ID', 'نام', 'توضیحات'])
            st.dataframe(df, use_container_width=True, hide_index=True)
    
    with tab2:
        centers = db.get_centers()
        categories = db.get_categories()
        
        if centers and categories:
            with st.form("set_commission"):
                col1, col2, col3 = st.columns(3)
                with col1:
                    center_id = st.selectbox("مرکز فروش", options=[c[0] for c in centers],
                                            format_func=lambda x: next((c[1] for c in centers if c[0] == x), str(x)))
                with col2:
                    category_id = st.selectbox("دسته‌بندی", options=[c[0] for c in categories],
                                              format_func=lambda x: next((c[1] for c in categories if c[0] == x), str(x)))
                with col3:
                    percent = st.number_input("درصد کمیسیون", min_value=0.0, max_value=100.0, value=0.0)
                
                if st.form_submit_button("💾 ذخیره"):
                    db.set_commission(center_id, category_id, percent)
                    st.success("✅ ذخیره شد!")
                    st.rerun()
            
            # ماتریس کمیسیون
            st.markdown("### 📊 ماتریس کمیسیون")
            matrix_data = []
            for cat in categories:
                row = {'دسته‌بندی': cat[1]}
                for center in centers:
                    comm = db.execute_query(
                        "SELECT commission_percent FROM commissions WHERE center_id = ? AND category_id = ?",
                        (center[0], cat[0])
                    )
                    row[center[1]] = f"{comm[0][0]}%" if comm else "0%"
                matrix_data.append(row)
            st.dataframe(pd.DataFrame(matrix_data), use_container_width=True, hide_index=True)
    
    with tab3:
        products = db.get_products()
        categories = db.get_categories()
        
        if products and categories:
            with st.form("set_product_category"):
                product_id = st.selectbox("محصول", options=[p[0] for p in products],
                                         format_func=lambda x: next((f"[{p[0]}] {p[1]}" for p in products if p[0] == x), str(x)))
                category_id = st.selectbox("دسته‌بندی", options=[c[0] for c in categories],
                                          format_func=lambda x: next((c[1] for c in categories if c[0] == x), str(x)))
                
                if st.form_submit_button("💾 ذخیره"):
                    db.set_product_category(product_id, category_id)
                    st.success("✅ ذخیره شد!")


# ==================== تسویه حساب ====================
elif menu == "💵 تسویه حساب":
    st.markdown("# 💵 تسویه حساب")
    
    tab1, tab2, tab3 = st.tabs(["➕ ثبت تسویه", "📊 بدهی مراکز", "📋 تاریخچه"])
    
    with tab1:
        centers = db.get_centers()
        if centers:
            with st.form("add_settlement"):
                center_id = st.selectbox("مرکز فروش", options=[c[0] for c in centers],
                                        format_func=lambda x: next((c[1] for c in centers if c[0] == x), str(x)))
                amount = st.number_input("مبلغ (تومان)", min_value=0, value=0, step=10000)
                description = st.text_input("توضیحات")
                
                st.markdown("**تاریخ تسویه:**")
                year, month, day = persian_date_input("تاریخ", "settlement")
                
                if st.form_submit_button("➕ ثبت تسویه", type="primary"):
                    if amount > 0:
                        settlement_date = persian_to_gregorian(year, month, day)
                        db.add_settlement(center_id, amount, settlement_date, description)
                        st.success("✅ تسویه ثبت شد!")
                        st.rerun()
    
    with tab2:
        debts = db.get_center_debts()
        if debts:
            data = []
            for cid, name, sales, comm, ship, settled in debts:
                receivable = sales - comm - ship
                debt = receivable - settled
                data.append({
                    'مرکز': name,
                    'فروش': f"{sales:,.0f}",
                    'کمیسیون+ارسال': f"{comm + ship:,.0f}",
                    'قابل دریافت': f"{receivable:,.0f}",
                    'تسویه شده': f"{settled:,.0f}",
                    'بدهی': f"{debt:,.0f}"
                })
            st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True)
    
    with tab3:
        settlements = db.get_settlements()
        if settlements:
            data = []
            for s in settlements:
                data.append({
                    'ID': s[0],
                    'مرکز': s[1],
                    'مبلغ': f"{s[2]:,.0f}",
                    'تاریخ': gregorian_to_persian(s[3]),
                    'توضیحات': s[4] or '-'
                })
            st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True)


# ==================== حساب نقدی ====================
elif menu == "🏦 حساب نقدی":
    st.markdown("# 🏦 حساب نقدی")
    
    deposits, withdraws, balance = db.get_cash_summary()
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("💵 مجموع واریزها", f"{deposits:,.0f} تومان")
    with col2:
        st.metric("💸 مجموع برداشت‌ها", f"{withdraws:,.0f} تومان")
    with col3:
        st.metric("🏦 موجودی", f"{balance:,.0f} تومان", delta="مثبت" if balance >= 0 else "منفی")
    
    tab1, tab2 = st.tabs(["➕ ثبت تراکنش", "📋 تاریخچه"])
    
    with tab1:
        with st.form("add_cash"):
            trans_type = st.selectbox("نوع تراکنش", options=['deposit', 'withdraw'],
                                     format_func=lambda x: {'deposit': '📥 واریز', 'withdraw': '📤 برداشت'}[x])
            amount = st.number_input("مبلغ (تومان)", min_value=0, value=0, step=10000)
            
            if trans_type == 'deposit':
                source = st.selectbox("از کجا", ["اسنپ شاپ", "دیجی کالا", "نایتو", "فروش حضوری", "سایر"])
            else:
                source = st.selectbox("برای چی", ["خرید کالا", "هزینه ارسال", "هزینه بسته‌بندی", "سایر"])
            
            description = st.text_input("توضیحات")
            
            st.markdown("**تاریخ:**")
            year, month, day = persian_date_input("تاریخ", "cash")
            
            if st.form_submit_button("➕ ثبت", type="primary"):
                if amount > 0:
                    trans_date = persian_to_gregorian(year, month, day)
                    db.add_cash_transaction(trans_type, amount, source, description, trans_date)
                    st.success("✅ ثبت شد!")
                    st.rerun()
    
    with tab2:
        filter_type = st.selectbox("فیلتر", ["all", "deposit", "withdraw"],
                                  format_func=lambda x: {'all': 'همه', 'deposit': 'واریزها', 'withdraw': 'برداشت‌ها'}[x])
        
        transactions = db.get_cash_transactions(filter_type)
        if transactions:
            data = []
            for t in transactions:
                data.append({
                    'ID': t[0],
                    'نوع': '📥 واریز' if t[1] == 'deposit' else '📤 برداشت',
                    'مبلغ': f"{t[2]:,.0f}",
                    'منبع/مقصد': t[3],
                    'توضیحات': t[4] or '-',
                    'تاریخ': gregorian_to_persian(t[5])
                })
            st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True)


# ==================== قیمت‌گذاری ====================
elif menu == "💲 قیمت‌گذاری":
    st.markdown("# 💲 قیمت‌گذاری با نرخ دلار")
    
    centers = db.get_centers()
    
    col1, col2, col3 = st.columns(3)
    with col1:
        new_dollar_rate = st.number_input("💵 نرخ دلار فعلی (تومان)", min_value=1, value=100000, step=1000)
    with col2:
        target_profit = st.number_input("📈 درصد سود مورد نظر", min_value=0.0, max_value=500.0, value=20.0)
    with col3:
        if centers:
            pricing_center = st.selectbox(
                "🏪 مرکز فروش",
                options=[c[0] for c in centers],
                format_func=lambda x: next((c[1] for c in centers if c[0] == x), str(x))
            )
        else:
            pricing_center = None
    
    if st.button("🔄 محاسبه قیمت‌ها", type="primary"):
        if not pricing_center:
            st.error("مرکز فروش انتخاب کنید!")
        else:
            products = db.execute_query("""
                SELECT p.id, p.name, p.color,
                       COALESCE((SELECT buy_price FROM inflows WHERE product_id = p.id ORDER BY inflow_date DESC, id DESC LIMIT 1), 0),
                       COALESCE((SELECT dollar_rate FROM inflows WHERE product_id = p.id ORDER BY inflow_date DESC, id DESC LIMIT 1), 0)
                FROM products p ORDER BY p.name
            """)
            
            if products:
                pricing_data = []
                for pid, name, color, buy_price, old_rate in products:
                    commission_percent = db.get_product_commission(pricing_center, pid) / 100
                    
                    if old_rate and old_rate > 0:
                        new_buy_price = buy_price * (new_dollar_rate / old_rate)
                    else:
                        new_buy_price = buy_price
                    
                    shipping = db.calculate_shipping_cost(pricing_center, new_buy_price * 1.5, 1)
                    
                    if commission_percent < 1:
                        suggested_price = (new_buy_price * (1 + target_profit / 100) + shipping) / (1 - commission_percent)
                    else:
                        suggested_price = new_buy_price * (1 + target_profit / 100) + shipping
                    
                    commission_amount = suggested_price * commission_percent
                    net_profit = suggested_price - new_buy_price - commission_amount - shipping
                    
                    pricing_data.append({
                        'کد': pid,
                        'نام': name,
                        'رنگ': color or '-',
                        'قیمت خرید': f"{buy_price:,.0f}",
                        'نرخ دلار خرید': f"{old_rate:,.0f}" if old_rate else '-',
                        'قیمت خرید جدید': f"{new_buy_price:,.0f}",
                        'کمیسیون %': f"{commission_percent*100:.1f}%",
                        'کمیسیون': f"{commission_amount:,.0f}",
                        'ارسال': f"{shipping:,.0f}",
                        'قیمت فروش پیشنهادی': f"{suggested_price:,.0f}",
                        'سود خالص': f"{net_profit:,.0f}"
                    })
                
                st.dataframe(pd.DataFrame(pricing_data), use_container_width=True, hide_index=True)
    
    st.markdown("""
    ---
    **💡 راهنما:**
    - قیمت خرید جدید = قیمت خرید × (نرخ دلار فعلی ÷ نرخ دلار زمان خرید)
    - قیمت فروش طوری محاسبه شده که بعد از کسر کمیسیون و ارسال، سود مورد نظر باقی بماند
    - اگر نرخ دلار در ورودی ثبت نشده، قیمت جدید = قیمت خرید
    """)


# ==================== گزارشات ====================
elif menu == "📊 گزارشات":
    st.markdown("# 📊 گزارشات")
    
    tab1, tab2, tab3 = st.tabs(["📈 سود و زیان", "📦 موجودی", "🏪 عملکرد مراکز"])
    
    with tab1:
        stats = db.get_dashboard_stats()
        
        st.markdown("### 📈 گزارش سود و زیان")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("💵 فروش", f"{stats['revenue']:,.0f}")
            st.metric("📦 بهای تمام شده", f"{stats['cogs']:,.0f}")
        with col2:
            st.metric("📈 سود ناخالص", f"{stats['revenue'] - stats['cogs']:,.0f}")
            st.metric("💳 کمیسیون", f"{stats['commission']:,.0f}")
        with col3:
            st.metric("🚚 ارسال", f"{stats['shipping']:,.0f}")
            st.metric("✅ سود خالص", f"{stats['profit']:,.0f}")
    
    with tab2:
        st.markdown("### 📦 گزارش موجودی")
        products = db.get_products()
        if products:
            data = []
            total_value = 0
            for p in products:
                inflows = db.execute_query(
                    "SELECT remaining, buy_price FROM inflows WHERE product_id = ? AND remaining > 0",
                    (p[0],)
                )
                value = sum(r[0] * r[1] for r in inflows) if inflows else 0
                total_value += value
                data.append({
                    'کد': p[0],
                    'نام': p[1],
                    'رنگ': p[2] or '-',
                    'موجودی': p[4],
                    'ارزش': f"{value:,.0f}"
                })
            st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True)
            st.info(f"📊 کل ارزش موجودی: {total_value:,.0f} تومان")
    
    with tab3:
        st.markdown("### 🏪 عملکرد مراکز")
        centers = db.get_centers()
        if centers:
            data = []
            for c in centers:
                result = db.execute_query("""
                    SELECT COUNT(*), COALESCE(SUM(quantity), 0), COALESCE(SUM(quantity * sell_price), 0),
                           COALESCE(SUM((quantity * sell_price) - (quantity * cogs_unit) - commission_amount - shipping_cost), 0)
                    FROM outflows WHERE center_id = ? AND is_returned = 0
                """, (c[0],))
                if result and result[0]:
                    data.append({
                        'مرکز': c[1],
                        'تعداد سفارش': result[0][0],
                        'تعداد کالا': result[0][1],
                        'فروش': f"{result[0][2]:,.0f}",
                        'سود': f"{result[0][3]:,.0f}"
                    })
            st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True)


# ==================== مدیریت داده ====================
elif menu == "⚙️ مدیریت داده":
    st.markdown("# ⚙️ مدیریت داده")
    
    st.warning("⚠️ در Streamlit Cloud دیتابیس پایدار نیست! حتماً بکاپ بگیرید.")
    
    st.markdown("### 📥 خروجی اکسل")
    
    export_type = st.selectbox("انتخاب داده", 
                              options=['products', 'inflows', 'outflows', 'settlements', 'cash'],
                              format_func=lambda x: {
                                  'products': '📦 موجودی',
                                  'inflows': '📥 ورودی‌ها',
                                  'outflows': '📤 خروجی‌ها',
                                  'settlements': '💵 تسویه‌ها',
                                  'cash': '🏦 تراکنش‌های نقدی'
                              }[x])
    
    if st.button("📥 دانلود اکسل"):
        if export_type == 'products':
            data = db.get_products()
            df = pd.DataFrame(data, columns=['ID', 'نام', 'رنگ', 'بارکد', 'موجودی'])
        elif export_type == 'inflows':
            data = db.get_inflows()
            df = pd.DataFrame(data, columns=['ID', 'کد کالا', 'نام', 'رنگ', 'تعداد', 'قیمت', 'تاریخ', 'باقیمانده', 'نرخ دلار'])
        elif export_type == 'outflows':
            data = db.get_outflows()
            df = pd.DataFrame(data, columns=['ID', 'کد کالا', 'نام', 'رنگ', 'مرکز', 'تعداد', 'قیمت فروش', 'بهای تمام شده', 'کمیسیون', 'ارسال', 'تاریخ', 'شماره سفارش', 'برگشتی', 'پرداخت', 'center_id'])
        elif export_type == 'settlements':
            data = db.get_settlements()
            df = pd.DataFrame(data, columns=['ID', 'مرکز', 'مبلغ', 'تاریخ', 'توضیحات'])
        elif export_type == 'cash':
            data = db.get_cash_transactions()
            df = pd.DataFrame(data, columns=['ID', 'نوع', 'مبلغ', 'منبع', 'توضیحات', 'تاریخ'])
        
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Sheet1')
        
        st.download_button(
            label="📥 دانلود",
            data=output.getvalue(),
            file_name=f"{export_type}_{jdatetime.date.today().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    
    st.markdown("---")
    st.info(f"📅 تاریخ: {get_persian_today().strftime('%Y/%m/%d')} | نسخه: 2.0 Full")
