"""
سیستم جامع مدیریت انبار و حسابداری - نسخه وب
Warehouse Management System - Web Version
"""

import streamlit as st
import sqlite3
import pandas as pd
import hashlib
import os
import tempfile
from datetime import datetime, timedelta
import jdatetime
import plotly.express as px
import plotly.graph_objects as go

# ==================== تنظیمات صفحه ====================
st.set_page_config(
    page_title="سیستم مدیریت انبار",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==================== استایل‌های CSS ====================
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Vazirmatn:wght@400;700&display=swap');
    
    * {
        font-family: 'Vazirmatn', 'Tahoma', sans-serif !important;
    }
    
    .main-header {
        text-align: center;
        color: #1976D2;
        padding: 1rem;
        border-bottom: 3px solid #1976D2;
        margin-bottom: 2rem;
    }
    
    .metric-card {
        background: white;
        padding: 1.5rem;
        border-radius: 10px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        text-align: center;
        border-right: 5px solid;
    }
    
    .metric-title {
        font-size: 0.9rem;
        color: #666;
        margin-bottom: 0.5rem;
    }
    
    .metric-value {
        font-size: 1.5rem;
        font-weight: bold;
    }
    
    .stButton > button {
        width: 100%;
    }
    
    .success-box {
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        padding: 1rem;
        border-radius: 5px;
        color: #155724;
    }
    
    .error-box {
        background-color: #f8d7da;
        border: 1px solid #f5c6cb;
        padding: 1rem;
        border-radius: 5px;
        color: #721c24;
    }
    
    .rtl {
        direction: rtl;
        text-align: right;
    }
    
    div[data-testid="stSidebar"] {
        direction: rtl;
    }
    
    .cash-flow-card {
        padding: 1rem;
        border-radius: 10px;
        text-align: center;
        margin: 0.5rem;
    }
    
    .deposit-card {
        background: linear-gradient(135deg, #4CAF50 0%, #45a049 100%);
        color: white;
    }
    
    .withdraw-card {
        background: linear-gradient(135deg, #f44336 0%, #e53935 100%);
        color: white;
    }
    
    .balance-card {
        background: linear-gradient(135deg, #2196F3 0%, #1976D2 100%);
        color: white;
    }
</style>
""", unsafe_allow_html=True)

# ==================== توابع کمکی تاریخ ====================
def gregorian_to_persian(greg_date):
    """تبدیل تاریخ میلادی به شمسی"""
    if not greg_date:
        return ""
    try:
        if isinstance(greg_date, str):
            date_obj = datetime.strptime(greg_date, "%Y-%m-%d")
        else:
            date_obj = greg_date
        jdate = jdatetime.date.fromgregorian(date=date_obj.date() if hasattr(date_obj, 'date') else date_obj)
        return jdate.strftime("%Y/%m/%d")
    except:
        return str(greg_date)

def persian_to_gregorian(persian_date):
    """تبدیل تاریخ شمسی به میلادی"""
    try:
        parts = persian_date.replace("/", "-").split("-")
        jdate = jdatetime.date(int(parts[0]), int(parts[1]), int(parts[2]))
        gdate = jdate.togregorian()
        return gdate.strftime("%Y-%m-%d")
    except:
        return datetime.now().strftime("%Y-%m-%d")

def get_today_persian():
    """دریافت تاریخ امروز شمسی"""
    return jdatetime.date.today()

def get_today_gregorian():
    """دریافت تاریخ امروز میلادی"""
    return datetime.now().strftime("%Y-%m-%d")

# ==================== مدیریت دیتابیس ====================
def get_db_path():
    """مسیر دیتابیس"""
    return "warehouse_web.db"

def get_connection():
    """اتصال به دیتابیس"""
    conn = sqlite3.connect(get_db_path(), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_database():
    """ایجاد جداول دیتابیس"""
    conn = get_connection()
    c = conn.cursor()
    
    # جدول کاربران
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'viewer',
            full_name TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # جدول محصولات
    c.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            color TEXT DEFAULT '',
            barcode TEXT DEFAULT '',
            stock REAL DEFAULT 0
        )
    ''')
    
    # جدول ورودی‌ها
    c.execute('''
        CREATE TABLE IF NOT EXISTS inflows (
            id INTEGER PRIMARY KEY,
            product_id INTEGER,
            quantity REAL NOT NULL,
            remaining_quantity REAL NOT NULL,
            buy_price REAL NOT NULL,
            dollar_rate REAL DEFAULT 0,
            inflow_date TEXT NOT NULL,
            created_by INTEGER,
            FOREIGN KEY (product_id) REFERENCES products(id),
            FOREIGN KEY (created_by) REFERENCES users(id)
        )
    ''')
    
    # جدول مراکز فروش
    c.execute('''
        CREATE TABLE IF NOT EXISTS sales_centers (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            commission_percent REAL DEFAULT 7,
            shipping_type TEXT DEFAULT 'manual',
            shipping_percent REAL DEFAULT 0,
            shipping_min REAL DEFAULT 0,
            shipping_max REAL DEFAULT 0,
            shipping_fixed REAL DEFAULT 0
        )
    ''')
    
    # جدول دسته‌بندی کمیسیون
    c.execute('''
        CREATE TABLE IF NOT EXISTS commission_categories (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            description TEXT DEFAULT ''
        )
    ''')
    
    # جدول کمیسیون‌ها
    c.execute('''
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
    
    # جدول ارتباط محصول و دسته‌بندی
    c.execute('''
        CREATE TABLE IF NOT EXISTS product_categories (
            product_id INTEGER PRIMARY KEY,
            category_id INTEGER,
            FOREIGN KEY (product_id) REFERENCES products(id),
            FOREIGN KEY (category_id) REFERENCES commission_categories(id)
        )
    ''')
    
    # جدول خروجی‌ها
    c.execute('''
        CREATE TABLE IF NOT EXISTS outflows (
            id INTEGER PRIMARY KEY,
            product_id INTEGER,
            center_id INTEGER,
            quantity REAL NOT NULL,
            sell_price REAL NOT NULL,
            cogs_unit REAL DEFAULT 0,
            commission_amount REAL DEFAULT 0,
            shipping_cost REAL DEFAULT 0,
            outflow_date TEXT NOT NULL,
            order_number TEXT DEFAULT '',
            is_returned INTEGER DEFAULT 0,
            is_paid INTEGER DEFAULT 0,
            created_by INTEGER,
            FOREIGN KEY (product_id) REFERENCES products(id),
            FOREIGN KEY (center_id) REFERENCES sales_centers(id),
            FOREIGN KEY (created_by) REFERENCES users(id)
        )
    ''')
    
    # جدول تسویه‌ها
    c.execute('''
        CREATE TABLE IF NOT EXISTS settlements (
            id INTEGER PRIMARY KEY,
            center_id INTEGER,
            amount REAL NOT NULL,
            settlement_date TEXT NOT NULL,
            description TEXT DEFAULT '',
            created_by INTEGER,
            FOREIGN KEY (center_id) REFERENCES sales_centers(id),
            FOREIGN KEY (created_by) REFERENCES users(id)
        )
    ''')
    
    # جدول تراکنش‌های نقدی
    c.execute('''
        CREATE TABLE IF NOT EXISTS cash_transactions (
            id INTEGER PRIMARY KEY,
            transaction_type TEXT NOT NULL,
            amount REAL NOT NULL,
            source TEXT DEFAULT '',
            description TEXT DEFAULT '',
            transaction_date TEXT NOT NULL,
            created_by INTEGER,
            FOREIGN KEY (created_by) REFERENCES users(id)
        )
    ''')
    
    # ایجاد کاربر ادمین پیش‌فرض
    admin_password = hashlib.sha256("admin123".encode()).hexdigest()
    try:
        c.execute("""
            INSERT OR IGNORE INTO users (username, password, role, full_name) 
            VALUES (?, ?, ?, ?)
        """, ("admin", admin_password, "admin", "مدیر سیستم"))
    except:
        pass
    
    # ایجاد مراکز فروش پیش‌فرض
    default_centers = [
        ("اسنپ شاپ", 7),
        ("دیجی کالا", 10),
        ("نایتو", 5),
    ]
    for name, commission in default_centers:
        try:
            c.execute("INSERT OR IGNORE INTO sales_centers (name, commission_percent) VALUES (?, ?)", 
                     (name, commission))
        except:
            pass
    
    conn.commit()
    conn.close()

# ==================== توابع احراز هویت ====================
def hash_password(password):
    """هش کردن رمز عبور"""
    return hashlib.sha256(password.encode()).hexdigest()

def verify_user(username, password):
    """تایید کاربر"""
    conn = get_connection()
    c = conn.cursor()
    hashed = hash_password(password)
    c.execute("SELECT * FROM users WHERE username = ? AND password = ? AND is_active = 1", 
              (username, hashed))
    user = c.fetchone()
    conn.close()
    return dict(user) if user else None

def get_user_permissions(role):
    """دسترسی‌های هر نقش"""
    permissions = {
        "admin": {
            "dashboard": True,
            "products": True,
            "inflows": True,
            "outflows": True,
            "centers": True,
            "commission": True,
            "settlements": True,
            "cash_account": True,
            "pricing": True,
            "reports": True,
            "users": True,
            "data_management": True,
        },
        "warehouse": {
            "dashboard": True,
            "products": True,
            "inflows": True,
            "outflows": True,
            "centers": False,
            "commission": False,
            "settlements": False,
            "cash_account": False,
            "pricing": False,
            "reports": True,
            "users": False,
            "data_management": False,
        },
        "viewer": {
            "dashboard": True,
            "products": False,
            "inflows": False,
            "outflows": False,
            "centers": False,
            "commission": False,
            "settlements": False,
            "cash_account": False,
            "pricing": False,
            "reports": True,
            "users": False,
            "data_management": False,
        }
    }
    return permissions.get(role, permissions["viewer"])

# ==================== صفحه لاگین ====================
def login_page():
    """صفحه ورود"""
    st.markdown("<h1 style='text-align: center;'>📦 سیستم مدیریت انبار</h1>", unsafe_allow_html=True)
    st.markdown("<h3 style='text-align: center; color: #666;'>ورود به سیستم</h3>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        with st.form("login_form"):
            username = st.text_input("نام کاربری", placeholder="نام کاربری خود را وارد کنید")
            password = st.text_input("رمز عبور", type="password", placeholder="رمز عبور")
            submit = st.form_submit_button("🔐 ورود", use_container_width=True)
            
            if submit:
                if username and password:
                    user = verify_user(username, password)
                    if user:
                        st.session_state.logged_in = True
                        st.session_state.user = user
                        st.session_state.permissions = get_user_permissions(user['role'])
                        st.success("ورود موفقیت‌آمیز!")
                        st.rerun()
                    else:
                        st.error("نام کاربری یا رمز عبور اشتباه است!")
                else:
                    st.warning("لطفاً نام کاربری و رمز عبور را وارد کنید.")
        
        st.markdown("---")
        st.markdown("""
        <div style='text-align: center; color: #888;'>
            <small>نسخه ۱.۰ | طراحی شده برای نایتو</small>
        </div>
        """, unsafe_allow_html=True)

# ==================== داشبورد ====================
def dashboard_page():
    """صفحه داشبورد"""
    st.markdown("<h2 style='text-align: center; color: #1976D2;'>📊 داشبورد مدیریتی</h2>", unsafe_allow_html=True)
    
    conn = get_connection()
    
    # آمار کلی فروش
    stats = conn.execute("""
        SELECT 
            COALESCE(SUM(quantity * sell_price), 0) as revenue,
            COALESCE(SUM(quantity * cogs_unit), 0) as cogs,
            COALESCE(SUM(commission_amount), 0) as commission,
            COALESCE(SUM(shipping_cost), 0) as shipping
        FROM outflows WHERE is_returned = 0
    """).fetchone()
    
    revenue = stats['revenue'] or 0
    cogs = stats['cogs'] or 0
    commission = stats['commission'] or 0
    shipping = stats['shipping'] or 0
    net_profit = revenue - cogs - commission - shipping
    
    # موجودی انبار
    stock_stats = conn.execute("SELECT COALESCE(SUM(stock), 0) as total FROM products").fetchone()
    total_stock = stock_stats['total'] or 0
    
    # ارزش دارایی
    inventory_value = conn.execute(
        "SELECT COALESCE(SUM(remaining_quantity * buy_price), 0) as value FROM inflows"
    ).fetchone()['value'] or 0
    
    # تسویه شده
    settlements_total = conn.execute("""
        SELECT COALESCE(SUM(quantity * sell_price - commission_amount - shipping_cost), 0) as total
        FROM outflows WHERE is_paid = 1 AND is_returned = 0
    """).fetchone()['total'] or 0
    
    # کارت‌های آماری
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("💰 درآمد کل فروش", f"{int(revenue):,} تومان")
    with col2:
        st.metric("📦 بهای تمام شده", f"{int(cogs):,} تومان")
    with col3:
        st.metric("💳 کمیسیون پرداختی", f"{int(commission):,} تومان")
    with col4:
        st.metric("🚚 هزینه ارسال", f"{int(shipping):,} تومان")
    
    col5, col6, col7 = st.columns(3)
    
    with col5:
        delta_color = "normal" if net_profit >= 0 else "inverse"
        st.metric("📈 سود خالص", f"{int(net_profit):,} تومان", delta=None)
    with col6:
        st.metric("🏪 موجودی کل انبار", f"{int(total_stock):,} واحد")
    with col7:
        st.metric("✅ مجموع تسویه شده", f"{int(settlements_total):,} تومان")
    
    st.markdown("---")
    
    # بخش موجودی حساب
    st.markdown("### 🏦 موجودی حساب")
    
    deposits = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) as total FROM cash_transactions WHERE transaction_type = 'deposit'"
    ).fetchone()['total'] or 0
    
    withdraws = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) as total FROM cash_transactions WHERE transaction_type = 'withdraw'"
    ).fetchone()['total'] or 0
    
    cash_balance = deposits - withdraws
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("💵 مجموع واریزها", f"{int(deposits):,} تومان")
    with col2:
        st.metric("💸 مجموع برداشت‌ها", f"{int(withdraws):,} تومان")
    with col3:
        st.metric("💰 موجودی نقدی", f"{int(cash_balance):,} تومان")
    with col4:
        st.metric("💎 ارزش کل دارایی", f"{int(inventory_value):,} تومان")
    
    st.markdown("---")
    
    # جدول بدهی مراکز
    st.markdown("### 📋 بدهی مراکز فروش")
    
    debt_query = """
        SELECT 
            sc.name as center_name,
            COALESCE(SUM(o.quantity * o.sell_price), 0) as total_sales,
            COALESCE(SUM(o.commission_amount), 0) as total_commission,
            COALESCE(SUM(o.shipping_cost), 0) as total_shipping,
            COALESCE((SELECT SUM(amount) FROM settlements WHERE center_id = sc.id), 0) as settled
        FROM sales_centers sc
        LEFT JOIN outflows o ON sc.id = o.center_id AND o.is_returned = 0 AND o.is_paid = 0
        GROUP BY sc.id
    """
    
    debt_data = conn.execute(debt_query).fetchall()
    
    if debt_data:
        debt_df = []
        for row in debt_data:
            sales = row['total_sales'] or 0
            commission = row['total_commission'] or 0
            shipping = row['total_shipping'] or 0
            settled = row['settled'] or 0
            receivable = sales - commission - shipping
            debt = receivable - settled
            
            debt_df.append({
                "مرکز فروش": row['center_name'],
                "کل فروش": f"{int(sales):,}",
                "کمیسیون+ارسال": f"{int(commission + shipping):,}",
                "قابل دریافت": f"{int(receivable):,}",
                "تسویه شده": f"{int(settled):,}",
                "بدهی": f"{int(debt):,}"
            })
        
        st.dataframe(pd.DataFrame(debt_df), use_container_width=True, hide_index=True)
    
    conn.close()

# ==================== مدیریت کالا ====================
def products_page():
    """صفحه مدیریت کالا"""
    st.markdown("### 📝 مدیریت کالا و موجودی")
    
    conn = get_connection()
    
    tab1, tab2 = st.tabs(["📋 لیست کالاها", "➕ افزودن کالا"])
    
    with tab1:
        # جستجو
        search = st.text_input("🔍 جستجو", placeholder="نام، کد یا بارکد...")
        
        if search:
            products = conn.execute("""
                SELECT id, name, color, barcode, stock FROM products 
                WHERE name LIKE ? OR id LIKE ? OR barcode LIKE ?
                ORDER BY name
            """, (f"%{search}%", f"%{search}%", f"%{search}%")).fetchall()
        else:
            products = conn.execute("SELECT id, name, color, barcode, stock FROM products ORDER BY name").fetchall()
        
        if products:
            df = pd.DataFrame([dict(p) for p in products])
            df.columns = ["کد کالا", "نام کالا", "رنگ", "بارکد", "موجودی"]
            
            st.dataframe(df, use_container_width=True, hide_index=True)
            
            # ویرایش/حذف
            st.markdown("---")
            col1, col2 = st.columns(2)
            
            with col1:
                product_id = st.number_input("کد کالا برای ویرایش/حذف", min_value=1, step=1)
            
            with col2:
                col_edit, col_delete = st.columns(2)
                with col_edit:
                    if st.button("✏️ ویرایش", use_container_width=True):
                        st.session_state.edit_product_id = product_id
                
                with col_delete:
                    if st.button("🗑️ حذف", use_container_width=True, type="primary"):
                        conn.execute("DELETE FROM products WHERE id = ?", (product_id,))
                        conn.commit()
                        st.success("کالا حذف شد!")
                        st.rerun()
            
            # فرم ویرایش
            if 'edit_product_id' in st.session_state:
                product = conn.execute(
                    "SELECT * FROM products WHERE id = ?", 
                    (st.session_state.edit_product_id,)
                ).fetchone()
                
                if product:
                    st.markdown("#### ویرایش کالا")
                    with st.form("edit_product_form"):
                        new_name = st.text_input("نام کالا", value=product['name'])
                        new_color = st.text_input("رنگ", value=product['color'] or "")
                        new_barcode = st.text_input("بارکد", value=product['barcode'] or "")
                        
                        if st.form_submit_button("💾 ذخیره تغییرات"):
                            conn.execute("""
                                UPDATE products SET name = ?, color = ?, barcode = ? WHERE id = ?
                            """, (new_name, new_color, new_barcode, st.session_state.edit_product_id))
                            conn.commit()
                            del st.session_state.edit_product_id
                            st.success("کالا ویرایش شد!")
                            st.rerun()
        else:
            st.info("کالایی یافت نشد.")
    
    with tab2:
        with st.form("add_product_form"):
            st.markdown("#### افزودن کالای جدید")
            
            col1, col2 = st.columns(2)
            with col1:
                name = st.text_input("نام کالا *")
                color = st.text_input("رنگ")
            with col2:
                barcode = st.text_input("بارکد")
            
            if st.form_submit_button("➕ افزودن کالا", use_container_width=True):
                if name:
                    try:
                        conn.execute(
                            "INSERT INTO products (name, color, barcode, stock) VALUES (?, ?, ?, 0)",
                            (name, color, barcode)
                        )
                        conn.commit()
                        st.success(f"کالای «{name}» با موفقیت اضافه شد!")
                    except Exception as e:
                        st.error(f"خطا: {e}")
                else:
                    st.warning("نام کالا الزامی است!")
    
    conn.close()

# ==================== ورودی انبار ====================
def inflows_page():
    """صفحه ورودی انبار"""
    st.markdown("### 📥 ورودی انبار")
    
    conn = get_connection()
    
    tab1, tab2 = st.tabs(["➕ ثبت ورودی", "📋 تاریخچه"])
    
    with tab1:
        products = conn.execute("SELECT id, name, color FROM products ORDER BY name").fetchall()
        
        if not products:
            st.warning("ابتدا کالا اضافه کنید!")
        else:
            with st.form("inflow_form"):
                col1, col2 = st.columns(2)
                
                with col1:
                    product_options = {f"[{p['id']}] {p['name']} - {p['color'] or 'بدون رنگ'}": p['id'] for p in products}
                    selected_product = st.selectbox("کالا *", options=list(product_options.keys()))
                    product_id = product_options[selected_product]
                    
                    quantity = st.number_input("تعداد *", min_value=0.01, step=1.0)
                
                with col2:
                    buy_price = st.number_input("قیمت خرید (تومان) *", min_value=0, step=1000)
                    dollar_rate = st.number_input("نرخ دلار (تومان)", min_value=0, step=1000)
                
                today = get_today_persian()
                inflow_date = st.date_input("تاریخ ورودی", value=datetime.now())
                
                if st.form_submit_button("📥 ثبت ورودی", use_container_width=True, type="primary"):
                    if quantity > 0 and buy_price > 0:
                        # ثبت ورودی
                        conn.execute("""
                            INSERT INTO inflows (product_id, quantity, remaining_quantity, buy_price, dollar_rate, inflow_date, created_by)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        """, (product_id, quantity, quantity, buy_price, dollar_rate, 
                              inflow_date.strftime("%Y-%m-%d"), st.session_state.user['id']))
                        
                        # به‌روزرسانی موجودی
                        conn.execute("UPDATE products SET stock = stock + ? WHERE id = ?", (quantity, product_id))
                        conn.commit()
                        
                        st.success(f"✅ ورودی {quantity} عدد با قیمت {int(buy_price):,} تومان ثبت شد!")
                    else:
                        st.warning("تعداد و قیمت خرید الزامی است!")
    
    with tab2:
        inflows = conn.execute("""
            SELECT i.id, i.inflow_date, p.id as pid, p.name, p.color, i.quantity, i.buy_price, i.remaining_quantity, i.dollar_rate
            FROM inflows i
            JOIN products p ON i.product_id = p.id
            ORDER BY i.inflow_date DESC, i.id DESC
            LIMIT 100
        """).fetchall()
        
        if inflows:
            df = []
            for i in inflows:
                df.append({
                    "تاریخ": gregorian_to_persian(i['inflow_date']),
                    "کد": i['pid'],
                    "کالا": i['name'],
                    "رنگ": i['color'] or "-",
                    "تعداد": i['quantity'],
                    "قیمت واحد": f"{int(i['buy_price']):,}",
                    "باقی‌مانده": i['remaining_quantity'],
                    "نرخ دلار": f"{int(i['dollar_rate']):,}" if i['dollar_rate'] else "-"
                })
            
            st.dataframe(pd.DataFrame(df), use_container_width=True, hide_index=True)
        else:
            st.info("ورودی ثبت نشده است.")
    
    conn.close()

# ==================== خروجی انبار ====================
def outflows_page():
    """صفحه خروجی انبار"""
    st.markdown("### 📤 خروجی انبار")
    
    conn = get_connection()
    
    tab1, tab2 = st.tabs(["➕ ثبت خروجی", "📋 تاریخچه"])
    
    with tab1:
        products = conn.execute("SELECT id, name, color, stock FROM products WHERE stock > 0 ORDER BY name").fetchall()
        centers = conn.execute("SELECT id, name, commission_percent FROM sales_centers").fetchall()
        
        if not products:
            st.warning("موجودی انبار خالی است!")
        elif not centers:
            st.warning("ابتدا مرکز فروش اضافه کنید!")
        else:
            with st.form("outflow_form"):
                col1, col2 = st.columns(2)
                
                with col1:
                    product_options = {f"[{p['id']}] {p['name']} - {p['color'] or 'بدون رنگ'} (موجودی: {p['stock']})": p['id'] for p in products}
                    selected_product = st.selectbox("کالا *", options=list(product_options.keys()))
                    product_id = product_options[selected_product]
                    
                    selected_product_data = next(p for p in products if p['id'] == product_id)
                    
                    center_options = {c['name']: c['id'] for c in centers}
                    selected_center = st.selectbox("مرکز فروش *", options=list(center_options.keys()))
                    center_id = center_options[selected_center]
                    
                    selected_center_data = next(c for c in centers if c['id'] == center_id)
                
                with col2:
                    quantity = st.number_input("تعداد *", min_value=0.01, max_value=float(selected_product_data['stock']), step=1.0)
                    sell_price = st.number_input("قیمت فروش (تومان) *", min_value=0, step=1000)
                    shipping_cost = st.number_input("هزینه ارسال (تومان)", min_value=0, step=1000)
                
                order_number = st.text_input("شماره سفارش (اختیاری)")
                outflow_date = st.date_input("تاریخ خروج", value=datetime.now())
                
                # نمایش محاسبات
                commission_percent = selected_center_data['commission_percent']
                commission_amount = sell_price * (commission_percent / 100)
                
                st.info(f"💳 کمیسیون ({commission_percent}%): {int(commission_amount):,} تومان")
                
                if st.form_submit_button("📤 ثبت خروجی", use_container_width=True, type="primary"):
                    if quantity > 0 and sell_price > 0:
                        # محاسبه COGS به روش FIFO
                        remaining_qty = quantity
                        total_cogs = 0
                        
                        batches = conn.execute("""
                            SELECT id, remaining_quantity, buy_price FROM inflows 
                            WHERE product_id = ? AND remaining_quantity > 0 
                            ORDER BY inflow_date ASC
                        """, (product_id,)).fetchall()
                        
                        for batch in batches:
                            if remaining_qty <= 0:
                                break
                            
                            use_qty = min(remaining_qty, batch['remaining_quantity'])
                            total_cogs += use_qty * batch['buy_price']
                            remaining_qty -= use_qty
                            
                            conn.execute(
                                "UPDATE inflows SET remaining_quantity = remaining_quantity - ? WHERE id = ?",
                                (use_qty, batch['id'])
                            )
                        
                        cogs_unit = total_cogs / quantity if quantity > 0 else 0
                        
                        # ثبت خروجی
                        conn.execute("""
                            INSERT INTO outflows (product_id, center_id, quantity, sell_price, cogs_unit, 
                                                 commission_amount, shipping_cost, outflow_date, order_number, created_by)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (product_id, center_id, quantity, sell_price, cogs_unit, 
                              commission_amount, shipping_cost, outflow_date.strftime("%Y-%m-%d"), 
                              order_number, st.session_state.user['id']))
                        
                        # به‌روزرسانی موجودی
                        conn.execute("UPDATE products SET stock = stock - ? WHERE id = ?", (quantity, product_id))
                        conn.commit()
                        
                        revenue = quantity * sell_price
                        profit = revenue - total_cogs - commission_amount - shipping_cost
                        
                        st.success(f"""
                        ✅ خروجی ثبت شد!
                        - درآمد: {int(revenue):,} تومان
                        - بهای تمام شده: {int(total_cogs):,} تومان
                        - کمیسیون: {int(commission_amount):,} تومان
                        - سود خالص: {int(profit):,} تومان
                        """)
                    else:
                        st.warning("تعداد و قیمت فروش الزامی است!")
    
    with tab2:
        # فیلترها
        col1, col2, col3 = st.columns(3)
        with col1:
            search = st.text_input("🔍 جستجو", key="outflow_search")
        with col2:
            filter_paid = st.selectbox("وضعیت پرداخت", ["همه", "پرداخت شده", "در انتظار"])
        with col3:
            filter_returned = st.selectbox("وضعیت", ["همه", "تحویل شده", "برگشت خورده"])
        
        query = """
            SELECT o.id, o.outflow_date, o.order_number, p.id as pid, p.name, sc.name as center,
                   o.quantity, o.sell_price, o.cogs_unit, o.commission_amount, o.shipping_cost,
                   o.is_returned, o.is_paid
            FROM outflows o
            JOIN products p ON o.product_id = p.id
            JOIN sales_centers sc ON o.center_id = sc.id
            WHERE 1=1
        """
        params = []
        
        if search:
            query += " AND (p.name LIKE ? OR o.order_number LIKE ?)"
            params.extend([f"%{search}%", f"%{search}%"])
        
        if filter_paid == "پرداخت شده":
            query += " AND o.is_paid = 1"
        elif filter_paid == "در انتظار":
            query += " AND o.is_paid = 0"
        
        if filter_returned == "تحویل شده":
            query += " AND o.is_returned = 0"
        elif filter_returned == "برگشت خورده":
            query += " AND o.is_returned = 1"
        
        query += " ORDER BY o.outflow_date DESC, o.id DESC LIMIT 100"
        
        outflows = conn.execute(query, params).fetchall()
        
        if outflows:
            df = []
            for o in outflows:
                revenue = o['quantity'] * o['sell_price']
                profit = revenue - (o['quantity'] * o['cogs_unit']) - o['commission_amount'] - o['shipping_cost']
                
                df.append({
                    "ID": o['id'],
                    "تاریخ": gregorian_to_persian(o['outflow_date']),
                    "سفارش": o['order_number'] or "-",
                    "کالا": o['name'],
                    "مرکز": o['center'],
                    "تعداد": o['quantity'],
                    "قیمت فروش": f"{int(o['sell_price']):,}",
                    "کمیسیون": f"{int(o['commission_amount']):,}",
                    "ارسال": f"{int(o['shipping_cost']):,}",
                    "سود": f"{int(profit):,}",
                    "وضعیت": "برگشتی" if o['is_returned'] else "تحویل",
                    "پرداخت": "✅" if o['is_paid'] else "⏳"
                })
            
            st.dataframe(pd.DataFrame(df), use_container_width=True, hide_index=True)
            
            # تغییر وضعیت پرداخت
            st.markdown("---")
            col1, col2, col3 = st.columns(3)
            
            with col1:
                outflow_id = st.number_input("ID خروجی", min_value=1, step=1, key="outflow_id_action")
            
            with col2:
                if st.button("✅ پرداخت شد", use_container_width=True):
                    conn.execute("UPDATE outflows SET is_paid = 1 WHERE id = ?", (outflow_id,))
                    conn.commit()
                    st.success("وضعیت پرداخت تغییر کرد!")
                    st.rerun()
            
            with col3:
                if st.button("↩️ برگشت سفارش", use_container_width=True):
                    # برگرداندن موجودی
                    outflow = conn.execute("SELECT product_id, quantity, cogs_unit FROM outflows WHERE id = ?", (outflow_id,)).fetchone()
                    if outflow:
                        conn.execute("UPDATE products SET stock = stock + ? WHERE id = ?", 
                                   (outflow['quantity'], outflow['product_id']))
                        conn.execute("UPDATE outflows SET is_returned = 1 WHERE id = ?", (outflow_id,))
                        conn.commit()
                        st.success("سفارش برگشت خورد و موجودی برگردانده شد!")
                        st.rerun()
        else:
            st.info("خروجی ثبت نشده است.")
    
    conn.close()

# ==================== مراکز فروش ====================
def centers_page():
    """صفحه مراکز فروش"""
    st.markdown("### 🏪 مراکز فروش")
    
    conn = get_connection()
    
    tab1, tab2 = st.tabs(["📋 لیست مراکز", "➕ افزودن مرکز"])
    
    with tab1:
        centers = conn.execute("SELECT * FROM sales_centers").fetchall()
        
        if centers:
            df = []
            for c in centers:
                df.append({
                    "ID": c['id'],
                    "نام مرکز": c['name'],
                    "کمیسیون پیش‌فرض (%)": c['commission_percent'],
                })
            
            st.dataframe(pd.DataFrame(df), use_container_width=True, hide_index=True)
            
            # حذف مرکز
            col1, col2 = st.columns([3, 1])
            with col1:
                center_id = st.number_input("ID مرکز برای حذف", min_value=1, step=1)
            with col2:
                if st.button("🗑️ حذف مرکز", use_container_width=True):
                    conn.execute("DELETE FROM sales_centers WHERE id = ?", (center_id,))
                    conn.commit()
                    st.success("مرکز حذف شد!")
                    st.rerun()
    
    with tab2:
        with st.form("add_center_form"):
            name = st.text_input("نام مرکز فروش *")
            commission = st.number_input("درصد کمیسیون پیش‌فرض", min_value=0.0, max_value=100.0, value=7.0, step=0.5)
            
            if st.form_submit_button("➕ افزودن مرکز", use_container_width=True):
                if name:
                    try:
                        conn.execute(
                            "INSERT INTO sales_centers (name, commission_percent) VALUES (?, ?)",
                            (name, commission)
                        )
                        conn.commit()
                        st.success(f"مرکز «{name}» اضافه شد!")
                    except:
                        st.error("این مرکز قبلاً ثبت شده است!")
                else:
                    st.warning("نام مرکز الزامی است!")
    
    conn.close()

# ==================== موجودی حساب ====================
def cash_account_page():
    """صفحه موجودی حساب"""
    st.markdown("### 🏦 موجودی حساب")
    
    conn = get_connection()
    
    # موجودی فعلی
    deposits = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) as total FROM cash_transactions WHERE transaction_type = 'deposit'"
    ).fetchone()['total'] or 0
    
    withdraws = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) as total FROM cash_transactions WHERE transaction_type = 'withdraw'"
    ).fetchone()['total'] or 0
    
    balance = deposits - withdraws
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("💵 مجموع واریزها", f"{int(deposits):,} تومان")
    with col2:
        st.metric("💸 مجموع برداشت‌ها", f"{int(withdraws):,} تومان")
    with col3:
        st.metric("💰 موجودی نقدی", f"{int(balance):,} تومان")
    
    st.markdown("---")
    
    tab1, tab2 = st.tabs(["➕ ثبت تراکنش", "📋 تاریخچه"])
    
    with tab1:
        with st.form("cash_transaction_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                trans_type = st.selectbox("نوع تراکنش", ["💵 واریز", "💸 برداشت"])
                amount = st.number_input("مبلغ (تومان) *", min_value=0, step=10000)
            
            with col2:
                if "واریز" in trans_type:
                    source_options = ["اسنپ شاپ", "دیجی کالا", "نایتو", "فروش حضوری", "سایر"]
                else:
                    source_options = ["خرید کالا", "هزینه ارسال", "هزینه بسته‌بندی", "سایر"]
                
                source = st.selectbox("منبع/مقصد", source_options)
                description = st.text_input("توضیحات (اختیاری)")
            
            trans_date = st.date_input("تاریخ", value=datetime.now())
            
            if st.form_submit_button("✅ ثبت تراکنش", use_container_width=True, type="primary"):
                if amount > 0:
                    type_value = "deposit" if "واریز" in trans_type else "withdraw"
                    conn.execute("""
                        INSERT INTO cash_transactions (transaction_type, amount, source, description, transaction_date, created_by)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (type_value, amount, source, description, trans_date.strftime("%Y-%m-%d"), st.session_state.user['id']))
                    conn.commit()
                    st.success(f"تراکنش {int(amount):,} تومان ثبت شد!")
                    st.rerun()
                else:
                    st.warning("مبلغ باید بیشتر از صفر باشد!")
    
    with tab2:
        filter_type = st.selectbox("فیلتر", ["همه", "واریزها", "برداشت‌ها"], key="cash_filter")
        
        if filter_type == "واریزها":
            transactions = conn.execute(
                "SELECT * FROM cash_transactions WHERE transaction_type = 'deposit' ORDER BY transaction_date DESC, id DESC"
            ).fetchall()
        elif filter_type == "برداشت‌ها":
            transactions = conn.execute(
                "SELECT * FROM cash_transactions WHERE transaction_type = 'withdraw' ORDER BY transaction_date DESC, id DESC"
            ).fetchall()
        else:
            transactions = conn.execute(
                "SELECT * FROM cash_transactions ORDER BY transaction_date DESC, id DESC"
            ).fetchall()
        
        if transactions:
            df = []
            for t in transactions:
                df.append({
                    "ID": t['id'],
                    "تاریخ": gregorian_to_persian(t['transaction_date']),
                    "نوع": "💵 واریز" if t['transaction_type'] == 'deposit' else "💸 برداشت",
                    "مبلغ": f"{int(t['amount']):,}",
                    "منبع/مقصد": t['source'],
                    "توضیحات": t['description'] or "-"
                })
            
            st.dataframe(pd.DataFrame(df), use_container_width=True, hide_index=True)
            
            # حذف تراکنش
            col1, col2 = st.columns([3, 1])
            with col1:
                trans_id = st.number_input("ID تراکنش برای حذف", min_value=1, step=1)
            with col2:
                if st.button("🗑️ حذف", use_container_width=True):
                    conn.execute("DELETE FROM cash_transactions WHERE id = ?", (trans_id,))
                    conn.commit()
                    st.success("تراکنش حذف شد!")
                    st.rerun()
        else:
            st.info("تراکنشی ثبت نشده است.")
    
    conn.close()

# ==================== تسویه حساب ====================
def settlements_page():
    """صفحه تسویه حساب"""
    st.markdown("### 💵 تسویه حساب")
    
    conn = get_connection()
    
    tab1, tab2 = st.tabs(["➕ ثبت تسویه", "📋 تاریخچه"])
    
    with tab1:
        centers = conn.execute("SELECT id, name FROM sales_centers").fetchall()
        
        if centers:
            with st.form("settlement_form"):
                center_options = {c['name']: c['id'] for c in centers}
                selected_center = st.selectbox("مرکز فروش", options=list(center_options.keys()))
                center_id = center_options[selected_center]
                
                amount = st.number_input("مبلغ تسویه (تومان)", min_value=0, step=10000)
                description = st.text_input("توضیحات")
                settlement_date = st.date_input("تاریخ", value=datetime.now())
                
                if st.form_submit_button("✅ ثبت تسویه", use_container_width=True):
                    if amount > 0:
                        conn.execute("""
                            INSERT INTO settlements (center_id, amount, settlement_date, description, created_by)
                            VALUES (?, ?, ?, ?, ?)
                        """, (center_id, amount, settlement_date.strftime("%Y-%m-%d"), description, st.session_state.user['id']))
                        conn.commit()
                        st.success(f"تسویه {int(amount):,} تومان ثبت شد!")
                    else:
                        st.warning("مبلغ باید بیشتر از صفر باشد!")
    
    with tab2:
        settlements = conn.execute("""
            SELECT s.id, s.settlement_date, sc.name, s.amount, s.description
            FROM settlements s
            JOIN sales_centers sc ON s.center_id = sc.id
            ORDER BY s.settlement_date DESC
        """).fetchall()
        
        if settlements:
            df = []
            for s in settlements:
                df.append({
                    "ID": s['id'],
                    "تاریخ": gregorian_to_persian(s['settlement_date']),
                    "مرکز فروش": s['name'],
                    "مبلغ": f"{int(s['amount']):,}",
                    "توضیحات": s['description'] or "-"
                })
            
            st.dataframe(pd.DataFrame(df), use_container_width=True, hide_index=True)
    
    conn.close()

# ==================== گزارشات ====================
def reports_page():
    """صفحه گزارشات"""
    st.markdown("### 📊 گزارشات")
    
    conn = get_connection()
    
    tab1, tab2, tab3 = st.tabs(["📈 نمودار فروش", "📦 موجودی کالاها", "💰 سود و زیان"])
    
    with tab1:
        # نمودار فروش روزانه
        sales_data = conn.execute("""
            SELECT outflow_date, SUM(quantity * sell_price) as daily_sales
            FROM outflows WHERE is_returned = 0
            GROUP BY outflow_date
            ORDER BY outflow_date DESC
            LIMIT 30
        """).fetchall()
        
        if sales_data:
            df = pd.DataFrame([dict(s) for s in sales_data])
            df['outflow_date'] = pd.to_datetime(df['outflow_date'])
            df = df.sort_values('outflow_date')
            
            fig = px.line(df, x='outflow_date', y='daily_sales', 
                         title='فروش روزانه (30 روز اخیر)',
                         labels={'outflow_date': 'تاریخ', 'daily_sales': 'فروش (تومان)'})
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("داده‌ای برای نمایش وجود ندارد.")
    
    with tab2:
        products = conn.execute("""
            SELECT id, name, color, stock FROM products ORDER BY stock DESC
        """).fetchall()
        
        if products:
            df = pd.DataFrame([dict(p) for p in products])
            df.columns = ["کد", "نام کالا", "رنگ", "موجودی"]
            
            st.dataframe(df, use_container_width=True, hide_index=True)
            
            # نمودار موجودی
            fig = px.bar(df.head(20), x='نام کالا', y='موجودی', 
                        title='20 کالای پرموجودی')
            st.plotly_chart(fig, use_container_width=True)
    
    with tab3:
        profit_data = conn.execute("""
            SELECT 
                p.name,
                SUM(o.quantity) as total_qty,
                SUM(o.quantity * o.sell_price) as revenue,
                SUM(o.quantity * o.cogs_unit) as cogs,
                SUM(o.commission_amount) as commission,
                SUM(o.shipping_cost) as shipping
            FROM outflows o
            JOIN products p ON o.product_id = p.id
            WHERE o.is_returned = 0
            GROUP BY p.id
            ORDER BY (SUM(o.quantity * o.sell_price) - SUM(o.quantity * o.cogs_unit) - SUM(o.commission_amount) - SUM(o.shipping_cost)) DESC
        """).fetchall()
        
        if profit_data:
            df = []
            for p in profit_data:
                profit = (p['revenue'] or 0) - (p['cogs'] or 0) - (p['commission'] or 0) - (p['shipping'] or 0)
                df.append({
                    "کالا": p['name'],
                    "تعداد فروش": p['total_qty'],
                    "درآمد": f"{int(p['revenue'] or 0):,}",
                    "بهای تمام شده": f"{int(p['cogs'] or 0):,}",
                    "کمیسیون": f"{int(p['commission'] or 0):,}",
                    "سود خالص": f"{int(profit):,}"
                })
            
            st.dataframe(pd.DataFrame(df), use_container_width=True, hide_index=True)
    
    conn.close()

# ==================== مدیریت کاربران ====================
def users_page():
    """صفحه مدیریت کاربران"""
    st.markdown("### 👥 مدیریت کاربران")
    
    conn = get_connection()
    
    tab1, tab2 = st.tabs(["📋 لیست کاربران", "➕ افزودن کاربر"])
    
    with tab1:
        users = conn.execute("SELECT id, username, full_name, role, is_active, created_at FROM users").fetchall()
        
        if users:
            df = []
            role_names = {"admin": "👑 مدیر", "warehouse": "📦 انباردار", "viewer": "👀 ناظر"}
            
            for u in users:
                df.append({
                    "ID": u['id'],
                    "نام کاربری": u['username'],
                    "نام کامل": u['full_name'] or "-",
                    "نقش": role_names.get(u['role'], u['role']),
                    "وضعیت": "✅ فعال" if u['is_active'] else "❌ غیرفعال"
                })
            
            st.dataframe(pd.DataFrame(df), use_container_width=True, hide_index=True)
            
            # غیرفعال کردن کاربر
            st.markdown("---")
            col1, col2, col3 = st.columns(3)
            
            with col1:
                user_id = st.number_input("ID کاربر", min_value=1, step=1)
            
            with col2:
                if st.button("🔄 تغییر وضعیت", use_container_width=True):
                    conn.execute("UPDATE users SET is_active = NOT is_active WHERE id = ? AND id != 1", (user_id,))
                    conn.commit()
                    st.success("وضعیت کاربر تغییر کرد!")
                    st.rerun()
            
            with col3:
                if st.button("🗑️ حذف کاربر", use_container_width=True):
                    if user_id != 1:
                        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
                        conn.commit()
                        st.success("کاربر حذف شد!")
                        st.rerun()
                    else:
                        st.error("نمی‌توان کاربر ادمین اصلی را حذف کرد!")
    
    with tab2:
        with st.form("add_user_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                username = st.text_input("نام کاربری *")
                password = st.text_input("رمز عبور *", type="password")
            
            with col2:
                full_name = st.text_input("نام کامل")
                role = st.selectbox("نقش", ["viewer", "warehouse", "admin"], 
                                   format_func=lambda x: {"admin": "👑 مدیر", "warehouse": "📦 انباردار", "viewer": "👀 ناظر"}[x])
            
            if st.form_submit_button("➕ افزودن کاربر", use_container_width=True):
                if username and password:
                    try:
                        hashed = hash_password(password)
                        conn.execute("""
                            INSERT INTO users (username, password, role, full_name)
                            VALUES (?, ?, ?, ?)
                        """, (username, hashed, role, full_name))
                        conn.commit()
                        st.success(f"کاربر «{username}» اضافه شد!")
                    except:
                        st.error("این نام کاربری قبلاً ثبت شده است!")
                else:
                    st.warning("نام کاربری و رمز عبور الزامی است!")
    
    conn.close()

# ==================== مدیریت داده ====================
def data_management_page():
    """صفحه مدیریت داده و انتقال دیتابیس"""
    st.markdown("### 💾 مدیریت داده")
    
    tab1, tab2, tab3 = st.tabs(["📤 انتقال از دیتابیس قدیم", "📊 آمار دیتابیس", "🗑️ پاک‌سازی"])
    
    with tab1:
        st.markdown("#### 📤 انتقال داده از نسخه دسکتاپ")
        st.info("""
        فایل `warehouse_v2.db` را از کامپیوتر خود آپلود کنید.
        تمام داده‌ها شامل کالاها، ورودی‌ها، خروجی‌ها، مراکز فروش و تراکنش‌ها منتقل می‌شوند.
        """)
        
        uploaded_file = st.file_uploader("فایل دیتابیس را انتخاب کنید", type=['db'])
        
        if uploaded_file is not None:
            st.warning("⚠️ این عملیات داده‌های موجود را پاک کرده و داده‌های جدید را جایگزین می‌کند!")
            
            col1, col2 = st.columns(2)
            with col1:
                replace_data = st.checkbox("داده‌های قبلی پاک شوند", value=True)
            
            if st.button("🚀 شروع انتقال", type="primary", use_container_width=True):
                try:
                    # ذخیره فایل آپلود شده
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as tmp_file:
                        tmp_file.write(uploaded_file.getvalue())
                        tmp_path = tmp_file.name
                    
                    # اتصال به دیتابیس قدیم
                    old_conn = sqlite3.connect(tmp_path)
                    old_conn.row_factory = sqlite3.Row
                    old_cursor = old_conn.cursor()
                    
                    # اتصال به دیتابیس جدید
                    new_conn = get_connection()
                    new_cursor = new_conn.cursor()
                    
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    
                    # پاک‌سازی داده‌های قبلی اگر انتخاب شده
                    if replace_data:
                        status_text.text("🗑️ پاک‌سازی داده‌های قبلی...")
                        new_cursor.execute("DELETE FROM outflows")
                        new_cursor.execute("DELETE FROM inflows")
                        new_cursor.execute("DELETE FROM products")
                        new_cursor.execute("DELETE FROM sales_centers WHERE id > 0")
                        new_cursor.execute("DELETE FROM settlements")
                        new_cursor.execute("DELETE FROM cash_transactions")
                        new_cursor.execute("DELETE FROM commission_categories")
                        new_cursor.execute("DELETE FROM commissions")
                        new_cursor.execute("DELETE FROM product_categories")
                        new_conn.commit()
                    
                    progress_bar.progress(10)
                    
                    # انتقال محصولات
                    status_text.text("📦 انتقال محصولات...")
                    try:
                        products = old_cursor.execute("SELECT id, name, color, barcode, stock FROM products").fetchall()
                        for p in products:
                            new_cursor.execute("""
                                INSERT OR REPLACE INTO products (id, name, color, barcode, stock)
                                VALUES (?, ?, ?, ?, ?)
                            """, (p['id'], p['name'], p['color'], p['barcode'], p['stock']))
                        st.success(f"✅ {len(products)} کالا منتقل شد")
                    except Exception as e:
                        st.warning(f"⚠️ خطا در انتقال محصولات: {e}")
                    
                    progress_bar.progress(25)
                    
                    # انتقال مراکز فروش
                    status_text.text("🏪 انتقال مراکز فروش...")
                    try:
                        centers = old_cursor.execute("SELECT * FROM sales_centers").fetchall()
                        for c in centers:
                            new_cursor.execute("""
                                INSERT OR REPLACE INTO sales_centers (id, name, commission_percent, shipping_type, shipping_percent, shipping_min, shipping_max, shipping_fixed)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            """, (c['id'], c['name'], c['commission_percent'] if 'commission_percent' in c.keys() else 7,
                                  c['shipping_type'] if 'shipping_type' in c.keys() else 'manual',
                                  c['shipping_percent'] if 'shipping_percent' in c.keys() else 0,
                                  c['shipping_min'] if 'shipping_min' in c.keys() else 0,
                                  c['shipping_max'] if 'shipping_max' in c.keys() else 0,
                                  c['shipping_fixed'] if 'shipping_fixed' in c.keys() else 0))
                        st.success(f"✅ {len(centers)} مرکز فروش منتقل شد")
                    except Exception as e:
                        st.warning(f"⚠️ خطا در انتقال مراکز: {e}")
                    
                    progress_bar.progress(40)
                    
                    # انتقال ورودی‌ها
                    status_text.text("📥 انتقال ورودی‌ها...")
                    try:
                        inflows = old_cursor.execute("SELECT * FROM inflows").fetchall()
                        for i in inflows:
                            dollar_rate = i['dollar_rate'] if 'dollar_rate' in i.keys() else 0
                            new_cursor.execute("""
                                INSERT OR REPLACE INTO inflows (id, product_id, quantity, remaining_quantity, buy_price, dollar_rate, inflow_date)
                                VALUES (?, ?, ?, ?, ?, ?, ?)
                            """, (i['id'], i['product_id'], i['quantity'], i['remaining_quantity'], 
                                  i['buy_price'], dollar_rate, i['inflow_date']))
                        st.success(f"✅ {len(inflows)} ورودی منتقل شد")
                    except Exception as e:
                        st.warning(f"⚠️ خطا در انتقال ورودی‌ها: {e}")
                    
                    progress_bar.progress(60)
                    
                    # انتقال خروجی‌ها
                    status_text.text("📤 انتقال خروجی‌ها...")
                    try:
                        outflows = old_cursor.execute("SELECT * FROM outflows").fetchall()
                        for o in outflows:
                            new_cursor.execute("""
                                INSERT OR REPLACE INTO outflows (id, product_id, center_id, quantity, sell_price, cogs_unit, 
                                    commission_amount, shipping_cost, outflow_date, order_number, is_returned, is_paid)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """, (o['id'], o['product_id'], o['center_id'], o['quantity'], o['sell_price'],
                                  o['cogs_unit'], o['commission_amount'], o['shipping_cost'], o['outflow_date'],
                                  o['order_number'] if 'order_number' in o.keys() else '',
                                  o['is_returned'] if 'is_returned' in o.keys() else 0,
                                  o['is_paid'] if 'is_paid' in o.keys() else 0))
                        st.success(f"✅ {len(outflows)} خروجی منتقل شد")
                    except Exception as e:
                        st.warning(f"⚠️ خطا در انتقال خروجی‌ها: {e}")
                    
                    progress_bar.progress(75)
                    
                    # انتقال تسویه‌ها
                    status_text.text("💵 انتقال تسویه‌ها...")
                    try:
                        settlements = old_cursor.execute("SELECT * FROM settlements").fetchall()
                        for s in settlements:
                            new_cursor.execute("""
                                INSERT OR REPLACE INTO settlements (id, center_id, amount, settlement_date, description)
                                VALUES (?, ?, ?, ?, ?)
                            """, (s['id'], s['center_id'], s['amount'], s['settlement_date'],
                                  s['description'] if 'description' in s.keys() else ''))
                        st.success(f"✅ {len(settlements)} تسویه منتقل شد")
                    except Exception as e:
                        st.warning(f"⚠️ خطا در انتقال تسویه‌ها: {e}")
                    
                    progress_bar.progress(85)
                    
                    # انتقال تراکنش‌های نقدی
                    status_text.text("🏦 انتقال تراکنش‌های نقدی...")
                    try:
                        cash_trans = old_cursor.execute("SELECT * FROM cash_transactions").fetchall()
                        for ct in cash_trans:
                            new_cursor.execute("""
                                INSERT OR REPLACE INTO cash_transactions (id, transaction_type, amount, source, description, transaction_date)
                                VALUES (?, ?, ?, ?, ?, ?)
                            """, (ct['id'], ct['transaction_type'], ct['amount'], ct['source'],
                                  ct['description'] if 'description' in ct.keys() else '',
                                  ct['transaction_date']))
                        st.success(f"✅ {len(cash_trans)} تراکنش نقدی منتقل شد")
                    except Exception as e:
                        st.warning(f"⚠️ جدول تراکنش‌های نقدی وجود نداشت یا خطا: {e}")
                    
                    progress_bar.progress(95)
                    
                    # انتقال دسته‌بندی کمیسیون
                    status_text.text("💳 انتقال دسته‌بندی‌های کمیسیون...")
                    try:
                        categories = old_cursor.execute("SELECT * FROM commission_categories").fetchall()
                        for cat in categories:
                            new_cursor.execute("""
                                INSERT OR REPLACE INTO commission_categories (id, name, description)
                                VALUES (?, ?, ?)
                            """, (cat['id'], cat['name'], cat['description'] if 'description' in cat.keys() else ''))
                        st.success(f"✅ {len(categories)} دسته‌بندی منتقل شد")
                    except Exception as e:
                        st.warning(f"⚠️ جدول دسته‌بندی وجود نداشت: {e}")
                    
                    # انتقال کمیسیون‌ها
                    try:
                        commissions = old_cursor.execute("SELECT * FROM commissions").fetchall()
                        for comm in commissions:
                            new_cursor.execute("""
                                INSERT OR REPLACE INTO commissions (id, center_id, category_id, commission_percent)
                                VALUES (?, ?, ?, ?)
                            """, (comm['id'], comm['center_id'], comm['category_id'], comm['commission_percent']))
                        st.success(f"✅ {len(commissions)} کمیسیون منتقل شد")
                    except Exception as e:
                        pass
                    
                    # انتقال ارتباط محصول و دسته‌بندی
                    try:
                        prod_cats = old_cursor.execute("SELECT * FROM product_categories").fetchall()
                        for pc in prod_cats:
                            new_cursor.execute("""
                                INSERT OR REPLACE INTO product_categories (product_id, category_id)
                                VALUES (?, ?)
                            """, (pc['product_id'], pc['category_id']))
                    except Exception as e:
                        pass
                    
                    new_conn.commit()
                    progress_bar.progress(100)
                    
                    # بستن اتصالات
                    old_conn.close()
                    new_conn.close()
                    
                    # حذف فایل موقت
                    os.unlink(tmp_path)
                    
                    status_text.text("")
                    st.balloons()
                    st.success("🎉 انتقال داده‌ها با موفقیت انجام شد!")
                    
                except Exception as e:
                    st.error(f"❌ خطا در انتقال: {e}")
    
    with tab2:
        st.markdown("#### 📊 آمار دیتابیس")
        
        conn = get_connection()
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            products_count = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
            st.metric("📦 تعداد کالاها", products_count)
            
            inflows_count = conn.execute("SELECT COUNT(*) FROM inflows").fetchone()[0]
            st.metric("📥 تعداد ورودی‌ها", inflows_count)
        
        with col2:
            outflows_count = conn.execute("SELECT COUNT(*) FROM outflows").fetchone()[0]
            st.metric("📤 تعداد خروجی‌ها", outflows_count)
            
            centers_count = conn.execute("SELECT COUNT(*) FROM sales_centers").fetchone()[0]
            st.metric("🏪 تعداد مراکز فروش", centers_count)
        
        with col3:
            settlements_count = conn.execute("SELECT COUNT(*) FROM settlements").fetchone()[0]
            st.metric("💵 تعداد تسویه‌ها", settlements_count)
            
            cash_count = conn.execute("SELECT COUNT(*) FROM cash_transactions").fetchone()[0]
            st.metric("🏦 تعداد تراکنش‌های نقدی", cash_count)
        
        conn.close()
    
    with tab3:
        st.markdown("#### 🗑️ پاک‌سازی داده‌ها")
        st.error("⚠️ این عملیات قابل بازگشت نیست!")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("🗑️ پاک کردن همه خروجی‌ها", use_container_width=True):
                conn = get_connection()
                conn.execute("DELETE FROM outflows")
                conn.commit()
                conn.close()
                st.success("خروجی‌ها پاک شدند!")
                st.rerun()
        
        with col2:
            if st.button("🗑️ پاک کردن همه ورودی‌ها", use_container_width=True):
                conn = get_connection()
                conn.execute("DELETE FROM inflows")
                conn.commit()
                conn.close()
                st.success("ورودی‌ها پاک شدند!")
                st.rerun()
        
        st.markdown("---")
        
        confirm_text = st.text_input("برای پاک کردن کل داده‌ها، عبارت 'DELETE ALL' را تایپ کنید:")
        
        if st.button("☢️ پاک کردن کل داده‌ها", type="primary", use_container_width=True):
            if confirm_text == "DELETE ALL":
                conn = get_connection()
                conn.execute("DELETE FROM outflows")
                conn.execute("DELETE FROM inflows")
                conn.execute("DELETE FROM products")
                conn.execute("DELETE FROM settlements")
                conn.execute("DELETE FROM cash_transactions")
                conn.commit()
                conn.close()
                st.success("همه داده‌ها پاک شدند!")
                st.rerun()
            else:
                st.warning("عبارت تایید اشتباه است!")

# ==================== منوی اصلی ====================
def main_menu():
    """منوی اصلی سایدبار"""
    with st.sidebar:
        st.markdown(f"### 👋 خوش آمدید")
        st.markdown(f"**{st.session_state.user['full_name'] or st.session_state.user['username']}**")
        
        role_names = {"admin": "👑 مدیر", "warehouse": "📦 انباردار", "viewer": "👀 ناظر"}
        st.markdown(f"نقش: {role_names.get(st.session_state.user['role'], '')}")
        
        st.markdown("---")
        
        permissions = st.session_state.permissions
        
        menu_items = []
        
        if permissions.get('dashboard'):
            menu_items.append("🏠 داشبورد")
        if permissions.get('products'):
            menu_items.append("📝 مدیریت کالا")
        if permissions.get('inflows'):
            menu_items.append("📥 ورودی انبار")
        if permissions.get('outflows'):
            menu_items.append("📤 خروجی انبار")
        if permissions.get('centers'):
            menu_items.append("🏪 مراکز فروش")
        if permissions.get('settlements'):
            menu_items.append("💵 تسویه حساب")
        if permissions.get('cash_account'):
            menu_items.append("🏦 موجودی حساب")
        if permissions.get('reports'):
            menu_items.append("📊 گزارشات")
        if permissions.get('users'):
            menu_items.append("👥 مدیریت کاربران")
        if permissions.get('data_management'):
            menu_items.append("💾 مدیریت داده")
        
        selected = st.radio("منو", menu_items, label_visibility="collapsed")
        
        st.markdown("---")
        
        if st.button("🚪 خروج", use_container_width=True):
            st.session_state.logged_in = False
            st.session_state.user = None
            st.session_state.permissions = None
            st.rerun()
        
        return selected

# ==================== اجرای برنامه ====================
def main():
    """تابع اصلی"""
    
    # ایجاد دیتابیس
    init_database()
    
    # بررسی لاگین
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
    
    if not st.session_state.logged_in:
        login_page()
    else:
        selected_page = main_menu()
        
        if "داشبورد" in selected_page:
            dashboard_page()
        elif "مدیریت کالا" in selected_page:
            products_page()
        elif "ورودی انبار" in selected_page:
            inflows_page()
        elif "خروجی انبار" in selected_page:
            outflows_page()
        elif "مراکز فروش" in selected_page:
            centers_page()
        elif "تسویه حساب" in selected_page:
            settlements_page()
        elif "موجودی حساب" in selected_page:
            cash_account_page()
        elif "گزارشات" in selected_page:
            reports_page()
        elif "مدیریت کاربران" in selected_page:
            users_page()
        elif "مدیریت داده" in selected_page:
            data_management_page()

if __name__ == "__main__":
    main()
