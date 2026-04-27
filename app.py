from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory, session
import sqlite3
import os
import json
from werkzeug.utils import secure_filename
from datetime import datetime
from functools import wraps

app = Flask(__name__)
app.secret_key = 'souk_gold_secret_key_2026'

UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'mp4', 'webm', 'mov'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 200 * 1024 * 1024

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def init_db():
    conn = sqlite3.connect('souk.db')
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        phone TEXT NOT NULL UNIQUE,
        password TEXT NOT NULL,
        date TEXT DEFAULT CURRENT_TIMESTAMP
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        description TEXT NOT NULL,
        price TEXT NOT NULL,
        phone TEXT NOT NULL,
        category TEXT NOT NULL,
        city TEXT NOT NULL,
        images TEXT NOT NULL DEFAULT '[]',
        user_id INTEGER DEFAULT 0,
        views INTEGER DEFAULT 0,
        sold INTEGER DEFAULT 0,
        delivery_available INTEGER DEFAULT 0,
        delivery_price_inside TEXT DEFAULT '0',
        delivery_price_outside TEXT DEFAULT '0',
        date TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS favorites (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        product_id INTEGER NOT NULL,
        date TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (product_id) REFERENCES products(id),
        UNIQUE(user_id, product_id)
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER NOT NULL,
        seller_id INTEGER NOT NULL,
        buyer_name TEXT NOT NULL,
        buyer_phone TEXT NOT NULL,
        buyer_address TEXT NOT NULL,
        buyer_city TEXT NOT NULL,
        delivery_price TEXT DEFAULT '0',
        status TEXT DEFAULT 'new',
        date TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (product_id) REFERENCES products(id),
        FOREIGN KEY (seller_id) REFERENCES users(id)
    )''')
    
    conn.commit()
    conn.close()

init_db()

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('❌ يجب تسجيل الدخول أولاً', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def index():
    user_id = session.get('user_id', 0)
    
    city_filter = request.args.get('city', '')
    category_filter = request.args.get('category', '')
    price_min = request.args.get('price_min', '')
    price_max = request.args.get('price_max', '')
    sort = request.args.get('sort', 'newest')
    
    conn = sqlite3.connect('souk.db')
    c = conn.cursor()
    
    query = "SELECT * FROM products WHERE 1=1"
    params = []
    
    if city_filter:
        query += " AND city LIKE ?"
        params.append(f'%{city_filter}%')
    if category_filter:
        query += " AND category = ?"
        params.append(category_filter)
    if price_min:
        query += " AND CAST(price AS INTEGER) >= ?"
        params.append(int(price_min))
    if price_max:
        query += " AND CAST(price AS INTEGER) <= ?"
        params.append(int(price_max))
    
    if sort == 'cheapest':
        query += " ORDER BY CAST(price AS INTEGER) ASC"
    else:
        query += " ORDER BY id DESC"
    
    c.execute(query, params)
    products = c.fetchall()
    
    favorites = []
    if user_id > 0:
        c.execute("SELECT product_id FROM favorites WHERE user_id = ?", (user_id,))
        favorites = [row[0] for row in c.fetchall()]
    
    products_list = []
    for p in products:
        images = json.loads(p[7])
        products_list.append({
            'id': p[0], 'title': p[1], 'description': p[2], 'price': p[3],
            'phone': p[4], 'category': p[5], 'city': p[6],
            'images': images, 'first_image': images[0] if images else 'default.jpg',
            'user_id': p[8], 'views': p[9], 'sold': p[10],
            'delivery_available': p[11] if len(p) > 11 else 0,
            'delivery_price_inside': p[12] if len(p) > 12 else '0',
            'delivery_price_outside': p[13] if len(p) > 13 else '0',
            'date': p[14] if len(p) > 14 else '',
            'is_favorite': p[0] in favorites
        })
    
    conn.close()
    return render_template('index.html', products=products_list, user_id=user_id)

@app.route('/add', methods=['GET', 'POST'])
@login_required
def add_product():
    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        price = request.form['price']
        phone = request.form['phone']
        category = request.form['category']
        city = request.form['city']
        files = request.files.getlist('images')
        user_id = session.get('user_id', 0)
        delivery_available = request.form.get('delivery_available', '0')
        delivery_price_inside = request.form.get('delivery_price_inside', '0')
        delivery_price_outside = request.form.get('delivery_price_outside', '0')

        if not files or files[0].filename == '':
            flash('❌ يجب رفع صورة واحدة على الأقل', 'danger')
            return render_template('add.html')

        saved_files = []
        for file in files:
            if file and allowed_file(file.filename):
                ext = file.filename.rsplit('.', 1)[1].lower()
                filename = f"{datetime.now().strftime('%Y%m%d%H%M%S%f')}_{len(saved_files)}.{ext}"
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                saved_files.append(filename)

        if saved_files:
            conn = sqlite3.connect('souk.db')
            c = conn.cursor()
            c.execute("""INSERT INTO products (title, description, price, phone, category, city, images, user_id, delivery_available, delivery_price_inside, delivery_price_outside) 
                         VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                      (title, description, price, phone, category, city, json.dumps(saved_files), user_id, delivery_available, delivery_price_inside, delivery_price_outside))
            conn.commit()
            conn.close()
            flash('✅ تم إضافة الإعلان بنجاح!', 'success')
            return redirect(url_for('index'))
        else:
            flash('❌ خطأ: الصيغ غير مدعومة', 'danger')

    return render_template('add.html')

@app.route('/product/<int:id>')
def product_detail(id):
    conn = sqlite3.connect('souk.db')
    c = conn.cursor()
    
    c.execute("UPDATE products SET views = views + 1 WHERE id = ?", (id,))
    
    c.execute("SELECT * FROM products WHERE id = ?", (id,))
    p = c.fetchone()
    
    user_id = session.get('user_id', 0)
    is_favorite = False
    
    if user_id > 0 and p:
        c.execute("SELECT id FROM favorites WHERE user_id = ? AND product_id = ?", (user_id, id))
        is_favorite = c.fetchone() is not None
    
    conn.commit()
    conn.close()
    
    if p:
        images = json.loads(p[7])
        product = {
            'id': p[0], 'title': p[1], 'description': p[2], 'price': p[3],
            'phone': p[4], 'category': p[5], 'city': p[6],
            'images': images, 'user_id': p[8], 'views': p[9], 'sold': p[10],
            'delivery_available': p[11] if len(p) > 11 else 0,
            'delivery_price_inside': p[12] if len(p) > 12 else '0',
            'delivery_price_outside': p[13] if len(p) > 13 else '0',
            'date': p[14] if len(p) > 14 else '',
            'is_favorite': is_favorite
        }
        return render_template('product.html', product=product, user_id=user_id)
    return redirect(url_for('index'))

@app.route('/search')
def search():
    q = request.args.get('q', '')
    city_filter = request.args.get('city', '')
    sort = request.args.get('sort', 'newest')
    user_id = session.get('user_id', 0)
    
    conn = sqlite3.connect('souk.db')
    c = conn.cursor()
    
    query = "SELECT * FROM products WHERE (title LIKE ? OR description LIKE ? OR city LIKE ?)"
    params = [f'%{q}%', f'%{q}%', f'%{q}%']
    
    if city_filter:
        query += " AND city LIKE ?"
        params.append(f'%{city_filter}%')
    
    if sort == 'cheapest':
        query += " ORDER BY CAST(price AS INTEGER) ASC"
    else:
        query += " ORDER BY id DESC"
    
    c.execute(query, params)
    products = c.fetchall()
    
    favorites = []
    if user_id > 0:
        c.execute("SELECT product_id FROM favorites WHERE user_id = ?", (user_id,))
        favorites = [row[0] for row in c.fetchall()]
    
    products_list = []
    for p in products:
        images = json.loads(p[7])
        products_list.append({
            'id': p[0], 'title': p[1], 'description': p[2], 'price': p[3],
            'phone': p[4], 'category': p[5], 'city': p[6],
            'images': images, 'first_image': images[0] if images else 'default.jpg',
            'user_id': p[8], 'views': p[9], 'sold': p[10],
            'delivery_available': p[11] if len(p) > 11 else 0,
            'delivery_price_inside': p[12] if len(p) > 12 else '0',
            'delivery_price_outside': p[13] if len(p) > 13 else '0',
            'date': p[14] if len(p) > 14 else '',
            'is_favorite': p[0] in favorites
        })
    
    conn.close()
    return render_template('index.html', products=products_list, user_id=user_id,
                           search_query=q, city_filter=city_filter, sort=sort)

# ========== نظام الطلبات ==========
@app.route('/order/<int:product_id>', methods=['POST'])
def place_order(product_id):
    buyer_name = request.form['buyer_name']
    buyer_phone = request.form['buyer_phone']
    buyer_address = request.form['buyer_address']
    buyer_city = request.form['buyer_city']
    delivery_price = request.form.get('delivery_price', '0')
    
    conn = sqlite3.connect('souk.db')
    c = conn.cursor()
    c.execute("SELECT * FROM products WHERE id = ?", (product_id,))
    product = c.fetchone()
    
    if product:
        seller_id = product[8]
        
        c.execute("""INSERT INTO orders (product_id, seller_id, buyer_name, buyer_phone, buyer_address, buyer_city, delivery_price)
                     VALUES (?,?,?,?,?,?,?)""",
                  (product_id, seller_id, buyer_name, buyer_phone, buyer_address, buyer_city, delivery_price))
        conn.commit()
        conn.close()
        
        flash('✅ تم إرسال طلبك بنجاح! سيتواصل معك البائع قريباً', 'success')
    else:
        conn.close()
        flash('❌ حدث خطأ، المنتج غير موجود', 'danger')
    
    return redirect(url_for('product_detail', id=product_id))

@app.route('/orders')
@login_required
def my_orders():
    user_id = session.get('user_id', 0)
    conn = sqlite3.connect('souk.db')
    c = conn.cursor()
    
    # الطلبات اللي وصلتني كبائع
    c.execute("""
        SELECT o.*, p.title, p.price FROM orders o
        JOIN products p ON o.product_id = p.id
        WHERE o.seller_id = ?
        ORDER BY o.id DESC
    """, (user_id,))
    seller_orders = c.fetchall()
    
    # الطلبات اللي عملتها كمشتري
    c.execute("""
        SELECT o.*, p.title, p.price FROM orders o
        JOIN products p ON o.product_id = p.id
        WHERE o.buyer_phone = (SELECT phone FROM users WHERE id = ?)
        ORDER BY o.id DESC
    """, (user_id,))
    buyer_orders = c.fetchall()
    
    conn.close()
    return render_template('orders.html', seller_orders=seller_orders, buyer_orders=buyer_orders)

# ========== نظام المستخدمين ==========
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        phone = request.form['phone']
        password = request.form['password']
        
        conn = sqlite3.connect('souk.db')
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE phone = ? AND password = ?", (phone, password))
        user = c.fetchone()
        conn.close()
        
        if user:
            session['user_id'] = user[0]
            session['user_name'] = user[1]
            flash(f'👋 مرحباً {user[1]}!', 'success')
            return redirect(url_for('index'))
        else:
            flash('❌ رقم الهاتف أو كلمة المرور غير صحيحة', 'danger')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        phone = request.form['phone']
        password = request.form['password']
        
        conn = sqlite3.connect('souk.db')
        c = conn.cursor()
        
        c.execute("SELECT id FROM users WHERE phone = ?", (phone,))
        if c.fetchone():
            conn.close()
            flash('❌ رقم الهاتف مسجل من قبل', 'danger')
            return render_template('login.html')
        
        c.execute("INSERT INTO users (name, phone, password) VALUES (?,?,?)", (name, phone, password))
        conn.commit()
        conn.close()
        
        flash('✅ تم التسجيل بنجاح! يمكنك تسجيل الدخول الآن', 'success')
        return redirect(url_for('login'))
    
    return redirect(url_for('login'))

@app.route('/logout')
def logout():
    session.clear()
    flash('👋 تم تسجيل الخروج', 'success')
    return redirect(url_for('index'))

@app.route('/my_ads')
@login_required
def my_ads():
    user_id = session.get('user_id', 0)
    conn = sqlite3.connect('souk.db')
    c = conn.cursor()
    c.execute("SELECT * FROM products WHERE user_id = ? ORDER BY id DESC", (user_id,))
    products = c.fetchall()
    conn.close()
    
    products_list = []
    for p in products:
        images = json.loads(p[7])
        products_list.append({
            'id': p[0], 'title': p[1], 'description': p[2], 'price': p[3],
            'phone': p[4], 'category': p[5], 'city': p[6],
            'images': images, 'first_image': images[0] if images else 'default.jpg',
            'views': p[9], 'sold': p[10],
            'delivery_available': p[11] if len(p) > 11 else 0,
            'delivery_price_inside': p[12] if len(p) > 12 else '0',
            'delivery_price_outside': p[13] if len(p) > 13 else '0',
            'date': p[14] if len(p) > 14 else ''
        })
    
    return render_template('my_ads.html', products=products_list)

@app.route('/delete_ad/<int:id>')
@login_required
def delete_ad(id):
    user_id = session.get('user_id', 0)
    conn = sqlite3.connect('souk.db')
    c = conn.cursor()
    c.execute("DELETE FROM products WHERE id = ? AND user_id = ?", (id, user_id))
    c.execute("DELETE FROM favorites WHERE product_id = ?", (id,))
    c.execute("DELETE FROM orders WHERE product_id = ?", (id,))
    conn.commit()
    conn.close()
    flash('🗑️ تم حذف الإعلان', 'success')
    return redirect(url_for('my_ads'))

@app.route('/toggle_sold/<int:id>')
@login_required
def toggle_sold(id):
    user_id = session.get('user_id', 0)
    conn = sqlite3.connect('souk.db')
    c = conn.cursor()
    c.execute("SELECT sold FROM products WHERE id = ? AND user_id = ?", (id, user_id))
    result = c.fetchone()
    if result:
        new_status = 0 if result[0] == 1 else 1
        c.execute("UPDATE products SET sold = ? WHERE id = ?", (new_status, id))
        conn.commit()
        flash('✅ تم تحديث حالة الإعلان', 'success')
    conn.close()
    return redirect(url_for('my_ads'))

# ========== المفضلة ==========
@app.route('/toggle_favorite/<int:product_id>')
@login_required
def toggle_favorite(product_id):
    user_id = session.get('user_id', 0)
    conn = sqlite3.connect('souk.db')
    c = conn.cursor()
    
    c.execute("SELECT id FROM favorites WHERE user_id = ? AND product_id = ?", (user_id, product_id))
    existing = c.fetchone()
    
    if existing:
        c.execute("DELETE FROM favorites WHERE user_id = ? AND product_id = ?", (user_id, product_id))
        conn.commit()
        conn.close()
        return {'status': 'removed', 'message': 'تمت إزالة من المفضلة'}
    else:
        c.execute("INSERT INTO favorites (user_id, product_id) VALUES (?,?)", (user_id, product_id))
        conn.commit()
        conn.close()
        return {'status': 'added', 'message': 'تمت إضافة إلى المفضلة'}

@app.route('/favorites')
@login_required
def favorites():
    user_id = session.get('user_id', 0)
    conn = sqlite3.connect('souk.db')
    c = conn.cursor()
    c.execute("""
        SELECT p.* FROM products p
        JOIN favorites f ON p.id = f.product_id
        WHERE f.user_id = ?
        ORDER BY f.id DESC
    """, (user_id,))
    products = c.fetchall()
    conn.close()
    
    products_list = []
    for p in products:
        images = json.loads(p[7])
        products_list.append({
            'id': p[0], 'title': p[1], 'description': p[2], 'price': p[3],
            'phone': p[4], 'category': p[5], 'city': p[6],
            'images': images, 'first_image': images[0] if images else 'default.jpg',
            'views': p[9], 'sold': p[10],
            'delivery_available': p[11] if len(p) > 11 else 0,
            'date': p[14] if len(p) > 14 else '',
            'is_favorite': True
        })
    
    return render_template('index.html', products=products_list, user_id=user_id, is_favorites=True)

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

