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
from sklearn.ensemble import RandomForestRegressor
from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder
import joblib
import sys

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'tailor-cost-prediction-secret-key-2024')

# Database configuration - Use PostgreSQL on Render, SQLite locally
basedir = os.path.abspath(os.path.dirname(__file__))

# Check if running on Render (has DATABASE_URL environment variable)
if os.environ.get('DATABASE_URL'):
    # Use PostgreSQL on Render
    database_url = os.environ.get('DATABASE_URL')
    # Fix for Render's PostgreSQL URL format
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    print("Using PostgreSQL database on Render")
else:
    # Use SQLite locally
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'tailor.db')
    print("Using SQLite database locally")

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# ==================== DATABASE MODELS ====================
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True, nullable=False)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    first_name = db.Column(db.String(50), default='')
    last_name = db.Column(db.String(50), default='')
    institution = db.Column(db.String(200), default='University of Zululand')
    bio = db.Column(db.Text, default='')
    avatar_initials = db.Column(db.String(4), default='')
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def get_full_name(self):
        return f"{self.first_name} {self.last_name}"
    
    def save(self):
        if not self.avatar_initials:
            first = self.first_name[:1].upper() if self.first_name else ''
            last = self.last_name[:1].upper() if self.last_name else ''
            self.avatar_initials = (first + last) or self.email[:2].upper()
        db.session.add(self)
        db.session.commit()


class EstimateHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    garment = db.Column(db.String(50), nullable=False)
    fabric_type = db.Column(db.String(50), nullable=False)
    fabric_m = db.Column(db.Float, nullable=False)
    price_per_m = db.Column(db.Float, nullable=False)
    material_cost = db.Column(db.Float, nullable=False)
    garment_cost = db.Column(db.Float, default=0)
    overhead_cost = db.Column(db.Float, default=0)
    total_cost = db.Column(db.Float, nullable=False)
    label = db.Column(db.String(200), default='')
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    
    user = db.relationship('User', backref=db.backref('estimates', lazy=True))


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# ==================== ML PREDICTOR ====================
FABRIC_PRICE_MAP = {
    'Cotton': 90, 'Denim': 114, 'Leather': 275, 'Linen': 140,
    'Nylon': 70, 'Polyester': 68, 'Silk': 173, 'Wool': 217,
}

GARMENT_MAP = {
    'blouse': 'Blouse', 'coat': 'Coat', 'dress': 'Dress', 'hoodie': 'Hoodie',
    'jacket': 'Jacket', 'jersey': 'Jersey', 'shirt': 'Shirt', 'shorts': 'Shorts',
    'skirt': 'Skirt', 'suit': 'Suit', 'tracksuit': 'Tracksuit', 'trousers': 'Trousers',
    'pants': 'Trousers', 'jeans': 'Trousers', 'jean': 'Trousers'
}

FABRIC_MAP = {
    'cotton': 'Cotton', 'denim': 'Denim', 'jean': 'Denim', 'leather': 'Leather',
    'linen': 'Linen', 'nylon': 'Nylon', 'polyester': 'Polyester', 'silk': 'Silk', 'wool': 'Wool'
}

GARMENTS = ['Blouse', 'Coat', 'Dress', 'Hoodie', 'Jacket', 'Jersey', 'Shirt', 'Shorts', 'Skirt', 'Suit', 'Tracksuit', 'Trousers']
FABRICS = ['Cotton', 'Denim', 'Leather', 'Linen', 'Nylon', 'Polyester', 'Silk', 'Wool']


