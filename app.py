from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory, send_file, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from werkzeug.utils import secure_filename
import os, uuid, datetime, qrcode, io, base64

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app = Flask(__name__)
app.config["SECRET_KEY"] = "dev-secret-key-change-me"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(BASE_DIR, "data.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024  # 5MB

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)

# Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    fullname = db.Column(db.String(120))
    bio = db.Column(db.Text)
    profile_pic = db.Column(db.String(256))
    organization = db.Column(db.String(20), nullable=False)  # farmer, distributor, retailer
    mobile = db.Column(db.String(15), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)

    posts = db.relationship("Post", backref="author", lazy=True)
    likes = db.relationship("Like", backref="user", lazy=True)
    comments = db.relationship("Comment", backref="user", lazy=True)
    bought_orders = db.relationship("Order", foreign_keys="Order.buyer_id", backref="buyer", lazy=True)
    sold_orders = db.relationship("Order", foreign_keys="Order.seller_id", backref="seller", lazy=True)

    def check_password(self, password):
        return bcrypt.check_password_hash(self.password_hash, password)

    def set_password(self, password):
        self.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    author_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    title = db.Column(db.String(200))
    description = db.Column(db.Text)
    image = db.Column(db.String(256))
    price = db.Column(db.Float)
    unit = db.Column(db.String(10), default="kg")  # kg or dozen
    stock = db.Column(db.Float, nullable=False, default=0)  # initial stock quantity
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    likes = db.relationship("Like", backref="post", lazy=True, cascade="all, delete-orphan")
    comments = db.relationship("Comment", backref="post", lazy=True, cascade="all, delete-orphan")

    def available_stock(self):
        # Calculate available stock: initial stock - sum of accepted order quantities
        accepted_orders = Order.query.filter_by(post_id=self.id, status="accepted").all()
        sold_quantity = sum(float(order.quantity.split()[0]) for order in accepted_orders if order.quantity.split()[0].replace('.', '').isdigit())
        return max(0, self.stock - sold_quantity)

class Like(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey("post.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey("post.id"), nullable=False)
    text = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    buyer_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    seller_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey("post.id"), nullable=False)
    quantity = db.Column(db.String(50), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default="pending")  # pending, accepted, rejected
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    post = db.relationship("Post", backref="orders", lazy=True)
    rating = db.relationship("Rating", backref="order", lazy=True, uselist=False)

class Rating(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("order.id"), nullable=False)
    rating = db.Column(db.Integer, nullable=False)  # 1-5 stars
    review = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("order.id"), nullable=False)
    sender_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    text = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    sender = db.relationship("User", backref="sent_messages", lazy=True)

# Helpers
@app.context_processor
def inject_user():
    username = session.get("username")
    user = None
    if username:
        user = User.query.filter_by(username=username).first()
    return dict(current_user=user)

def save_file(file_storage):
    if not file_storage:
        return None
    filename = secure_filename(file_storage.filename)
    if filename == "":
        return None
    unique = str(uuid.uuid4())[:8] + "_" + filename
    dest = os.path.join(app.config["UPLOAD_FOLDER"], unique)
    file_storage.save(dest)
    return "uploads/" + unique

# Routes
@app.route("/")
def index():
    if session.get("username"):
        return redirect(url_for("home"))
    return render_template("index.html")

@app.route("/register", methods=["POST"])
def register():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()
    fullname = request.form.get("fullname", "").strip()
    organization = request.form.get("organization", "").strip()
    mobile = request.form.get("mobile", "").strip()
    email = request.form.get("email", "").strip()
    if not username or not password or not organization or not mobile or not email:
        flash("All fields are required.", "danger")
        return redirect(url_for("index"))
    if organization not in ["farmer", "distributor", "retailer"]:
        flash("Invalid organization.", "danger")
        return redirect(url_for("index"))
    if User.query.filter_by(username=username).first():
        flash("Username already exists. Please login.", "warning")
        return redirect(url_for("index"))
    if User.query.filter_by(mobile=mobile).first():
        flash("Mobile number already registered.", "warning")
        return redirect(url_for("index"))
    if User.query.filter_by(email=email).first():
        flash("Email already registered.", "warning")
        return redirect(url_for("index"))
    u = User(username=username, fullname=fullname, organization=organization, mobile=mobile, email=email)
    u.set_password(password)
    # optional profile pic
    pic = request.files.get("profile_pic")
    if pic and pic.filename:
        u.profile_pic = save_file(pic)
    db.session.add(u)
    db.session.commit()
    session["username"] = username
    flash("Registered and logged in.", "success")
    return redirect(url_for("home"))

