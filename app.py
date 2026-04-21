from flask import Flask, session, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from flask_cors import CORS
from sqlalchemy import or_
from datetime import datetime, UTC
from functools import wraps
import os

app = Flask(__name__)
app.secret_key = 'bwiohgoiwhbgoiwhjoigbwoi'
CORS(app, supports_credentials=True)

IS_PROD = os.environ.get('IS_PROD')

if IS_PROD:
    app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://admin:password@/hfweddinghirecarsdb?unix_socket=/cloudsql/hfweddinghirecars-dev:australia-southeast1:cloudsql-mysql-dev'

    app.config.update(
        SESSION_COOKIE_SECURE=True,
        SESSION_COOKIE_SAMESITE='None'
    )
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:password@localhost/hfweddinghirecarsdb'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SESSION_COOKIE_SECURE'] = False

print("IS_PROD:", IS_PROD)

db = SQLAlchemy(app)

class User(db.Model):
    __tablename__ = 'hfuser'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(255), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(45), nullable=False)
    status = db.Column(db.String(45), nullable=False)
    last_login = db.Column(db.DateTime, default=None)
    first_name = db.Column(db.String(255), nullable=False)
    last_name = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255), nullable=False)
    phone = db.Column(db.String(45), nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "username": self.username,
            "email": self.email,
            "phone": self.phone,
            "last_login": self.last_login,
            "role": self.role,
            "status": self.status
        }

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):

        print(f"DEBUG: Session -> {dict(session)}")

        user_id = session.get('user_id')
        
        if not user_id:
            return jsonify({"status": "error", "message": "Unauthorized"}), 401
        
        return f(*args, **kwargs)
    return decorated_function

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    user = User.query.filter_by(username=username).first()

    if user and check_password_hash(user.password, password):

        session['user_id'] = user.id

        user.last_login = datetime.now(UTC)
        db.session.commit()
        
        return jsonify({
            "status": "success",
            "message": "Logged in successfully",
            "user": {
                "username": user.username,
                "role": user.role
            }
        }), 200
    
    return jsonify({"status": "error", "message": "Invalid credentials"}), 401

@app.route('/api/admin', methods=['GET'])
def get_users():

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    
    search = request.args.get('search', '')

    select_date_from = request.args.get('select_date_from', '')
    select_date_to = request.args.get('select_date_to', '')

    select_status = request.args.getlist('select_status[]')

    query = User.query
    if search:
        search_filter = f"%{search}%"
        query = query.filter(
            or_(
                User.first_name.ilike(search_filter),
                User.last_name.ilike(search_filter),
                User.username.ilike(search_filter),
                User.email.ilike(search_filter),
                User.phone.ilike(search_filter),
                User.last_login.ilike(search_filter),
            )
        )

    if select_date_from:
        query = query.filter(User.last_login >= select_date_from)

    if select_date_to:
        query = query.filter(User.last_login <= select_date_to)

    if select_status:
        query = query.filter(User.status.in_(select_status))
    
    pagination = query.paginate(page=page, per_page=per_page)
    start_record = (page - 1) * per_page + 1
    end_record = min(start_record + per_page - 1, pagination.total)
    
    return jsonify({
        "status": "success",
        "data": [user.to_dict() for user in pagination.items],
        "pagination": {
            "total_records": pagination.total,
            "total_pages": pagination.pages,
            "current_page": pagination.page,
            "per_page": per_page,
            "from": start_record if pagination.total > 0 else 0,
            "to": end_record if pagination.total > 0 else 0
        }
    })

@app.route('/api/check-username', methods=['GET'])
def check_username():
    username = request.args.get('username')
    if not username:
        return jsonify({"exists": False}), 200
    
    user_exists = User.query.filter_by(username=username).first() is not None
    
    return jsonify({"exists": user_exists}), 200

@app.route('/api/admin', methods=['POST'])
def add_user():
    data = request.json

    username = data.get('username')
    if User.query.filter_by(username=username).first():
        return jsonify({
            "status": "error",
            "message": "Username already exist."
        }), 400

    hashed_password = generate_password_hash(data.get('password'))
    new_user = User(
        first_name=data.get('first_name'),
        last_name=data.get('last_name'),
        username=data.get('username'),
        password=hashed_password,
        email=data.get('email'),
        phone=data.get('phone'),
        role='Admin',
        status=data.get('status')
    )
    db.session.add(new_user)
    db.session.commit()

    return jsonify({
            "status": "success",
            "message": "Add admin successfully",
            "user": {
                "id": new_user.id,
                "role": new_user.role
            }
        }), 201

@app.route('/api/admin/<int:user_id>', methods=['PUT'])
def update_user(user_id):
    data = request.json
    user = User.query.get_or_404(user_id)
    
    try:
        user.first_name = data.get('first_name', user.first_name)
        user.last_name = data.get('last_name', user.last_name)
        user.email = data.get('email', user.email)
        user.phone = data.get('phone', user.phone)
        user.status = data.get('status', user.status)

        
        if data.get('password'):
            user.password = generate_password_hash(data.get('password'))
            
        db.session.commit()
        
        return jsonify({
            "status": "success",
            "message": f"User {user_id} updated successfully"
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

if __name__ == '__main__':
    app.run(debug=True)