class TailorPredictor:
    _model = None
    
    def load(self, model_path, dataset_path):
        try:
            self._model = joblib.load(model_path)
            print(f"Loaded model from {model_path}")
        except Exception as e:
            print(f"Could not load model ({e}). Training new model...")
            self._train(dataset_path)
    
    def _train(self, dataset_path):
        df = pd.read_csv(dataset_path)
        X = df[['Garment', 'Fabric_Type', 'Fabric_m', 'Price_per_m']]
        y = df['Total_Cost_ZAR']
        
        preprocessor = ColumnTransformer([
            ('cat', OneHotEncoder(sparse_output=False), ['Garment', 'Fabric_Type']),
            ('num', 'passthrough', ['Fabric_m', 'Price_per_m'])
        ])
        
        self._model = Pipeline([
            ('pre', preprocessor),
            ('rf', RandomForestRegressor(n_estimators=100, random_state=42))
        ])
        self._model.fit(X, y)
        joblib.dump(self._model, 'random_forest_model.joblib')
        print("Model trained and saved")
    
    def predict(self, garment, fabric_type, fabric_m):
        price = FABRIC_PRICE_MAP.get(fabric_type, 100)
        material_cost = round(fabric_m * price, 2)
        
        input_df = pd.DataFrame([{
            'Garment': garment, 'Fabric_Type': fabric_type,
            'Fabric_m': fabric_m, 'Price_per_m': price
        }])
        
        total = float(self._model.predict(input_df)[0])
        overhead = round(total * 0.08, 2)
        garment_cost = round(total - overhead, 2)
        
        return {
            'total_cost': round(total, 2),
            'material_cost': material_cost,
            'price_per_m': price,
            'garment_cost': garment_cost,
            'overhead_cost': overhead,
            'fabric_m': fabric_m,
            'garment': garment,
            'fabric_type': fabric_type,
        }

predictor = TailorPredictor()


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
            flash(f'Welcome back!', 'success')
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
                username=request.form['email'],
                first_name=request.form['first_name'],
                last_name=request.form['last_name']
            )
            user.set_password(request.form['password'])
            user.save()
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
    recent = EstimateHistory.query.filter_by(user_id=current_user.id).order_by(EstimateHistory.created_at.desc()).limit(6).all()
    return render_template('estimator.html', 
                          recent=recent, 
                          user=current_user,
                          garments=GARMENTS,
                          fabrics=FABRICS)

@app.route('/estimator/recent')
@login_required
def get_recent_estimates():
    recent = EstimateHistory.query.filter_by(user_id=current_user.id).order_by(EstimateHistory.created_at.desc()).limit(6).all()
    html = ''
    for est in recent:
        html += f'<div class="recent"><svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg><span title="{est.label}">{est.label[:32]}</span></div>'
    if not html:
        html = '<div class="recent muted-item"><span>No estimates yet</span></div>'
    return jsonify({'recent': html})

@app.route('/api/predict', methods=['POST'])
@login_required
def predict_ajax():
    try:
        data = request.get_json()
        result = predictor.predict(data['garment'], data['fabric_type'], float(data['fabric_m']))
        estimate = EstimateHistory(
            user_id=current_user.id,
            garment=result['garment'],
            fabric_type=result['fabric_type'],
            fabric_m=result['fabric_m'],
            price_per_m=result['price_per_m'],
            material_cost=result['material_cost'],
            garment_cost=result['garment_cost'],
            overhead_cost=result['overhead_cost'],
            total_cost=result['total_cost']
        )
        db.session.add(estimate)
        db.session.commit()
        return jsonify({'success': True, **result})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/chat', methods=['POST'])