@app.route("/login", methods=["POST"])
def login():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()
    u = User.query.filter_by(username=username).first()
    if not u or not u.check_password(password):
        flash("Invalid credentials.", "danger")
        return redirect(url_for("index"))
    session["username"] = username
    flash("Logged in.", "success")
    return redirect(url_for("home"))

@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out.", "info")
    return redirect(url_for("index"))

@app.route("/home")
def home():
    q = request.args.get("q", "").strip().lower()
    page = max(1, int(request.args.get("page", 1)))
    per_page = 5
    query = Post.query.order_by(Post.created_at.desc())
    if q:
        query = query.filter((Post.title.ilike(f"%{q}%")) | (Post.description.ilike(f"%{q}%")) | (User.username.ilike(f"%{q}%"))).join(User, Post.author)
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    posts = pagination.items
    return render_template("home.html", posts=posts, pagination=pagination, q=q)

@app.route("/profile/<username>", methods=["GET", "POST"])
def profile(username):
    user = User.query.filter_by(username=username).first_or_404()
    can_post = session.get("username") == username
    if request.method == "POST" and can_post:
        # create post
        title = request.form.get("title","").strip()
        description = request.form.get("description","").strip()
        price = request.form.get("price","").strip()
        unit = request.form.get("unit","kg").strip()
        stock = request.form.get("stock","").strip()
        image = request.files.get("image")
        image_path = save_file(image)
        try:
            price = float(price) if price else None
        except ValueError:
            price = None
        try:
            stock = float(stock) if stock else 0
        except ValueError:
            stock = 0
        p = Post(author_id=user.id, title=title, description=description, image=image_path, price=price, unit=unit, stock=stock)
        db.session.add(p)
        db.session.commit()
        flash("Post created.", "success")
        return redirect(url_for("profile", username=username))
    posts = Post.query.filter_by(author_id=user.id).order_by(Post.created_at.desc()).all()
    return render_template("profile.html", profile_user=user, posts=posts, can_post=can_post)

@app.route("/edit_profile", methods=["POST"])
def edit_profile():
    if not session.get("username"):
        flash("Login required.", "danger")
        return redirect(url_for("index"))
    user = User.query.filter_by(username=session["username"]).first()
    fullname = request.form.get("fullname","").strip()
    bio = request.form.get("bio","").strip()
    pic = request.files.get("profile_pic")
    if fullname:
        user.fullname = fullname
    user.bio = bio
    if pic and pic.filename:
        user.profile_pic = save_file(pic)
    db.session.commit()
    flash("Profile updated.", "success")
    return redirect(url_for("profile", username=user.username))

@app.route("/like/<int:post_id>", methods=["POST"])
def like(post_id):
    if not session.get("username"):
        flash("Login required.", "danger")
        return redirect(url_for("index"))
    user = User.query.filter_by(username=session["username"]).first()
    post = Post.query.get_or_404(post_id)
    existing = Like.query.filter_by(user_id=user.id, post_id=post.id).first()
    if existing:
        db.session.delete(existing)
        db.session.commit()
        flash("Unliked.", "info")
    else:
        l = Like(user_id=user.id, post_id=post.id)
        db.session.add(l)
        db.session.commit()
        flash("Liked.", "success")
    return redirect(request.referrer or url_for("home"))

@app.route("/comment/<int:post_id>", methods=["POST"])
def comment(post_id):
    if not session.get("username"):
        flash("Login required.", "danger")
        return redirect(url_for("index"))
    text = request.form.get("comment","").strip()
    if not text:
        flash("Comment cannot be empty.", "warning")
        return redirect(request.referrer or url_for("home"))
    user = User.query.filter_by(username=session["username"]).first()
    post = Post.query.get_or_404(post_id)
    c = Comment(user_id=user.id, post_id=post.id, text=text)
    db.session.add(c)
    db.session.commit()
    flash("Comment added.", "success")
    return redirect(request.referrer or url_for("home"))

