"""
Tailor Cost Prediction System - Flask Version
University of Zululand – Group 7
Deployed on Render
"""

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import pandas as pd
import re
import os
import sys

app = Flask(__name__)
app.secret_key = 'tailor-cost-prediction-secret-key-2024'

basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'tailor.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# ==================== DATABASE MODELS ====================
class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    first_name = db.Column(db.String(50), default='')
    last_name = db.Column(db.String(50), default='')
    
    def set_password(self, password):
        self.password = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password, password)
    
    def get_full_name(self):
        return f"{self.first_name} {self.last_name}"

class Estimate(db.Model):
    __tablename__ = 'estimates'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    garment = db.Column(db.String(50), nullable=False)
    fabric = db.Column(db.String(50), nullable=False)
    meters = db.Column(db.Float, nullable=False)
    price_per_m = db.Column(db.Float, nullable=False)
    material_cost = db.Column(db.Float, nullable=False)
    total_cost = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    
    user = db.relationship('User', backref=db.backref('estimates', lazy=True))

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ==================== CREATE TABLES (Forced) ====================
def init_db():
    """Create all database tables"""
    with app.app_context():
        db.create_all()
        print("✅ Database tables created/verified")

# Call this immediately
init_db()

# ==================== ML PREDICTOR ====================
FABRIC_PRICES = {
    'Cotton': 90, 'Denim': 114, 'Leather': 275, 'Linen': 140,
    'Nylon': 70, 'Polyester': 68, 'Silk': 173, 'Wool': 217,
}

GARMENT_LIST = ['Blouse', 'Coat', 'Dress', 'Hoodie', 'Jacket', 'Jersey', 'Shirt', 'Shorts', 'Skirt', 'Suit', 'Tracksuit', 'Trousers']
FABRIC_LIST = ['Cotton', 'Denim', 'Leather', 'Linen', 'Nylon', 'Polyester', 'Silk', 'Wool']

# Simple mappings for chat
GARMENT_MAP = {
    'blouse': 'Blouse', 'dress': 'Dress', 'shirt': 'Shirt', 'jacket': 'Jacket',
    'trousers': 'Trousers', 'jeans': 'Trousers', 'skirt': 'Skirt', 'coat': 'Coat',
    'hoodie': 'Hoodie', 'suit': 'Suit', 'shorts': 'Shorts', 'jersey': 'Jersey',
    'tracksuit': 'Tracksuit'
}

FABRIC_MAP = {
    'cotton': 'Cotton', 'silk': 'Silk', 'denim': 'Denim', 'wool': 'Wool',
    'leather': 'Leather', 'linen': 'Linen', 'polyester': 'Polyester', 'nylon': 'Nylon'
}

class Predictor:
    def predict(self, garment, fabric, meters):
        price = FABRIC_PRICES.get(fabric, 100)
        material_cost = round(meters * price, 2)
        
        # Simple formula based on garment complexity
        complexity = {
            'Blouse': 2.2, 'Shirt': 1.9, 'Trousers': 1.5,
            'Dress': 1.4, 'Skirt': 1.5, 'Jacket': 1.3, 'Coat': 1.2,
            'Suit': 1.15, 'Hoodie': 1.4, 'Shorts': 1.7, 'Jersey': 1.5,
            'Tracksuit': 1.3
        }
        multiplier = complexity.get(garment, 1.4)
        total = round(material_cost * multiplier, 2)
        overhead = round(total * 0.08, 2)
        garment_cost = round(total - overhead, 2)
        
        return {
            'total_cost': total,
            'material_cost': material_cost,
            'price_per_m': price,
            'garment_cost': garment_cost,
            'overhead_cost': overhead,
            'fabric_m': meters,
            'garment': garment,
            'fabric_type': fabric,
        }

predictor = Predictor()

# ==================== ROUTES ====================
@app.route('/')
def root():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('estimator'))
    
    if request.method == 'POST':
        user = User.query.filter_by(email=request.form['email']).first()
        if user and user.check_password(request.form['password']):
            login_user(user)
            flash('Welcome back!', 'success')
            return redirect(url_for('estimator'))
        flash('Invalid email or password.', 'error')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('estimator'))
    
    if request.method == 'POST':
        if request.form['password'] != request.form['confirm_password']:
            flash('Passwords do not match', 'error')
        elif User.query.filter_by(email=request.form['email']).first():
            flash('Email already exists', 'error')
        else:
            user = User(
                email=request.form['email'],
                first_name=request.form['first_name'],
                last_name=request.form['last_name']
            )
            user.set_password(request.form['password'])
            db.session.add(user)
            db.session.commit()
            login_user(user)
            flash('Account created!', 'success')
            return redirect(url_for('estimator'))
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/estimator', methods=['GET'])
@login_required
def estimator():
    recent = Estimate.query.filter_by(user_id=current_user.id).order_by(Estimate.created_at.desc()).limit(6).all()
    return render_template('estimator.html', 
                          recent=recent, 
                          user=current_user,
                          garments=GARMENT_LIST,
                          fabrics=FABRIC_LIST)