@login_required
def chat_predict():
    try:
        data = request.get_json()
        message = data.get('message', '').lower()
        
        meters = None
        match = re.search(r'(\d+(?:\.\d+)?)\s*(?:m|meter|meters)', message)
        if match:
            meters = float(match.group(1))
        
        garment = None
        for key, val in GARMENT_MAP.items():
            if key in message:
                garment = val
                break
        
        fabric = None
        for key, val in FABRIC_MAP.items():
            if key in message:
                fabric = val
                break
        
        if not garment:
            return jsonify({'success': False, 'reply': 'Missing garment'})
        if not fabric:
            return jsonify({'success': False, 'reply': 'Missing fabric'})
        if not meters:
            return jsonify({'success': False, 'reply': 'Missing meters'})
        
        result = predictor.predict(garment, fabric, meters)
        estimate = EstimateHistory(
            user_id=current_user.id,
            garment=result['garment'],
            fabric_type=result['fabric_type'],
            fabric_m=result['fabric_m'],
            price_per_m=result['price_per_m'],
            material_cost=result['material_cost'],
            garment_cost=result['garment_cost'],
            overhead_cost=result['overhead_cost'],
            total_cost=result['total_cost']
        )
        db.session.add(estimate)
        db.session.commit()
        
        return jsonify({'success': True, 'reply': f"{fabric} {garment}, {meters}m - Total: R{result['total_cost']:,.2f}", **result})
    except Exception as e:
        return jsonify({'success': False, 'reply': str(e)}), 500

@app.route('/history')
@login_required
def history():
    search_query = request.args.get('search', '').strip()
    garment_filter = request.args.get('garment', '')
    fabric_filter = request.args.get('fabric', '')
    page = request.args.get('page', 1, type=int)
    
    query = EstimateHistory.query.filter_by(user_id=current_user.id)
    
    if search_query:
        query = query.filter(
            db.or_(
                EstimateHistory.garment.ilike(f'%{search_query}%'),
                EstimateHistory.fabric_type.ilike(f'%{search_query}%'),
                EstimateHistory.label.ilike(f'%{search_query}%')
            )
        )
    
    if garment_filter:
        query = query.filter_by(garment=garment_filter)
    if fabric_filter:
        query = query.filter_by(fabric_type=fabric_filter)
    
    pagination = query.order_by(EstimateHistory.created_at.desc()).paginate(page=page, per_page=15, error_out=False)
    estimates = pagination.items
    
    all_estimates = EstimateHistory.query.filter_by(user_id=current_user.id).all()
    total_est = len(all_estimates)
    avg_cost = round(sum(e.total_cost for e in all_estimates) / total_est, 2) if total_est else 0
    max_cost = max((e.total_cost for e in all_estimates), default=0)
    
    return render_template('history.html',
                          estimates=estimates,
                          pagination=pagination,
                          search_query=search_query,
                          garment_filter=garment_filter,
                          fabric_filter=fabric_filter,
                          garments=GARMENTS,
                          fabrics=FABRICS,
                          total_est=total_est,
                          avg_cost=avg_cost,
                          max_cost=max_cost,
                          user=current_user)

@app.route('/history/delete/<int:id>', methods=['POST'])
@login_required
def delete_estimate(id):
    est = EstimateHistory.query.get_or_404(id)
    if est.user_id == current_user.id:
        db.session.delete(est)
        db.session.commit()
        flash('Estimate deleted successfully', 'success')
    return redirect(url_for('history'))

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        current_user.first_name = request.form.get('first_name')
        current_user.last_name = request.form.get('last_name')
        current_user.institution = request.form.get('institution')
        current_user.bio = request.form.get('bio')
        current_user.save()
        flash('Profile updated!', 'success')
        return redirect(url_for('profile'))
    
    estimates = EstimateHistory.query.filter_by(user_id=current_user.id).all()
    total_est = len(estimates)
    total_spend = sum(e.total_cost for e in estimates)
    return render_template('profile.html', user=current_user, total_est=total_est, total_spend=total_spend)


# ==================== RUN ====================
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        print("Database ready")
    
    # Load model
    model_path = os.path.join(basedir, 'fine_tuned_random_forest_regressor.joblib')
    dataset_path = os.path.join(basedir, 'group_7_dataset.csv')
    
    if os.path.exists(model_path) and os.path.exists(dataset_path):
        predictor.load(model_path, dataset_path)
        print("ML model loaded!")
    else:
        print("Warning: Model or dataset not found. Training will happen on first request.")
    
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)