@app.route("/place_order/<int:post_id>", methods=["GET", "POST"])
def place_order(post_id):
    if not session.get("username"):
        flash("Login required.", "danger")
        return redirect(url_for("index"))
    user = User.query.filter_by(username=session["username"]).first()
    post = Post.query.get_or_404(post_id)
    if user.organization != "distributor" or post.author.organization != "farmer":
        flash("Only distributors can place orders on farmer posts.", "danger")
        return redirect(url_for("home"))
    if request.method == "POST":
        quantity = request.form.get("quantity", "").strip()
        amount = request.form.get("amount", "").strip()
        if not quantity or not amount:
            flash("Quantity and amount are required.", "danger")
            return redirect(url_for("place_order", post_id=post_id))
        try:
            amount = float(amount)
        except ValueError:
            flash("Invalid amount.", "danger")
            return redirect(url_for("place_order", post_id=post_id))
        # Parse quantity number
        try:
            qty_num = float(quantity.split()[0])
        except (ValueError, IndexError):
            flash("Invalid quantity format. Use e.g., '10 kg'.", "danger")
            return redirect(url_for("place_order", post_id=post_id))
        available = post.available_stock()
        if qty_num > available:
            flash(f"Insufficient stock. Available: {available} {post.unit}.", "danger")
            return redirect(url_for("place_order", post_id=post_id))
        order = Order(buyer_id=user.id, seller_id=post.author_id, post_id=post.id, quantity=quantity, amount=amount)
        db.session.add(order)
        db.session.commit()
        flash("Order placed successfully.", "success")
        return redirect(url_for("profile", username=user.username))
    return render_template("place_order.html", post=post)

@app.route("/rate_order/<int:order_id>", methods=["GET", "POST"])
def rate_order(order_id):
    if not session.get("username"):
        flash("Login required.", "danger")
        return redirect(url_for("index"))
    user = User.query.filter_by(username=session["username"]).first()
    order = Order.query.get_or_404(order_id)
    if order.buyer_id != user.id:
        flash("You can only rate your own orders.", "danger")
        return redirect(url_for("profile", username=user.username))
    if order.status != "accepted":
        flash("You can only rate accepted orders.", "warning")
        return redirect(url_for("profile", username=user.username))
    existing_rating = Rating.query.filter_by(order_id=order.id).first()
    if existing_rating:
        flash("Order already rated.", "info")
        return redirect(url_for("profile", username=user.username))
    if request.method == "POST":
        rating = request.form.get("rating")
        review = request.form.get("review", "").strip()
        if not rating:
            flash("Rating is required.", "danger")
            return redirect(request.url)
        try:
            rating = int(rating)
            if rating < 1 or rating > 5:
                raise ValueError
        except ValueError:
            flash("Invalid rating.", "danger")
            return redirect(request.url)
        r = Rating(order_id=order.id, rating=rating, review=review)
        db.session.add(r)
        db.session.commit()
        flash("Rating submitted.", "success")
        return redirect(url_for("orders"))
    return render_template("rate_order.html", order=order)

@app.route("/orders")
def orders():
    if not session.get("username"):
        flash("Login required.", "danger")
        return redirect(url_for("index"))
    user = User.query.filter_by(username=session["username"]).first()
    # Orders where user is buyer or seller
    user_orders = Order.query.filter((Order.buyer_id == user.id) | (Order.seller_id == user.id)).order_by(Order.created_at.desc()).all()
    return render_template("orders.html", orders=user_orders)

@app.route("/accept_order/<int:order_id>", methods=["POST"])
def accept_order(order_id):
    if not session.get("username"):
        flash("Login required.", "danger")
        return redirect(url_for("index"))
    user = User.query.filter_by(username=session["username"]).first()
    order = Order.query.get_or_404(order_id)
    if order.seller_id != user.id:
        flash("You can only accept your own orders.", "danger")
        return redirect(url_for("orders"))
    if order.status != "pending":
        flash("Order is not pending.", "warning")
        return redirect(url_for("orders"))
    order.status = "accepted"
    db.session.commit()
    flash("Order accepted.", "success")
    return redirect(url_for("orders"))

@app.route("/reject_order/<int:order_id>", methods=["POST"])
def reject_order(order_id):
    if not session.get("username"):
        flash("Login required.", "danger")
        return redirect(url_for("index"))
    user = User.query.filter_by(username=session["username"]).first()
    order = Order.query.get_or_404(order_id)
    if order.seller_id != user.id:
        flash("You can only reject your own orders.", "danger")
        return redirect(url_for("orders"))
    if order.status != "pending":
        flash("Order is not pending.", "warning")
        return redirect(url_for("orders"))
    order.status = "rejected"
    db.session.commit()
    flash("Order rejected.", "success")
    return redirect(url_for("orders"))