@app.route('/estimator/recent')
@login_required
def get_recent_estimates():
    recent = Estimate.query.filter_by(user_id=current_user.id).order_by(Estimate.created_at.desc()).limit(6).all()
    html = ''
    for est in recent:
        html += f'<div class="recent"><span>{est.garment} - R{est.total_cost:.0f}</span></div>'
    if not html:
        html = '<div class="recent muted-item"><span>No estimates yet</span></div>'
    return jsonify({'recent': html})

@app.route('/api/predict', methods=['POST'])
@login_required
def predict_ajax():
    try:
        data = request.get_json()
        result = predictor.predict(data['garment'], data['fabric_type'], float(data['fabric_m']))
        
        estimate = Estimate(
            user_id=current_user.id,
            garment=result['garment'],
            fabric=result['fabric_type'],
            meters=result['fabric_m'],
            price_per_m=result['price_per_m'],
            material_cost=result['material_cost'],
            total_cost=result['total_cost']
        )
        db.session.add(estimate)
        db.session.commit()
        
        return jsonify({'success': True, **result})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/chat', methods=['POST'])
@login_required
def chat():
    try:
        data = request.get_json()
        message = data.get('message', '').lower()
        
        # Parse meters
        meters = None
        match = re.search(r'(\d+(?:\.\d+)?)\s*(?:m|meter|meters)', message)
        if match:
            meters = float(match.group(1))
        
        # Parse garment
        garment = None
        for key, val in GARMENT_MAP.items():
            if key in message:
                garment = val
                break
        if not garment:
            for g in GARMENT_LIST:
                if g.lower() in message:
                    garment = g
                    break
        
        # Parse fabric
        fabric = None
        for key, val in FABRIC_MAP.items():
            if key in message:
                fabric = val
                break
        if not fabric:
            for f in FABRIC_LIST:
                if f.lower() in message:
                    fabric = f
                    break
        
        # Validate
        missing = []
        if not garment:
            missing.append('garment')
        if not fabric:
            missing.append('fabric')
        if not meters:
            missing.append('meters')
        
        if missing:
            return jsonify({'success': False, 'reply': f"Missing: {', '.join(missing)}. Try: 'silk dress 3m'"})
        
        result = predictor.predict(garment, fabric, meters)
        
        estimate = Estimate(
            user_id=current_user.id,
            garment=result['garment'],
            fabric=result['fabric_type'],
            meters=result['fabric_m'],
            price_per_m=result['price_per_m'],
            material_cost=result['material_cost'],
            total_cost=result['total_cost']
        )
        db.session.add(estimate)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'reply': f"{fabric} {garment}, {meters}m - Total: R{result['total_cost']:,.2f}",
            **result
        })
    except Exception as e:
        return jsonify({'success': False, 'reply': str(e)}), 500

@app.route('/history')
@login_required
def history():
    estimates = Estimate.query.filter_by(user_id=current_user.id).order_by(Estimate.created_at.desc()).all()
    return render_template('history.html', estimates=estimates, user=current_user)

@app.route('/history/delete/<int:id>', methods=['POST'])
@login_required
def delete_estimate(id):
    est = Estimate.query.get_or_404(id)
    if est.user_id == current_user.id:
        db.session.delete(est)
        db.session.commit()
        flash('Estimate deleted', 'success')
    return redirect(url_for('history'))

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        current_user.first_name = request.form.get('first_name')
        current_user.last_name = request.form.get('last_name')
        db.session.commit()
        flash('Profile updated!', 'success')
        return redirect(url_for('profile'))
    
    estimates = Estimate.query.filter_by(user_id=current_user.id).all()
    total_est = len(estimates)
    total_spend = sum(e.total_cost for e in estimates)
    return render_template('profile.html', user=current_user, total_est=total_est, total_spend=total_spend)


# ==================== RUN ====================
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)