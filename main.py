from flask import Flask, render_template, request, session, redirect, url_for, jsonify
import pandas as pd
from datetime import timedelta
import logging
from logging.handlers import RotatingFileHandler
import re
import sqlite3
import os
from werkzeug.security import generate_password_hash, check_password_hash


app = Flask(__name__)
app.secret_key = '1percent'

DB_PATH = os.path.join(app.instance_path, 'users.db')


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    os.makedirs(app.instance_path, exist_ok=True)
    with get_db() as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT,
                email TEXT UNIQUE,
                phone TEXT UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()


init_db()

app.config['SESSION_COOKIE_SECURE'] = True
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=15)

HOTEL_PHOTOS = [
    "https://images.unsplash.com/photo-1566073771259-6a8506099945?w=600&q=80",
    "https://images.unsplash.com/photo-1551882547-ff40c63fe5fa?w=600&q=80",
    "https://images.unsplash.com/photo-1542314831-068cd1dbfeeb?w=600&q=80",
    "https://images.unsplash.com/photo-1520250497591-112f2f40a3f4?w=600&q=80",
    "https://images.unsplash.com/photo-1571896349842-33c89424de2d?w=600&q=80",
    "https://images.unsplash.com/photo-1582719478250-c89cae4dc85b?w=600&q=80",
    "https://images.unsplash.com/photo-1445019980597-93fa8acb246c?w=600&q=80",
    "https://images.unsplash.com/photo-1455587734955-081b22074882?w=600&q=80",
    "https://images.unsplash.com/photo-1496417263034-38ec4f0b665a?w=600&q=80",
    "https://images.unsplash.com/photo-1564501049412-61c2a3083791?w=600&q=80",
    "https://images.unsplash.com/photo-1549294413-26f195200c16?w=600&q=80",
    "https://images.unsplash.com/photo-1578683010236-d716f9a3f461?w=600&q=80",
    "https://images.unsplash.com/photo-1590490360182-c33d57733427?w=600&q=80",
    "https://images.unsplash.com/photo-1560347876-aeef00ee58a1?w=600&q=80",
    "https://images.unsplash.com/photo-1522798514-97ceb8c4f1c8?w=600&q=80",
    "https://images.unsplash.com/photo-1444201983204-c43cbd584d93?w=600&q=80",
    "https://images.unsplash.com/photo-1487017159836-4e23ece2e4cf?w=600&q=80",
    "https://images.unsplash.com/photo-1568084680786-a84f91d1153c?w=600&q=80",
    "https://images.unsplash.com/photo-1529290130-4ca3753253ae?w=600&q=80",
    "https://images.unsplash.com/photo-1501117716987-c8c394bb29df?w=600&q=80",
]


def sanitize_input(user_input):
    return re.sub(r'[^\w\s]', '', user_input)


def compute_match_score(hotel, prefs):
    score = 0
    min_p = prefs.get('min_price', 0)
    max_p = prefs.get('max_price', 9999)
    price = hotel['Price_Per_Night']
    mid = (min_p + max_p) / 2
    price_range = (max_p - min_p) / 2 + 1

    if min_p <= price <= max_p:
        score += 40 * (1 - abs(price - mid) / price_range)

    score += (hotel['Rating'] / 5.0) * 30
    score += (hotel.get('Customer_Satisfaction_Score', 5) / 10.0) * 20

    for col in ['WiFi_Included', 'Restaurant_Available', 'Pet_Friendly', 'Business_Center_Available']:
        if hotel.get(col):
            score += 2.5

    vibe_prefs = prefs.get('vibe_preferences', [])
    if vibe_prefs:
        hotel_vibes = compute_vibes(hotel)
        matches = sum(1 for v in vibe_prefs if any(v in hv for hv in hotel_vibes))
        score = min(score + matches * 3, 100)

    return round(min(score, 100))


def compute_vibes(hotel):
    vibes = []
    price = hotel['Price_Per_Night']
    rating = hotel['Rating']
    restaurant = hotel.get('Restaurant_Available', False)
    pet = hotel.get('Pet_Friendly', False)
    biz = hotel.get('Business_Center_Available', False)
    wifi = hotel.get('WiFi_Included', False)

    if rating >= 4.5 and restaurant and price >= 250:
        vibes.append('🌹 Romantic')
    if price >= 350 and rating >= 4.0:
        vibes.append('💎 Luxury')
    if biz and wifi:
        vibes.append('💼 Business')
    if pet and price <= 200:
        vibes.append('🐾 Adventure')
    if pet and restaurant:
        vibes.append('👨‍👩‍👧 Family')
    if price <= 175:
        vibes.append('💸 Budget')
    if restaurant and rating >= 4.0:
        vibes.append('🍽️ Fine Dining')
    if not vibes:
        vibes.append('🏨 Classic Stay')
    return vibes


