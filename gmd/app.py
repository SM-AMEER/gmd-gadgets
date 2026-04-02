from flask import Flask, render_template, request, redirect, session
import sqlite3
import razorpay
import os

app = Flask(__name__)
app.secret_key = "gmdsecret123"

# 🔐 ADMIN LOGIN
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "1234"

# 🔑 RAZORPAY KEYS (SAFE WAY)
RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID") or "rzp_test_SXliBnoUDhf8gC"
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET") or "qysxIjz17GYDS24xS3XGI8Qt"

# =========================
# DATABASE
# =========================
def get_db():
    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    return conn

def create_table():
    db = get_db()

    db.execute("""
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        price INTEGER,
        image TEXT
    )
    """)

    db.execute("""
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        phone TEXT,
        address TEXT,
        items TEXT,
        total INTEGER,
        status TEXT
    )
    """)

    db.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT
    )
    """)

    db.commit()

create_table()

# =========================
# HOME + SEARCH
# =========================
@app.route("/")
def index():
    db = get_db()
    query = request.args.get("q")

    if query:
        products = db.execute(
            "SELECT * FROM products WHERE name LIKE ?",
            ('%' + query + '%',)
        ).fetchall()
    else:
        products = db.execute("SELECT * FROM products").fetchall()

    return render_template("index.html", products=products)

# =========================
# USER SIGNUP
# =========================
@app.route("/signup", methods=["GET", "POST"])
def signup():
    error = None

    if request.method == "POST":
        try:
            db = get_db()
            db.execute(
                "INSERT INTO users (username, password) VALUES (?, ?)",
                (request.form["username"], request.form["password"])
            )
            db.commit()
            return redirect("/user_login")

        except:
            error = "Username already exists ❌"

    return render_template("signup.html", error=error)

# =========================
# USER LOGIN
# =========================
@app.route("/user_login", methods=["GET", "POST"])
def user_login():
    error = None

    if request.method == "POST":
        db = get_db()
        user = db.execute(
            "SELECT * FROM users WHERE username=? AND password=?",
            (request.form["username"], request.form["password"])
        ).fetchone()

        if user:
            session.pop("admin", None)   # 🔥 FIX
            session["user"] = user["username"]
            return redirect("/")
        else:
            error = "Invalid login ❌"

    return render_template("user_login.html", error=error)

@app.route("/user_logout")
def user_logout():
    session.pop("user", None)
    return redirect("/")

# =========================
# ADMIN LOGIN
# =========================
@app.route("/login", methods=["GET", "POST"])
def login():
    error = None

    if request.method == "POST":
        if request.form["username"] == ADMIN_USERNAME and request.form["password"] == ADMIN_PASSWORD:
            session.pop("user", None)   # 🔥 FIX
            session["admin"] = True
            return redirect("/admin")
        else:
            error = "Invalid Admin Login ❌"

    return render_template("login.html", error=error)

@app.route("/logout")
def logout():
    session.pop("admin", None)
    return redirect("/login")

# =========================
# ADMIN PANEL
# =========================
@app.route("/admin", methods=["GET", "POST"])
def admin():
    if not session.get("admin"):
        return redirect("/login")

    db = get_db()

    if request.method == "POST":
        db.execute(
            "INSERT INTO products (name, price, image) VALUES (?, ?, ?)",
            (request.form["name"], request.form["price"], request.form["image"])
        )
        db.commit()

    products = db.execute("SELECT * FROM products").fetchall()
    return render_template("admin.html", products=products)

@app.route("/delete/<int:id>")
def delete(id):
    if not session.get("admin"):
        return redirect("/login")

    db = get_db()
    db.execute("DELETE FROM products WHERE id=?", (id,))
    db.commit()
    return redirect("/admin")

# =========================
# CART
# =========================
@app.route("/add_to_cart/<int:id>")
def add_to_cart(id):
    db = get_db()
    product = db.execute("SELECT * FROM products WHERE id=?", (id,)).fetchone()

    if not product:
        return redirect("/")

    cart = session.get("cart", {})
    pid = str(product["id"])

    if pid in cart:
        cart[pid]["quantity"] += 1
    else:
        cart[pid] = {
            "id": product["id"],
            "name": product["name"],
            "price": int(product["price"]),
            "image": product["image"],
            "quantity": 1
        }

    session["cart"] = cart
    return redirect("/")

@app.route("/cart")
def cart():
    cart = session.get("cart", {})
    total = sum(item["price"] * item["quantity"] for item in cart.values())
    return render_template("cart.html", cart=cart, total=total)

@app.route("/increase/<int:id>")
def increase(id):
    cart = session.get("cart", {})
    if str(id) in cart:
        cart[str(id)]["quantity"] += 1
    session["cart"] = cart
    return redirect("/cart")

@app.route("/decrease/<int:id>")
def decrease(id):
    cart = session.get("cart", {})
    if str(id) in cart:
        cart[str(id)]["quantity"] -= 1
        if cart[str(id)]["quantity"] <= 0:
            del cart[str(id)]
    session["cart"] = cart
    return redirect("/cart")

@app.route("/remove/<int:id>")
def remove(id):
    cart = session.get("cart", {})
    cart.pop(str(id), None)
    session["cart"] = cart
    return redirect("/cart")

# =========================
# CHECKOUT
# =========================
@app.route("/checkout", methods=["GET", "POST"])
def checkout():
    if not session.get("user"):   # 🔥 LOGIN REQUIRED
        return redirect("/user_login")

    cart = session.get("cart", {})
    total = sum(item["price"] * item["quantity"] for item in cart.values())

    if total == 0:
        return redirect("/")

    if request.method == "POST":
        session["customer"] = {
            "name": request.form["name"],
            "phone": request.form["phone"],
            "address": request.form["address"]
        }
        return redirect("/payment")

    return render_template("checkout.html", total=total)

# =========================
# PAYMENT
# =========================
@app.route("/payment")
def payment():
    try:
        cart = session.get("cart", {})
        total = sum(item["price"] * item["quantity"] for item in cart.values())

        if total == 0:
            return redirect("/")

        client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))

        order = client.order.create({
            "amount": total * 100,
            "currency": "INR",
            "payment_capture": 1
        })

        return render_template(
            "payment.html",
            total=total,
            order_id=order["id"],
            key_id=RAZORPAY_KEY_ID
        )

    except Exception as e:
        print(e)  # 🔥 DEBUG
        return f"<h2>Error:</h2><pre>{str(e)}</pre>"

# =========================
# SUCCESS
# =========================
@app.route("/success")
def success():
    cart = session.get("cart", {})
    customer = session.get("customer", {})

    total = sum(item["price"] * item["quantity"] for item in cart.values())

    db = get_db()
    db.execute("""
        INSERT INTO orders (name, phone, address, items, total, status)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        customer.get("name"),
        customer.get("phone"),
        customer.get("address"),
        str(list(cart.values())),
        total,
        "Pending"
    ))
    db.commit()

    session.pop("cart", None)
    session.pop("customer", None)

    return "<h2>✅ Order Placed!</h2><a href='/'>Go Home</a>"

# =========================
# ADMIN ORDERS
# =========================
@app.route("/admin/orders")
def admin_orders():
    if not session.get("admin"):
        return redirect("/login")

    db = get_db()
    orders = db.execute("SELECT * FROM orders").fetchall()
    return render_template("admin_orders.html", orders=orders)

# =========================
# RUN
# =========================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)