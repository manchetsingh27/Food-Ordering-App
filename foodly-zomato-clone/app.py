from flask import Flask, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
import os

load_dotenv()

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "foodly_secret_key")
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///foodly.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(200))
    role = db.Column(db.String(20), default="user")


class FoodItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    restaurant = db.Column(db.String(100))
    category = db.Column(db.String(50))
    price = db.Column(db.Integer)
    image = db.Column(db.String(300))


class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer)
    items = db.Column(db.Text)
    total = db.Column(db.Integer)
    address = db.Column(db.Text)
    payment_id = db.Column(db.String(100))
    status = db.Column(db.String(50), default="Placed")


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


@app.route("/")
def home():
    search = request.args.get("search", "")
    category = request.args.get("category", "")

    foods = FoodItem.query

    if search:
        foods = foods.filter(
            FoodItem.name.contains(search) |
            FoodItem.restaurant.contains(search)
        )

    if category:
        foods = foods.filter_by(category=category)

    foods = foods.all()
    categories = ["Pizza", "Burger", "Biryani", "Chinese", "Dessert"]

    return render_template(
        "index.html",
        foods=foods,
        categories=categories,
        selected_category=category,
        search=search
    )


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        existing_user = User.query.filter_by(email=request.form["email"]).first()

        if existing_user:
            return "Email already registered. Please login."

        user = User(
            name=request.form["name"],
            email=request.form["email"],
            password=generate_password_hash(request.form["password"])
        )

        db.session.add(user)
        db.session.commit()

        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = User.query.filter_by(email=request.form["email"]).first()

        if user and check_password_hash(user.password, request.form["password"]):
            login_user(user)
            return redirect(url_for("home"))

        return "Invalid email or password"

    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("home"))


@app.route("/add-to-cart/<int:item_id>")
@login_required
def add_to_cart(item_id):
    cart = session.get("cart", [])
    cart.append(item_id)
    session["cart"] = cart

    return redirect(url_for("cart"))


@app.route("/remove-from-cart/<int:item_id>")
@login_required
def remove_from_cart(item_id):
    cart = session.get("cart", [])

    if item_id in cart:
        cart.remove(item_id)

    session["cart"] = cart

    return redirect(url_for("cart"))


@app.route("/cart")
@login_required
def cart():
    cart_ids = session.get("cart", [])
    items = FoodItem.query.filter(FoodItem.id.in_(cart_ids)).all()

    total = 0
    for cart_id in cart_ids:
        item = FoodItem.query.get(cart_id)
        if item:
            total += item.price

    return render_template("cart.html", items=items, total=total)


@app.route("/checkout")
@login_required
def checkout():
    cart_ids = session.get("cart", [])

    if not cart_ids:
        return redirect(url_for("cart"))

    items = FoodItem.query.filter(FoodItem.id.in_(cart_ids)).all()

    total = 0
    for cart_id in cart_ids:
        item = FoodItem.query.get(cart_id)
        if item:
            total += item.price

    return render_template("checkout.html", total=total, items=items)


@app.route("/place-order", methods=["POST"])
@login_required
def place_order():
    cart_ids = session.get("cart", [])

    if not cart_ids:
        return redirect(url_for("cart"))

    items = FoodItem.query.filter(FoodItem.id.in_(cart_ids)).all()

    total = 0
    item_names_list = []

    for cart_id in cart_ids:
        item = FoodItem.query.get(cart_id)
        if item:
            total += item.price
            item_names_list.append(item.name)

    item_names = ", ".join(item_names_list)
    address = request.form["address"]

    order = Order(
        user_id=current_user.id,
        items=item_names,
        total=total,
        address=address,
        payment_id="Cash on Delivery",
        status="Placed"
    )

    db.session.add(order)
    db.session.commit()

    session["cart"] = []

    return redirect(url_for("orders"))


@app.route("/orders")
@login_required
def orders():
    user_orders = Order.query.filter_by(user_id=current_user.id).all()
    return render_template("orders.html", orders=user_orders)


@app.route("/admin")
@login_required
def admin():
    if current_user.role != "admin":
        return "Access denied"

    orders = Order.query.all()
    foods = FoodItem.query.all()

    return render_template("admin.html", orders=orders, foods=foods)


@app.route("/add-food", methods=["GET", "POST"])
@login_required
def add_food():
    if current_user.role != "admin":
        return "Access denied"

    if request.method == "POST":
        food = FoodItem(
            name=request.form["name"],
            restaurant=request.form["restaurant"],
            category=request.form["category"],
            price=int(request.form["price"]),
            image=request.form["image"]
        )

        db.session.add(food)
        db.session.commit()

        return redirect(url_for("admin"))

    return render_template("add_food.html")


@app.route("/update-status/<int:order_id>", methods=["POST"])
@login_required
def update_status(order_id):
    if current_user.role != "admin":
        return "Access denied"

    order = Order.query.get(order_id)

    if order:
        order.status = request.form["status"]
        db.session.commit()

    return redirect(url_for("admin"))


def create_sample_data():
    with app.app_context():
        db.create_all()

        if not FoodItem.query.first():
            foods = [
                FoodItem(
                    name="Margherita Pizza",
                    restaurant="Pizza Palace",
                    category="Pizza",
                    price=299,
                    image="https://images.unsplash.com/photo-1604382354936-07c5d9983bd3"
                ),
                FoodItem(
                    name="Veg Burger",
                    restaurant="Burger Hub",
                    category="Burger",
                    price=149,
                    image="https://images.unsplash.com/photo-1568901346375-23c9450c58cd"
                ),
                FoodItem(
                    name="Paneer Biryani",
                    restaurant="Biryani House",
                    category="Biryani",
                    price=249,
                    image="https://images.unsplash.com/photo-1631515242808-497c3fbd3972"
                ),
                FoodItem(
                    name="Hakka Noodles",
                    restaurant="China Bowl",
                    category="Chinese",
                    price=199,
                    image="https://images.unsplash.com/photo-1612929633738-8fe44f7ec841"
                ),
                FoodItem(
                    name="Chocolate Brownie",
                    restaurant="Sweet Treats",
                    category="Dessert",
                    price=129,
                    image="https://images.unsplash.com/photo-1606313564200-e75d5e30476c"
                ),
            ]

            db.session.add_all(foods)

        if not User.query.filter_by(email="admin@foodly.com").first():
            admin_user = User(
                name="Admin",
                email="admin@foodly.com",
                password=generate_password_hash("admin123"),
                role="admin"
            )

            db.session.add(admin_user)

        db.session.commit()


if __name__ == "__main__":
    create_sample_data()
    app.run(debug=True)