def get_bot_response(message, hotel):
    msg = message.lower()
    name = hotel.get('Hotel_Name', 'this hotel')
    price = hotel.get('Price_Per_Night', 'N/A')
    location = hotel.get('Location', 'N/A')
    rating = hotel.get('Rating', 'N/A')
    satisfaction = hotel.get('Customer_Satisfaction_Score', 'N/A')
    wifi = hotel.get('WiFi_Included', False)
    pet = hotel.get('Pet_Friendly', False)
    restaurant = hotel.get('Restaurant_Available', False)
    biz = hotel.get('Business_Center_Available', False)
    airport_dist = hotel.get('Distance_to_Airport', 'N/A')
    rooms = hotel.get('Number_of_Rooms', 'N/A')

    if any(w in msg for w in ['hello', 'hi', 'hey', 'howdy', 'greetings']):
        return f"Hey there! 👋 Welcome to {name}. I'm here to answer any questions about our hotel. What would you like to know?"

    if any(w in msg for w in ['price', 'cost', 'rate', 'how much', 'night', 'per night', 'fee']):
        return f"Our rate at {name} is ${price:.2f} per night. Great value for what we offer! 💰"

    if any(w in msg for w in ['location', 'where', 'address', 'city', 'area', 'situated']):
        return f"We're located in {location}. A fantastic destination! 📍"

    if any(w in msg for w in ['rating', 'stars', 'score', 'review', 'rated', 'quality']):
        return f"{name} holds a {rating}/5 star rating with a guest satisfaction score of {satisfaction}/10. We're proud of our guests' feedback! ⭐"

    if any(w in msg for w in ['wifi', 'internet', 'connection', 'online', 'wireless', 'network']):
        if wifi:
            return "Great news — complimentary high-speed WiFi is included in your stay! 📶"
        return "WiFi is not included in the base rate, but can be arranged at the front desk. 📶"

    if any(w in msg for w in ['pet', 'dog', 'cat', 'animal', 'bring my', 'fur']):
        if pet:
            return f"Yes! {name} is pet-friendly. 🐾 Your furry friends are welcome. Please contact us for any specific pet policies."
        return f"Unfortunately {name} does not currently accommodate pets. 🐾 We apologize for the inconvenience."

    if any(w in msg for w in ['restaurant', 'food', 'dining', 'eat', 'breakfast', 'lunch', 'dinner', 'meal', 'hungry']):
        if restaurant:
            return f"We have an on-site restaurant at {name} serving breakfast, lunch, and dinner. 🍽️ Ask the front desk for today's menu!"
        return f"{name} does not have an on-site restaurant, but there are great dining options nearby. 🍽️"

    if any(w in msg for w in ['business', 'meeting', 'conference', 'work', 'office', 'corporate']):
        if biz:
            return f"We have a fully equipped business center at {name}. 💼 Great for meetings and remote work. Ask the front desk for access."
        return f"{name} doesn't have a dedicated business center, but our lobby has comfortable seating for working. 💼"

    if any(w in msg for w in ['airport', 'transport', 'distance', 'far', 'shuttle', 'drive']):
        return f"{name} is approximately {airport_dist:.1f} miles from the nearest airport. ✈️ Ask the front desk about shuttle services."

    if any(w in msg for w in ['check in', 'checkin', 'check-in', 'arrival', 'arrive']):
        return "Check-in time is 3:00 PM. Early check-in may be available upon request — just let us know! 🕒"

    if any(w in msg for w in ['check out', 'checkout', 'check-out', 'departure', 'leave', 'leaving']):
        return "Check-out time is 11:00 AM. Late check-out can sometimes be arranged — ask the front desk the day before. 🕚"

    if any(w in msg for w in ['pool', 'swim', 'gym', 'spa', 'fitness', 'workout', 'sauna', 'jacuzzi']):
        return "Please contact the front desk for current facility hours and availability. We'd love to help you plan your stay! 🏊"

    if any(w in msg for w in ['parking', 'car', 'garage', 'valet', 'park']):
        return "Parking is available at the property. Please contact the front desk for current rates and availability. 🚗"

    if any(w in msg for w in ['cancel', 'refund', 'policy', 'cancellation']):
        return "Cancellation policies vary by rate. Please check your booking confirmation or contact reservations for details. 📋"

    if any(w in msg for w in ['book', 'reserve', 'reservation', 'availability', 'available']):
        return f"To book a stay at {name}, visit the Marriott website or call us directly. We'd love to have you! 🏨"

    if any(w in msg for w in ['room', 'suite', 'bed', 'type', 'floor', 'view']):
        return f"We offer {rooms} rooms across various types — standard rooms, suites, and more. Contact us for current availability and upgrades! 🛏️"

    if any(w in msg for w in ['amenities', 'facilities', 'feature', 'offer', 'include']):
        amenity_list = []
        if wifi: amenity_list.append("Free WiFi")
        if restaurant: amenity_list.append("On-site Restaurant")
        if pet: amenity_list.append("Pet Friendly")
        if biz: amenity_list.append("Business Center")
        amenities_str = ", ".join(amenity_list) if amenity_list else "standard hotel amenities"
        return f"At {name} we offer: {amenities_str}. Ask us about more! ✨"

    if any(w in msg for w in ['thank', 'thanks', 'bye', 'goodbye', 'see you']):
        return f"You're welcome! We hope to see you at {name} soon. Have a wonderful day! 😊"

    return "I'm not sure about that one. Try asking about our price, location, WiFi, check-in times, restaurant, or amenities! 😊"


