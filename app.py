#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
سیستم جامع مدیریت انبار و حسابداری با روش FIFO
نسخه Streamlit برای دیپلوی آنلاین
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
    st.error("لطفاً کتابخانه jdatetime را نصب کنید")

# تنظیمات صفحه
st.set_page_config(
    page_title="سیستم مدیریت انبار",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded"
)

# استایل‌های CSS سفارشی
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Vazirmatn:wght@400;500;700&display=swap');
    
    * {
        font-family: 'Vazirmatn', Tahoma, sans-serif !important;
        direction: rtl;
    }
    
    .stApp {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        background-attachment: fixed;
    }
    
    .main .block-container {
        background: rgba(255, 255, 255, 0.95);
        border-radius: 20px;
        padding: 2rem;
        margin: 1rem;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
    }
    
    h1, h2, h3 {
        color: #1a1a2e !important;
        font-weight: 700 !important;
    }
    
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background: #f8f9fa;
        padding: 10px;
        border-radius: 15px;
    }
    
    .stTabs [data-baseweb="tab"] {
        background: white;
        border-radius: 10px;
        padding: 10px 20px;
        font-weight: 500;
        border: 2px solid transparent;
        transition: all 0.3s ease;
    }
    
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
        color: white !important;
        border-color: #667eea;
    }
    
    .stButton > button {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        border-radius: 10px;
        padding: 0.5rem 1.5rem;
        font-weight: 600;
        transition: all 0.3s ease;
        box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);
    }
    
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(102, 126, 234, 0.6);
    }
    
    .success-btn > button {
        background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%) !important;
        box-shadow: 0 4px 15px rgba(17, 153, 142, 0.4) !important;
    }
    
    .danger-btn > button {
        background: linear-gradient(135deg, #eb3349 0%, #f45c43 100%) !important;
        box-shadow: 0 4px 15px rgba(235, 51, 73, 0.4) !important;
    }
    
    .metric-card {
        background: white;
        border-radius: 15px;
        padding: 1.5rem;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
        border-right: 4px solid #667eea;
        transition: transform 0.3s ease;
    }
    
    .metric-card:hover {
        transform: translateY(-5px);
    }
    
    .metric-value {
        font-size: 2rem;
        font-weight: 700;
        color: #1a1a2e;
    }
    
    .metric-label {
        color: #666;
        font-size: 0.9rem;
    }
    
    .stDataFrame {
        border-radius: 10px;
        overflow: hidden;
    }
    
    div[data-testid="stMetricValue"] {
        font-size: 1.8rem;
        font-weight: 700;
    }
    
    .stSelectbox > div > div {
        border-radius: 10px;
    }
    
    .stTextInput > div > div > input {
        border-radius: 10px;
    }
    
    .sidebar .sidebar-content {
        background: linear-gradient(180deg, #1a1a2e 0%, #16213e 100%);
    }
    
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #1a1a2e 0%, #16213e 100%);
    }
    
    section[data-testid="stSidebar"] .stMarkdown {
        color: white;
    }
</style>
""", unsafe_allow_html=True)


# ==================== توابع کمکی تاریخ ====================
def get_persian_today():
    """دریافت تاریخ امروز شمسی"""
    return jdatetime.date.today()

def gregorian_to_persian(gregorian_str):
    """تبدیل تاریخ میلادی به شمسی"""
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
    """تبدیل تاریخ شمسی به میلادی"""
    try:
        jdate = jdatetime.date(year, month, day)
        gdate = jdate.togregorian()
        return gdate.isoformat()
    except:
        return datetime.date.today().isoformat()

def get_persian_months():
    """لیست ماه‌های شمسی"""
    return ["فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
            "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند"]


# ==================== کلاس مدیریت دیتابیس ====================
class DBManager:
    def __init__(self, db_path=None):
        if db_path:
            self.db_path = db_path
        else:
            self.db_path = "warehouse.db"
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.create_tables()
    
    def create_tables(self):
        """ایجاد جداول دیتابیس"""
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
        
        # درج مراکز فروش پیش‌فرض
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
        
        self.conn.commit()
    
    def execute_query(self, query, params=()):
        """اجرای کوئری و بازگرداندن نتایج"""
        try:
            self.cursor.execute(query, params)
            self.conn.commit()
            return self.cursor.fetchall()
        except sqlite3.Error as e:
            st.error(f"خطای دیتابیس: {e}")
            return None
    
    def get_products(self):
        """دریافت لیست محصولات"""
        return self.execute_query("SELECT id, name, color, barcode, stock FROM products ORDER BY name")
    
    def add_product(self, name, color="", barcode=""):
        """افزودن محصول جدید"""
        self.execute_query(
            "INSERT INTO products (name, color, barcode, stock) VALUES (?, ?, ?, 0)",
            (name, color, barcode)
        )
        return self.cursor.lastrowid
    
    def update_product(self, product_id, name, color, barcode):
        """ویرایش محصول"""
        self.execute_query(
            "UPDATE products SET name=?, color=?, barcode=? WHERE id=?",
            (name, color, barcode, product_id)
        )
    
    def delete_product(self, product_id):
        """حذف محصول"""
        self.execute_query("DELETE FROM products WHERE id=?", (product_id,))
    
    def add_inflow(self, product_id, quantity, buy_price, inflow_date, dollar_rate=0):
        """افزودن ورودی"""
        self.execute_query(
            "INSERT INTO inflows (product_id, quantity, remaining, buy_price, inflow_date, dollar_rate) VALUES (?, ?, ?, ?, ?, ?)",
            (product_id, quantity, quantity, buy_price, inflow_date, dollar_rate)
        )
        self.execute_query(
            "UPDATE products SET stock = stock + ? WHERE id = ?",
            (quantity, product_id)
        )
    
    def get_inflows(self, start_date=None, end_date=None):
        """دریافت لیست ورودی‌ها"""
        query = """
            SELECT i.id, p.id, p.name, p.color, i.quantity, i.buy_price, i.inflow_date, i.remaining, i.dollar_rate
            FROM inflows i 
            JOIN products p ON i.product_id = p.id
        """
        params = []
        if start_date and end_date:
            query += " WHERE i.inflow_date BETWEEN ? AND ?"
            params = [start_date, end_date]
        query += " ORDER BY i.inflow_date DESC"
        return self.execute_query(query, params)
    
    def get_centers(self):
        """دریافت لیست مراکز فروش"""
        return self.execute_query("SELECT id, name, shipping_type, shipping_percent, shipping_min, shipping_max, shipping_fixed FROM sales_centers ORDER BY name")
    
    def add_center(self, name, shipping_type='manual', shipping_percent=0, shipping_min=0, shipping_max=0, shipping_fixed=0):
        """افزودن مرکز فروش"""
        self.execute_query(
            "INSERT INTO sales_centers (name, shipping_type, shipping_percent, shipping_min, shipping_max, shipping_fixed) VALUES (?, ?, ?, ?, ?, ?)",
            (name, shipping_type, shipping_percent, shipping_min, shipping_max, shipping_fixed)
        )
    
    def get_categories(self):
        """دریافت دسته‌بندی‌های کمیسیون"""
        return self.execute_query("SELECT id, name, description FROM commission_categories ORDER BY name")
    
    def add_category(self, name, description=""):
        """افزودن دسته‌بندی کمیسیون"""
        self.execute_query(
            "INSERT INTO commission_categories (name, description) VALUES (?, ?)",
            (name, description)
        )
    
    def get_commissions(self):
        """دریافت تنظیمات کمیسیون"""
        return self.execute_query("""
            SELECT c.id, sc.name, cc.name, c.commission_percent, c.center_id, c.category_id
            FROM commissions c
            JOIN sales_centers sc ON c.center_id = sc.id
            JOIN commission_categories cc ON c.category_id = cc.id
            ORDER BY sc.name, cc.name
        """)
    
    def set_commission(self, center_id, category_id, percent):
        """تنظیم کمیسیون"""
        self.execute_query(
            "INSERT OR REPLACE INTO commissions (center_id, category_id, commission_percent) VALUES (?, ?, ?)",
            (center_id, category_id, percent)
        )
    
    def get_product_category(self, product_id):
        """دریافت دسته‌بندی محصول"""
        result = self.execute_query(
            "SELECT category_id FROM product_categories WHERE product_id = ?",
            (product_id,)
        )
        return result[0][0] if result else None
    
    def set_product_category(self, product_id, category_id):
        """تنظیم دسته‌بندی محصول"""
        self.execute_query(
            "INSERT OR REPLACE INTO product_categories (product_id, category_id) VALUES (?, ?)",
            (product_id, category_id)
        )
    
    def calculate_fifo_cost(self, product_id, quantity):
        """محاسبه بهای تمام شده با روش FIFO"""
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
    
    def add_outflow(self, product_id, center_id, quantity, sell_price, cogs_unit, commission, shipping, outflow_date, order_number=""):
        """ثبت خروجی"""
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
    
    def get_outflows(self, start_date=None, end_date=None):
        """دریافت لیست خروجی‌ها"""
        query = """
            SELECT o.id, p.id, p.name, p.color, sc.name, o.quantity, o.sell_price, o.cogs_unit, 
                   o.commission_amount, o.shipping_cost, o.outflow_date, o.order_number, o.is_returned, o.is_paid
            FROM outflows o
            JOIN products p ON o.product_id = p.id
            JOIN sales_centers sc ON o.center_id = sc.id
        """
        params = []
        if start_date and end_date:
            query += " WHERE o.outflow_date BETWEEN ? AND ?"
            params = [start_date, end_date]
        query += " ORDER BY o.outflow_date DESC"
        return self.execute_query(query, params)
    
    def toggle_outflow_return(self, outflow_id, is_returned):
        """تغییر وضعیت برگشت"""
        self.execute_query(
            "UPDATE outflows SET is_returned = ? WHERE id = ?",
            (1 if is_returned else 0, outflow_id)
        )
    
    def toggle_outflow_paid(self, outflow_id, is_paid):
        """تغییر وضعیت پرداخت"""
        self.execute_query(
            "UPDATE outflows SET is_paid = ? WHERE id = ?",
            (1 if is_paid else 0, outflow_id)
        )
    
    def add_settlement(self, center_id, amount, settlement_date, description=""):
        """ثبت تسویه حساب"""
        self.execute_query(
            "INSERT INTO settlements (center_id, amount, settlement_date, description) VALUES (?, ?, ?, ?)",
            (center_id, amount, settlement_date, description)
        )
    
    def get_settlements(self):
        """دریافت لیست تسویه‌ها"""
        return self.execute_query("""
            SELECT s.id, sc.name, s.amount, s.settlement_date, s.description
            FROM settlements s
            JOIN sales_centers sc ON s.center_id = sc.id
            ORDER BY s.settlement_date DESC
        """)
    
    def add_cash_transaction(self, trans_type, amount, source, description, trans_date):
        """ثبت تراکنش نقدی"""
        self.execute_query(
            "INSERT INTO cash_transactions (transaction_type, amount, source, description, transaction_date) VALUES (?, ?, ?, ?, ?)",
            (trans_type, amount, source, description, trans_date)
        )
    
    def get_cash_transactions(self):
        """دریافت تراکنش‌های نقدی"""
        return self.execute_query(
            "SELECT id, transaction_type, amount, source, description, transaction_date FROM cash_transactions ORDER BY transaction_date DESC, id DESC"
        )
    
    def get_cash_balance(self):
        """محاسبه موجودی نقدی"""
        result = self.execute_query("""
            SELECT 
                COALESCE(SUM(CASE WHEN transaction_type = 'deposit' THEN amount ELSE 0 END), 0) -
                COALESCE(SUM(CASE WHEN transaction_type = 'withdraw' THEN amount ELSE 0 END), 0)
            FROM cash_transactions
        """)
        return result[0][0] if result else 0
    
    def get_dashboard_stats(self):
        """آمار داشبورد"""
        stats = {}
        
        # تعداد محصولات
        result = self.execute_query("SELECT COUNT(*) FROM products")
        stats['total_products'] = result[0][0] if result else 0
        
        # ارزش موجودی
        result = self.execute_query("""
            SELECT SUM(p.stock * COALESCE(
                (SELECT AVG(buy_price) FROM inflows WHERE product_id = p.id AND remaining > 0), 0
            ))
            FROM products p
        """)
        stats['inventory_value'] = result[0][0] if result and result[0][0] else 0
        
        # فروش امروز
        today = datetime.date.today().isoformat()
        result = self.execute_query(
            "SELECT COUNT(*), COALESCE(SUM(quantity * sell_price), 0) FROM outflows WHERE outflow_date = ? AND is_returned = 0",
            (today,)
        )
        stats['today_sales_count'] = result[0][0] if result else 0
        stats['today_sales_amount'] = result[0][1] if result else 0
        
        # سود امروز
        result = self.execute_query("""
            SELECT COALESCE(SUM(
                (quantity * sell_price) - (quantity * cogs_unit) - commission_amount - shipping_cost
            ), 0)
            FROM outflows 
            WHERE outflow_date = ? AND is_returned = 0
        """, (today,))
        stats['today_profit'] = result[0][0] if result else 0
        
        # موجودی نقدی
        stats['cash_balance'] = self.get_cash_balance()
        
        # مطالبات از مراکز
        result = self.execute_query("""
            SELECT COALESCE(SUM(o.quantity * o.sell_price - o.shipping_cost - o.commission_amount), 0) -
                   COALESCE((SELECT SUM(amount) FROM settlements), 0)
            FROM outflows o
            WHERE o.is_returned = 0 AND o.is_paid = 0
        """)
        stats['receivables'] = result[0][0] if result else 0
        
        return stats
    
    def get_database_bytes(self):
        """دریافت بایت‌های دیتابیس برای دانلود"""
        self.conn.commit()
        with open(self.db_path, 'rb') as f:
            return f.read()
    
    def close(self):
        self.conn.close()


# ==================== راه‌اندازی دیتابیس ====================
@st.cache_resource
def get_database():
    return DBManager()

db = get_database()


# ==================== سایدبار ====================
with st.sidebar:
    st.markdown("## 📦 سیستم انبارداری")
    st.markdown("---")
    
    menu = st.radio(
        "منو",
        ["🏠 داشبورد", "📦 مدیریت کالا", "📥 ورودی انبار", "📤 خروجی انبار",
         "🏪 مراکز فروش", "💰 کمیسیون‌ها", "💵 تسویه حساب", "🏦 حساب نقدی",
         "📊 گزارشات", "⚙️ مدیریت داده"],
        label_visibility="collapsed"
    )
    
    st.markdown("---")
    st.markdown("### 💾 مدیریت دیتابیس")
    
    # دانلود دیتابیس
    db_bytes = db.get_database_bytes()
    st.download_button(
        label="📥 دانلود دیتابیس",
        data=db_bytes,
        file_name=f"warehouse_backup_{jdatetime.date.today().strftime('%Y%m%d')}.db",
        mime="application/octet-stream"
    )
    
    # آپلود دیتابیس
    uploaded_db = st.file_uploader("📤 بازیابی دیتابیس", type=['db'], label_visibility="collapsed")
    if uploaded_db:
        if st.button("⚠️ بازیابی", type="secondary"):
            with open("warehouse.db", "wb") as f:
                f.write(uploaded_db.read())
            st.cache_resource.clear()
            st.rerun()


# ==================== صفحات ====================

# داشبورد
if menu == "🏠 داشبورد":
    st.markdown("# 🏠 داشبورد")
    
    stats = db.get_dashboard_stats()
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("📦 تعداد محصولات", f"{stats['total_products']:,}")
    
    with col2:
        st.metric("💰 ارزش موجودی", f"{stats['inventory_value']:,.0f} تومان")
    
    with col3:
        st.metric("🛒 فروش امروز", f"{stats['today_sales_count']} سفارش")
    
    with col4:
        st.metric("📈 سود امروز", f"{stats['today_profit']:,.0f} تومان")
    
    st.markdown("---")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.metric("🏦 موجودی نقدی", f"{stats['cash_balance']:,.0f} تومان")
    
    with col2:
        st.metric("📋 مطالبات", f"{stats['receivables']:,.0f} تومان")
    
    # نمودار موجودی کالاها
    st.markdown("### 📊 موجودی کالاها")
    products = db.get_products()
    if products:
        df = pd.DataFrame(products, columns=['ID', 'نام', 'رنگ', 'بارکد', 'موجودی'])
        df_chart = df[df['موجودی'] > 0][['نام', 'موجودی']].head(10)
        if not df_chart.empty:
            st.bar_chart(df_chart.set_index('نام'))


# مدیریت کالا
elif menu == "📦 مدیریت کالا":
    st.markdown("# 📦 مدیریت کالا")
    
    tab1, tab2 = st.tabs(["➕ افزودن کالا", "📋 لیست کالاها"])
    
    with tab1:
        with st.form("add_product"):
            col1, col2 = st.columns(2)
            with col1:
                name = st.text_input("نام کالا *")
            with col2:
                color = st.text_input("رنگ / مدل")
            
            barcode = st.text_input("بارکد")
            
            if st.form_submit_button("➕ افزودن کالا", type="primary"):
                if name:
                    db.add_product(name, color, barcode)
                    st.success("✅ کالا با موفقیت اضافه شد!")
                    st.rerun()
                else:
                    st.error("نام کالا الزامی است!")
    
    with tab2:
        products = db.get_products()
        if products:
            df = pd.DataFrame(products, columns=['ID', 'نام', 'رنگ', 'بارکد', 'موجودی'])
            
            # فیلتر جستجو
            search = st.text_input("🔍 جستجو در کالاها")
            if search:
                df = df[df['نام'].str.contains(search, case=False, na=False) | 
                       df['رنگ'].str.contains(search, case=False, na=False)]
            
            st.dataframe(df, use_container_width=True, hide_index=True)
            
            # ویرایش/حذف
            st.markdown("### ✏️ ویرایش کالا")
            selected_id = st.selectbox(
                "انتخاب کالا",
                options=[p[0] for p in products],
                format_func=lambda x: next((f"[{p[0]}] {p[1]} - {p[2]}" for p in products if p[0] == x), str(x))
            )
            
            if selected_id:
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
                            if st.form_submit_button("💾 ذخیره تغییرات", type="primary"):
                                db.update_product(selected_id, edit_name, edit_color, edit_barcode)
                                st.success("✅ تغییرات ذخیره شد!")
                                st.rerun()
                        with col2:
                            if st.form_submit_button("🗑️ حذف کالا", type="secondary"):
                                db.delete_product(selected_id)
                                st.success("✅ کالا حذف شد!")
                                st.rerun()
        else:
            st.info("هنوز کالایی ثبت نشده است.")


# ورودی انبار
elif menu == "📥 ورودی انبار":
    st.markdown("# 📥 ورودی انبار")
    
    tab1, tab2 = st.tabs(["➕ ثبت ورودی", "📋 تاریخچه ورودی‌ها"])
    
    with tab1:
        products = db.get_products()
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
                
                # تاریخ شمسی
                st.markdown("**تاریخ ورودی:**")
                today = get_persian_today()
                col1, col2, col3 = st.columns(3)
                with col1:
                    year = st.number_input("سال", min_value=1390, max_value=1450, value=today.year)
                with col2:
                    month = st.selectbox("ماه", options=range(1, 13), format_func=lambda x: get_persian_months()[x-1], index=today.month-1)
                with col3:
                    day = st.number_input("روز", min_value=1, max_value=31, value=today.day)
                
                if st.form_submit_button("➕ ثبت ورودی", type="primary"):
                    if product_id and quantity > 0 and buy_price > 0:
                        inflow_date = persian_to_gregorian(year, month, day)
                        db.add_inflow(product_id, quantity, buy_price, inflow_date, dollar_rate)
                        st.success("✅ ورودی با موفقیت ثبت شد!")
                        st.rerun()
                    else:
                        st.error("لطفاً تمام فیلدهای ضروری را پر کنید!")
    
    with tab2:
        inflows = db.get_inflows()
        if inflows:
            data = []
            for i in inflows:
                data.append({
                    'ID': i[0],
                    'کد کالا': i[1],
                    'نام کالا': i[2],
                    'رنگ': i[3] or '-',
                    'تعداد': i[4],
                    'قیمت خرید': f"{i[5]:,.0f}",
                    'تاریخ': gregorian_to_persian(i[6]),
                    'باقیمانده': i[7],
                    'نرخ دلار': f"{i[8]:,.0f}" if i[8] else '-'
                })
            df = pd.DataFrame(data)
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("هنوز ورودی ثبت نشده است.")


# خروجی انبار
elif menu == "📤 خروجی انبار":
    st.markdown("# 📤 خروجی انبار")
    
    tab1, tab2 = st.tabs(["➕ ثبت خروجی", "📋 تاریخچه خروجی‌ها"])
    
    with tab1:
        products = db.get_products()
        centers = db.get_centers()
        
        if not products:
            st.warning("ابتدا کالا ثبت کنید!")
        elif not centers:
            st.warning("ابتدا مرکز فروش ثبت کنید!")
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
                
                # تاریخ شمسی
                st.markdown("**تاریخ خروجی:**")
                today = get_persian_today()
                col1, col2, col3 = st.columns(3)
                with col1:
                    year = st.number_input("سال", min_value=1390, max_value=1450, value=today.year, key="out_year")
                with col2:
                    month = st.selectbox("ماه", options=range(1, 13), format_func=lambda x: get_persian_months()[x-1], index=today.month-1, key="out_month")
                with col3:
                    day = st.number_input("روز", min_value=1, max_value=31, value=today.day, key="out_day")
                
                # محاسبه بهای تمام شده
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
                        # بررسی موجودی
                        product = next((p for p in products if p[0] == product_id), None)
                        if product and product[4] >= quantity:
                            outflow_date = persian_to_gregorian(year, month, day)
                            db.add_outflow(product_id, center_id, quantity, sell_price, cogs_unit or 0, commission, shipping, outflow_date, order_number)
                            st.success("✅ خروجی با موفقیت ثبت شد!")
                            st.rerun()
                        else:
                            st.error("⚠️ موجودی کافی نیست!")
                    else:
                        st.error("لطفاً تمام فیلدهای ضروری را پر کنید!")
    
    with tab2:
        outflows = db.get_outflows()
        if outflows:
            data = []
            for o in outflows:
                revenue = o[5] * o[6]
                profit = revenue - (o[5] * o[7]) - o[8] - o[9]
                data.append({
                    'ID': o[0],
                    'شماره سفارش': o[11] or '-',
                    'کالا': f"{o[2]} - {o[3]}" if o[3] else o[2],
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
            df = pd.DataFrame(data)
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("هنوز خروجی ثبت نشده است.")


# مراکز فروش
elif menu == "🏪 مراکز فروش":
    st.markdown("# 🏪 مراکز فروش")
    
    tab1, tab2 = st.tabs(["➕ افزودن مرکز", "📋 لیست مراکز"])
    
    with tab1:
        with st.form("add_center"):
            name = st.text_input("نام مرکز فروش *")
            
            shipping_type = st.selectbox("نوع محاسبه ارسال", options=['manual', 'percent', 'fixed'], 
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
                    st.success("✅ مرکز فروش اضافه شد!")
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
            df = pd.DataFrame(data)
            st.dataframe(df, use_container_width=True, hide_index=True)


# کمیسیون‌ها
elif menu == "💰 کمیسیون‌ها":
    st.markdown("# 💰 تنظیمات کمیسیون")
    
    tab1, tab2, tab3 = st.tabs(["📂 دسته‌بندی‌ها", "⚙️ تنظیم کمیسیون", "🏷️ دسته‌بندی محصولات"])
    
    with tab1:
        with st.form("add_category"):
            cat_name = st.text_input("نام دسته‌بندی")
            cat_desc = st.text_input("توضیحات")
            if st.form_submit_button("➕ افزودن"):
                if cat_name:
                    db.add_category(cat_name, cat_desc)
                    st.success("✅ دسته‌بندی اضافه شد!")
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
                center_id = st.selectbox("مرکز فروش", options=[c[0] for c in centers],
                                        format_func=lambda x: next((c[1] for c in centers if c[0] == x), str(x)))
                category_id = st.selectbox("دسته‌بندی", options=[c[0] for c in categories],
                                          format_func=lambda x: next((c[1] for c in categories if c[0] == x), str(x)))
                percent = st.number_input("درصد کمیسیون", min_value=0.0, max_value=100.0, value=0.0)
                
                if st.form_submit_button("💾 ذخیره"):
                    db.set_commission(center_id, category_id, percent)
                    st.success("✅ کمیسیون تنظیم شد!")
                    st.rerun()
            
            commissions = db.get_commissions()
            if commissions:
                df = pd.DataFrame(commissions, columns=['ID', 'مرکز', 'دسته‌بندی', 'درصد', 'center_id', 'category_id'])
                st.dataframe(df[['مرکز', 'دسته‌بندی', 'درصد']], use_container_width=True, hide_index=True)
    
    with tab3:
        products = db.get_products()
        categories = db.get_categories()
        
        if products and categories:
            with st.form("set_product_category"):
                product_id = st.selectbox("محصول", options=[p[0] for p in products],
                                         format_func=lambda x: next((f"[{p[0]}] {p[1]}" for p in products if p[0] == x), str(x)))
                category_id = st.selectbox("دسته‌بندی", options=[c[0] for c in categories],
                                          format_func=lambda x: next((c[1] for c in categories if c[0] == x), str(x)), key="prod_cat")
                
                if st.form_submit_button("💾 ذخیره"):
                    db.set_product_category(product_id, category_id)
                    st.success("✅ دسته‌بندی محصول تنظیم شد!")


# تسویه حساب
elif menu == "💵 تسویه حساب":
    st.markdown("# 💵 تسویه حساب")
    
    tab1, tab2 = st.tabs(["➕ ثبت تسویه", "📋 تاریخچه تسویه‌ها"])
    
    with tab1:
        centers = db.get_centers()
        if centers:
            with st.form("add_settlement"):
                center_id = st.selectbox("مرکز فروش", options=[c[0] for c in centers],
                                        format_func=lambda x: next((c[1] for c in centers if c[0] == x), str(x)))
                amount = st.number_input("مبلغ تسویه (تومان)", min_value=0, value=0, step=10000)
                description = st.text_input("توضیحات")
                
                today = get_persian_today()
                col1, col2, col3 = st.columns(3)
                with col1:
                    year = st.number_input("سال", min_value=1390, max_value=1450, value=today.year, key="set_year")
                with col2:
                    month = st.selectbox("ماه", options=range(1, 13), format_func=lambda x: get_persian_months()[x-1], index=today.month-1, key="set_month")
                with col3:
                    day = st.number_input("روز", min_value=1, max_value=31, value=today.day, key="set_day")
                
                if st.form_submit_button("➕ ثبت تسویه", type="primary"):
                    if amount > 0:
                        settlement_date = persian_to_gregorian(year, month, day)
                        db.add_settlement(center_id, amount, settlement_date, description)
                        st.success("✅ تسویه ثبت شد!")
                        st.rerun()
    
    with tab2:
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
            df = pd.DataFrame(data)
            st.dataframe(df, use_container_width=True, hide_index=True)


# حساب نقدی
elif menu == "🏦 حساب نقدی":
    st.markdown("# 🏦 حساب نقدی")
    
    balance = db.get_cash_balance()
    st.metric("💰 موجودی فعلی", f"{balance:,.0f} تومان")
    
    tab1, tab2 = st.tabs(["➕ ثبت تراکنش", "📋 تاریخچه"])
    
    with tab1:
        with st.form("add_cash"):
            trans_type = st.selectbox("نوع تراکنش", options=['deposit', 'withdraw'],
                                     format_func=lambda x: {'deposit': '📥 واریز', 'withdraw': '📤 برداشت'}[x])
            amount = st.number_input("مبلغ (تومان)", min_value=0, value=0, step=10000)
            source = st.text_input("منبع/مقصد")
            description = st.text_input("توضیحات")
            
            today = get_persian_today()
            col1, col2, col3 = st.columns(3)
            with col1:
                year = st.number_input("سال", min_value=1390, max_value=1450, value=today.year, key="cash_year")
            with col2:
                month = st.selectbox("ماه", options=range(1, 13), format_func=lambda x: get_persian_months()[x-1], index=today.month-1, key="cash_month")
            with col3:
                day = st.number_input("روز", min_value=1, max_value=31, value=today.day, key="cash_day")
            
            if st.form_submit_button("➕ ثبت تراکنش", type="primary"):
                if amount > 0:
                    trans_date = persian_to_gregorian(year, month, day)
                    db.add_cash_transaction(trans_type, amount, source, description, trans_date)
                    st.success("✅ تراکنش ثبت شد!")
                    st.rerun()
    
    with tab2:
        transactions = db.get_cash_transactions()
        if transactions:
            data = []
            for t in transactions:
                data.append({
                    'ID': t[0],
                    'نوع': '📥 واریز' if t[1] == 'deposit' else '📤 برداشت',
                    'مبلغ': f"{t[2]:,.0f}",
                    'منبع/مقصد': t[3] or '-',
                    'توضیحات': t[4] or '-',
                    'تاریخ': gregorian_to_persian(t[5])
                })
            df = pd.DataFrame(data)
            st.dataframe(df, use_container_width=True, hide_index=True)


# گزارشات
elif menu == "📊 گزارشات":
    st.markdown("# 📊 گزارشات")
    
    tab1, tab2, tab3 = st.tabs(["📈 سود و زیان", "📦 موجودی", "🏪 عملکرد مراکز"])
    
    with tab1:
        st.markdown("### 📈 گزارش سود و زیان")
        
        outflows = db.get_outflows()
        if outflows:
            total_revenue = sum(o[5] * o[6] for o in outflows if not o[12])
            total_cogs = sum(o[5] * o[7] for o in outflows if not o[12])
            total_commission = sum(o[8] for o in outflows if not o[12])
            total_shipping = sum(o[9] for o in outflows if not o[12])
            total_profit = total_revenue - total_cogs - total_commission - total_shipping
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("💵 کل فروش", f"{total_revenue:,.0f}")
            with col2:
                st.metric("💰 بهای تمام شده", f"{total_cogs:,.0f}")
            with col3:
                st.metric("📈 سود ناخالص", f"{total_revenue - total_cogs:,.0f}")
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("🏪 کمیسیون", f"{total_commission:,.0f}")
            with col2:
                st.metric("🚚 ارسال", f"{total_shipping:,.0f}")
            with col3:
                st.metric("✅ سود خالص", f"{total_profit:,.0f}")
    
    with tab2:
        st.markdown("### 📦 گزارش موجودی")
        products = db.get_products()
        if products:
            data = []
            total_value = 0
            for p in products:
                # محاسبه ارزش موجودی
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
                    'ارزش موجودی': f"{value:,.0f}"
                })
            
            df = pd.DataFrame(data)
            st.dataframe(df, use_container_width=True, hide_index=True)
            st.metric("📊 کل ارزش موجودی", f"{total_value:,.0f} تومان")
    
    with tab3:
        st.markdown("### 🏪 عملکرد مراکز فروش")
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
            
            if data:
                df = pd.DataFrame(data)
                st.dataframe(df, use_container_width=True, hide_index=True)


# مدیریت داده
elif menu == "⚙️ مدیریت داده":
    st.markdown("# ⚙️ مدیریت داده")
    
    st.warning("⚠️ توجه: در Streamlit Cloud دیتابیس بعد از هر بار restart پاک می‌شود. حتماً از دانلود دیتابیس استفاده کنید!")
    
    tab1, tab2 = st.tabs(["📥 خروجی اکسل", "🔧 تنظیمات"])
    
    with tab1:
        st.markdown("### 📥 خروجی اکسل")
        
        export_type = st.selectbox("انتخاب داده", options=['products', 'inflows', 'outflows', 'settlements'],
                                  format_func=lambda x: {
                                      'products': '📦 موجودی انبار',
                                      'inflows': '📥 ورودی‌ها',
                                      'outflows': '📤 خروجی‌ها',
                                      'settlements': '💵 تسویه‌ها'
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
                df = pd.DataFrame(data, columns=['ID', 'کد کالا', 'نام', 'رنگ', 'مرکز', 'تعداد', 'قیمت فروش', 'بهای تمام شده', 'کمیسیون', 'ارسال', 'تاریخ', 'شماره سفارش', 'برگشتی', 'پرداخت'])
            elif export_type == 'settlements':
                data = db.get_settlements()
                df = pd.DataFrame(data, columns=['ID', 'مرکز', 'مبلغ', 'تاریخ', 'توضیحات'])
            
            # تبدیل به اکسل
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='Sheet1')
            
            st.download_button(
                label="📥 دانلود فایل اکسل",
                data=output.getvalue(),
                file_name=f"{export_type}_{jdatetime.date.today().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
    
    with tab2:
        st.markdown("### 🔧 تنظیمات")
        st.info("نسخه: 2.0 Streamlit Edition")
        st.info(f"تاریخ امروز: {get_persian_today().strftime('%Y/%m/%d')}")