@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(os.path.join(BASE_DIR, "static", "uploads"), filename)

@app.route("/chat/<int:order_id>", methods=["GET", "POST"])
def chat(order_id):
    if not session.get("username"):
        flash("Login required.", "danger")
        return redirect(url_for("index"))
    user = User.query.filter_by(username=session["username"]).first()
    order = Order.query.get_or_404(order_id)
    if order.status not in ["pending", "accepted"] or (order.buyer_id != user.id and order.seller_id != user.id):
        flash("Access denied.", "danger")
        return redirect(url_for("orders"))
    if request.method == "POST":
        text = request.form.get("message", "").strip()
        if text:
            msg = Message(order_id=order.id, sender_id=user.id, text=text)
            db.session.add(msg)
            db.session.commit()
            flash("Message sent.", "success")
        return redirect(url_for("chat", order_id=order_id))
    messages = Message.query.filter_by(order_id=order.id).order_by(Message.created_at.asc()).all()
    return render_template("chat.html", order=order, messages=messages)

@app.route("/analytics")
def analytics():
    if not session.get("username"):
        flash("Login required.", "danger")
        return redirect(url_for("index"))
    user = User.query.filter_by(username=session["username"]).first()
    data = {}

    if user.organization == "farmer":
        # Farmer analytics: sales data
        sold_orders = Order.query.filter_by(seller_id=user.id, status="accepted").all()
        total_sales = sum(order.amount for order in sold_orders)
        total_orders = len(sold_orders)
        avg_rating = db.session.query(db.func.avg(Rating.rating)).join(Order).filter(Order.seller_id == user.id).scalar() or 0
        top_products = db.session.query(Post.title, db.func.count(Order.id)).join(Order, Order.post_id == Post.id).filter(Post.author_id == user.id, Order.status == "accepted").group_by(Post.id).order_by(db.func.count(Order.id).desc()).limit(5).all()

        data = {
            "type": "farmer",
            "total_sales": total_sales,
            "total_orders": total_orders,
            "avg_rating": round(avg_rating, 1),
            "top_products": top_products
        }

    elif user.organization in ["distributor", "retailer"]:
        # Distributor/Retailer analytics: purchase data
        bought_orders = Order.query.filter_by(buyer_id=user.id, status="accepted").all()
        total_purchases = sum(order.amount for order in bought_orders)
        total_orders = len(bought_orders)
        favorite_sellers = db.session.query(User.username, db.func.count(Order.id)).join(Order, Order.seller_id == User.id).filter(Order.buyer_id == user.id, Order.status == "accepted").group_by(User.id).order_by(db.func.count(Order.id).desc()).limit(5).all()

        data = {
            "type": "buyer",
            "total_purchases": total_purchases,
            "total_orders": total_orders,
            "favorite_sellers": favorite_sellers
        }

    # General market trends (for all users)
    popular_products = db.session.query(Post.title, db.func.count(Order.id)).join(Order).filter(Order.status == "accepted").group_by(Post.id).order_by(db.func.count(Order.id).desc()).limit(10).all()
    data["popular_products"] = popular_products

    return render_template("analytics.html", data=data)

@app.route("/qr/<mobile>")
def generate_qr(mobile):
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(mobile)
    qr.make(fit=True)
    img = qr.make_image(fill='black', back_color='white')
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return send_file(buf, mimetype='image/png')

if __name__ == "__main__":
    # create DB tables if not exist
    with app.app_context():
        db.drop_all()
        db.create_all()
        print("Database schema updated successfully!")

        # Create test data
        farmer = User(username='testfarmer', fullname='Test Farmer', organization='farmer', mobile='1234567890', email='farmer@test.com')
        farmer.set_password('pass')
        db.session.add(farmer)

        buyer = User(username='testbuyer', fullname='Test Buyer', organization='distributor', mobile='0987654321', email='buyer@test.com')
        buyer.set_password('pass')
        db.session.add(buyer)
        db.session.commit()

        # Create a post by farmer
        post = Post(author_id=farmer.id, title='Test Product', description='Test desc', price=10.0, unit='kg', stock=100.0)
        db.session.add(post)
        db.session.commit()

        # Create an order by buyer
        order = Order(buyer_id=buyer.id, seller_id=farmer.id, post_id=post.id, quantity='5 kg', amount=50.0)
        db.session.add(order)
        db.session.commit()

        # Accept the order
        order.status = 'accepted'
        db.session.commit()

        print("Test data created successfully!")
    app.run(debug=True)