@app.before_request
def make_session_permanent():
    session.permanent = True


@app.before_request
def log_csrf_token():
    csrf_token = session.get('csrf_token')
    if csrf_token:
        app.logger.info(f"CSRF Token (Placeholder): {csrf_token}")
    else:
        app.logger.info("No CSRF Token found (Placeholder).")


@app.after_request
def add_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Content-Security-Policy'] = (
        "default-src 'self'; "
        "img-src 'self' data: https:; "
        "style-src 'self' 'unsafe-inline' https:; "
        "script-src 'self' 'unsafe-inline' https:; "
        "font-src 'self' https: data:;"
    )
    return response


log_file = 'app.log'
handler = RotatingFileHandler(log_file, maxBytes=10000, backupCount=5)
handler.setLevel(logging.INFO)
app.logger.addHandler(handler)

hotel_data = pd.read_csv('marriott_hotels_dataset.csv')


@app.route('/')
def home():
    return render_template('index.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'attempts' not in session:
        session['attempts'] = 0

    if request.method == 'POST':
        login_type = request.form.get('login-type')

        if session['attempts'] >= 5:
            return render_template('login.html', error="Too many failed attempts. Please try again later.")

        if login_type == 'email':
            email = sanitize_input(request.form.get('email', ''))
            password = request.form.get('password', '')
            with get_db() as conn:
                user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
            if user and check_password_hash(user['password_hash'], password):
                session['attempts'] = 0
                session['user_id'] = user['id']
                session['username'] = user['username'] or email
                app.logger.info(f"Successful login: {email}")
                return redirect(url_for('preferences'))
            session['attempts'] += 1
            return render_template('login.html', error="Invalid email or password.")

        elif login_type == 'phone':
            phone = sanitize_input(request.form.get('phone', ''))
            password = request.form.get('otp', '')
            with get_db() as conn:
                user = conn.execute('SELECT * FROM users WHERE phone = ?', (phone,)).fetchone()
            if user and check_password_hash(user['password_hash'], password):
                session['attempts'] = 0
                session['user_id'] = user['id']
                session['username'] = user['username'] or phone
                app.logger.info(f"Successful phone login: {phone}")
                return redirect(url_for('preferences'))
            session['attempts'] += 1
            return render_template('login.html', error="Invalid phone number or password.")

    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        registration_type = request.form.get('registration-type')

        if registration_type == 'email':
            username = sanitize_input(request.form.get('username', ''))
            email = sanitize_input(request.form.get('email', ''))
            password = request.form.get('password', '')
            if not email or not password:
                return render_template('register.html', error="Email and password are required.")
            hashed = generate_password_hash(password, method='pbkdf2:sha256')
            try:
                with get_db() as conn:
                    conn.execute(
                        'INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)',
                        (username, email, hashed)
                    )
                    conn.commit()
                app.logger.info(f"New email registration: {email}")
                return redirect(url_for('login'))
            except sqlite3.IntegrityError:
                return render_template('register.html', error="An account with that email already exists.")

        elif registration_type == 'phone':
            phone = sanitize_input(request.form.get('phone', ''))
            password = request.form.get('otp', '')
            if not phone or not password:
                return render_template('register.html', error="Phone number and password are required.")
            hashed = generate_password_hash(password, method='pbkdf2:sha256')
            try:
                with get_db() as conn:
                    conn.execute(
                        'INSERT INTO users (phone, password_hash) VALUES (?, ?)',
                        (phone, hashed)
                    )
                    conn.commit()
                app.logger.info(f"New phone registration: {phone}")
                return redirect(url_for('login'))
            except sqlite3.IntegrityError:
                return render_template('register.html', error="An account with that phone number already exists.")

    return render_template('register.html')


@app.route('/preferences', methods=['GET', 'POST'])
def preferences():
    if request.method == 'POST':
        try:
            location = sanitize_input(request.form['location'])
            min_price = float(request.form['min_price'])
            max_price = float(request.form['max_price'])
            vibe_preferences = request.form.getlist('vibe_preferences')

            session['preferences'] = {
                'location': location,
                'min_price': min_price,
                'max_price': max_price,
                'vibe_preferences': vibe_preferences,
            }
            return redirect(url_for('hotels'))
        except Exception as e:
            app.logger.error(f"Error setting preferences: {e}")
            return render_template('preferences.html', error="An error occurred. Please try again.")

    return render_template('preferences.html')


@app.route('/hotels')
def hotels():
    prefs = session.get('preferences', {})
    location = prefs.get('location', '')
    min_price = prefs.get('min_price', 0)
    max_price = prefs.get('max_price', float('inf'))

    filtered = hotel_data[
        (hotel_data['Location'].str.contains(location, case=False, na=False)) &
        (hotel_data['Price_Per_Night'] >= min_price) &
        (hotel_data['Price_Per_Night'] <= max_price)
    ]

    hotels_list = filtered.to_dict(orient='records')

    for i, hotel in enumerate(hotels_list):
        hotel['photo'] = HOTEL_PHOTOS[i % len(HOTEL_PHOTOS)]
        hotel['vibes'] = compute_vibes(hotel)
        hotel['match_score'] = compute_match_score(hotel, prefs)

    hotels_list.sort(key=lambda h: h['match_score'], reverse=True)

    existing_liked = session.get('liked_hotels', [])
    existing_super_liked = session.get('super_liked_hotels', [])

    return render_template('hotels.html', hotels=hotels_list,
                           existing_liked=existing_liked,
                           existing_super_liked=existing_super_liked)


@app.route('/save_liked_hotels', methods=['POST'])
def save_liked_hotels():
    liked_hotels = request.json.get('liked_hotels', [])
    session['liked_hotels'] = liked_hotels
    session.modified = True
    return jsonify({'status': 'ok'})


@app.route('/save_super_liked_hotel', methods=['POST'])
def save_super_liked_hotel():
    hotel = request.json
    if 'super_liked_hotels' not in session:
        session['super_liked_hotels'] = []
    if len(session['super_liked_hotels']) >= 5:
        return jsonify({'status': 'limit_reached'})
    session['super_liked_hotels'].append(hotel)
    session.modified = True
    return jsonify({'status': 'ok', 'count': len(session['super_liked_hotels'])})


@app.route('/delete_liked_hotel', methods=['POST'])
def delete_liked_hotel():
    data = request.json
    hotel_name = data.get('hotel_name')
    list_type = data.get('list_type', 'liked')

    key = 'super_liked_hotels' if list_type == 'super' else 'liked_hotels'
    hotels = session.get(key, [])
    session[key] = [h for h in hotels if h.get('Hotel_Name') != hotel_name]
    session.modified = True
    return jsonify({'status': 'ok'})


@app.route('/liked_hotels')
def liked_hotels():
    liked = session.get('liked_hotels', [])
    super_liked = session.get('super_liked_hotels', [])
    return render_template('liked_hotels.html', liked_hotels=liked, super_liked_hotels=super_liked)


@app.route('/chat/<hotel_name>', methods=['GET', 'POST'])
def chat(hotel_name):
    hotel_row = hotel_data[hotel_data['Hotel_Name'] == hotel_name]
    hotel = hotel_row.iloc[0].to_dict() if not hotel_row.empty else {}

    messages = session.get(f'chat_{hotel_name}', [])

    if not messages:
        intro = get_bot_response('hello', hotel) if hotel else f"Welcome to {hotel_name}! How can I help you?"
        messages.append({'sender': 'bot', 'text': intro})

    if request.method == 'POST':
        user_message = request.form.get('message', '').strip()
        if user_message:
            messages.append({'sender': 'user', 'text': user_message})
            bot_reply = get_bot_response(user_message, hotel)
            messages.append({'sender': 'bot', 'text': bot_reply})
            session[f'chat_{hotel_name}'] = messages
            session.modified = True

    return render_template('chat.html', hotel_name=hotel_name, messages=messages)


@app.route('/logout')
def logout():
    user = session.get('user', 'Unknown user')
    session.clear()
    app.logger.info(f"User {user} logged out")
    return redirect(url_for('home'))


if __name__ == '__main__':
    app.run(debug=True)
