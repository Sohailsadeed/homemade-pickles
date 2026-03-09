from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import uuid
import boto3
import os
from dotenv import load_dotenv
import json

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY')


# ================== DynamoDB CONNECTION ==================

dynamodb = boto3.resource(
    "dynamodb",
    region_name=os.getenv("AWS_REGION")
)

users_table = dynamodb.Table('users')
orders_table = dynamodb.Table('orders')


# ================== TEMPORARY PRODUCT DATA ==================

products = {
    'non_veg_pickles': [
        {'id': 1, 'name': 'Chicken Pickle', 'weights': {'250': 600, '500': 1200, '1000': 1800}},
        {'id': 2, 'name': 'Fish Pickle', 'weights': {'250': 200, '500': 400, '1000': 800}},
        {'id': 3, 'name': 'Gongura Mutton', 'weights': {'250': 400, '500': 800, '1000': 1600}},
        {'id': 4, 'name': 'Mutton Pickle', 'weights': {'250': 400, '500': 800, '1000': 1600}},
        {'id': 5, 'name': 'Gongura Prawns', 'weights': {'250': 600, '500': 1200, '1000': 1800}},
        {'id': 6, 'name': 'Chicken Pickle (Gongura)', 'weights': {'250': 350, '500': 700, '1000': 1050}}
    ],
    'veg_pickles': [
        {'id': 7, 'name': 'Traditional Mango Pickle', 'weights': {'250': 150, '500': 280, '1000': 500}},
        {'id': 8, 'name': 'Zesty Lemon Pickle', 'weights': {'250': 120, '500': 220, '1000': 400}},
        {'id': 9, 'name': 'Tomato Pickle', 'weights': {'250': 130, '500': 240, '1000': 450}},
        {'id': 10, 'name': 'Kakarakaya Pickle', 'weights': {'250': 130, '500': 240, '1000': 450}},
        {'id': 11, 'name': 'Chintakaya Pickle', 'weights': {'250': 130, '500': 240, '1000': 450}},
        {'id': 12, 'name': 'Spicy Pandu Mirchi', 'weights': {'250': 130, '500': 240, '1000': 450}}
    ],
    'snacks': [
        {'id': 7, 'name': 'Banana Chips', 'weights': {'250': 300, '500': 600, '1000': 800}},
        {'id': 8, 'name': 'Crispy Aam-Papad', 'weights': {'250': 150, '500': 300, '1000': 600}},
        {'id': 9, 'name': 'Crispy Chekka Pakodi', 'weights': {'250': 50, '500': 100, '1000': 200}}
    ]
}


# ================== AUTHENTICATION ROUTES ==================

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/login', methods=['GET', 'POST'])
def login():

    if request.method == 'POST':

        username = request.form['username'].strip()
        password = request.form['password']

        try:

            response = users_table.get_item(
                Key={'username': username}
            )

            user = response.get('Item')

            if not user:
                return render_template('login.html', error='User not found')

            if check_password_hash(user['password'], password):

                session['logged_in'] = True
                session['username'] = username
                session.setdefault('cart', [])

                return redirect(url_for('home'))

            return render_template('login.html', error='Invalid password')

        except Exception as e:

            app.logger.error(f"Login error: {str(e)}")
            return render_template('login.html', error='Login failed. Try again later')

    return render_template('login.html')


@app.route('/signup', methods=['GET', 'POST'])
def signup():

    if request.method == 'POST':

        username = request.form['username'].strip()
        email = request.form['email'].strip()
        password = request.form['password']

        try:

            # check if user exists
            response = users_table.get_item(
                Key={'username': username}
            )

            if 'Item' in response:
                return render_template('signup.html', error='Username already exists')

            hashed_password = generate_password_hash(password)

            users_table.put_item(
                Item={
                    'username': username,
                    'email': email,
                    'password': hashed_password
                }
            )

            return redirect(url_for('login'))

        except Exception as e:

            app.logger.error(f"Signup error: {str(e)}")
            return render_template('signup.html', error='Registration failed')

    return render_template('signup.html')


@app.route('/logout')
def logout():

    session.clear()
    return redirect(url_for('login'))


# ================== PRODUCT PAGES ==================

@app.route('/home')
def home():

    if not session.get('logged_in'):
        return redirect(url_for('login'))

    return render_template('home.html')


@app.route('/non_veg_pickles')
def non_veg_pickles():

    if not session.get('logged_in'):
        return redirect(url_for('login'))

    return render_template(
        'non_veg_pickles.html',
        products=products['non_veg_pickles']
    )


@app.route('/veg_pickles')
def veg_pickles():

    if not session.get('logged_in'):
        return redirect(url_for('login'))

    return render_template(
        'veg_pickles.html',
        products=products['veg_pickles']
    )


@app.route('/snacks')
def snacks():

    if not session.get('logged_in'):
        return redirect(url_for('login'))

    return render_template(
        'snacks.html',
        products=products['snacks']
    )


# ================== CART & CHECKOUT ==================

@app.route('/cart')
def cart():

    if not session.get('logged_in'):
        return redirect(url_for('login'))

    return render_template('cart.html')


@app.route('/checkout', methods=['GET', 'POST'])
def checkout():

    if not session.get('logged_in'):
        return redirect(url_for('login'))

    if request.method == 'POST':

        try:

            name = request.form.get('name', '').strip()
            address = request.form.get('address', '').strip()
            phone = request.form.get('phone', '').strip()
            payment_method = request.form.get('payment', '').strip()
            cart_data = request.form.get('cart_data', '[]')
            total_amount = request.form.get('total_amount', '0')

            cart_items = json.loads(cart_data)

            orders_table.put_item(
                Item={
                    'order_id': str(uuid.uuid4()),
                    'username': session.get('username', 'Guest'),
                    'customer': {
                        'name': name,
                        'address': address,
                        'phone': phone
                    },
                    'items': cart_items,
                    'total_amount': float(total_amount),
                    'payment_method': payment_method,
                    'timestamp': str(datetime.now())
                }
            )

            return redirect(url_for('success'))

        except Exception as e:

            app.logger.error(f"Checkout error: {str(e)}")
            return render_template(
                'checkout.html',
                error="An unexpected error occurred."
            )

    return render_template('checkout.html')


@app.route('/success')
def success():

    return render_template('success.html')


if __name__ == '__main__':
    app.run(
    host="0.0.0.0",
    port=int(os.getenv("PORT", 5000)),
    debug=os.getenv("DEBUG", "False") == "True"
    )