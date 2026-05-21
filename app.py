import os
import uuid
import base64
import hashlib
import cv2
import json
import math
import io
import random
import pathlib
import numpy as np
from flask import Flask, render_template, request, jsonify, send_file, session, redirect, url_for, Response
from werkzeug.utils import secure_filename
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from sqlalchemy import or_, func, and_
try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    HAS_MATPLOTLIB = True
except:
    HAS_MATPLOTLIB = False

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, letter
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak
    from reportlab.lib.units import inch
    from reportlab.graphics.shapes import Drawing, Rect, String, Line
    from reportlab.graphics import renderPDF
    HAS_REPORTLAB = True
except:
    HAS_REPORTLAB = False

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'potholeai-secret-key-2026')

base_dir = os.environ.get('RENDER_DATA_DIR', '')
if not base_dir or not os.path.isdir(base_dir):
    base_dir = os.getcwd()
db_path = os.path.join(base_dir, 'database.db')

db_url = os.environ.get('DATABASE_URL')
if db_url and db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = db_url or f'sqlite:///{db_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join(base_dir, 'uploads')
app.config['RESULT_FOLDER'] = os.path.join(base_dir, 'results')
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['RESULT_FOLDER'], exist_ok=True)

@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['RESULT_FOLDER'], exist_ok=True)

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

detector = None

def get_detector():
    global detector
    if detector is None:
        try:
            from detection import PotholeDetector
            detector = PotholeDetector()
            print("YOLO model loaded successfully")
        except Exception as e:
            print(f"WARNING: Failed to load YOLO model: {e}")
    return detector

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'mp4', 'avi', 'mov'}

def calculate_severity(pothole_count, avg_confidence):
    if pothole_count >= 5:
        return 'severe'
    elif pothole_count >= 3:
        return 'high'
    elif pothole_count >= 1:
        return 'moderate'
    return 'low'

def calculate_road_quality(pothole_count, severity, avg_confidence=0):
    base_score = 100
    
    severity_weight = {'severe': 15, 'high': 10, 'moderate': 5, 'low': 2}
    deduction = severity_weight.get(severity, 5) * pothole_count
    
    return max(0, min(100, int(base_score - deduction)))

def get_quality_grade(score):
    if score >= 80:
        return {'grade': 'A', 'label': 'Excellent', 'color': '#00ff88'}
    elif score >= 60:
        return {'grade': 'B', 'label': 'Good', 'color': '#7fff00'}
    elif score >= 40:
        return {'grade': 'C', 'label': 'Fair', 'color': '#ffc107'}
    elif score >= 20:
        return {'grade': 'D', 'label': 'Poor', 'color': '#ff6b00'}
    else:
        return {'grade': 'F', 'label': 'Critical', 'color': '#ff0044'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))
    is_admin = db.Column(db.Boolean, default=False)
    is_corporation = db.Column(db.Boolean, default=False)
    corporation_name = db.Column(db.String(200), nullable=True)
    corporation_email = db.Column(db.String(200), nullable=True)
    corporation_city = db.Column(db.String(100), nullable=True)

class Detection(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(200))
    file_type = db.Column(db.String(10), default='image')
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)
    address = db.Column(db.String(500), nullable=True)
    pothole_count = db.Column(db.Integer)
    avg_confidence = db.Column(db.Float)
    severity = db.Column(db.String(20), default='moderate', nullable=True)
    road_quality_score = db.Column(db.Integer, default=100, nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(50), default='pending')
    complaint_filed = db.Column(db.Boolean, default=False)
    complaint_id = db.Column(db.String(100), nullable=True)
    complaint_date = db.Column(db.DateTime, nullable=True)
    gps_route = db.Column(db.Text, nullable=True)
    is_night_detection = db.Column(db.Boolean, default=False)
    duplicate_of_id = db.Column(db.Integer, nullable=True)
    reported_by_user = db.Column(db.String(100), nullable=True)
    user_description = db.Column(db.Text, nullable=True)
    image_hash = db.Column(db.String(64), nullable=True)

class HotspotZone(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    center_lat = db.Column(db.Float)
    center_lng = db.Column(db.Float)
    radius_km = db.Column(db.Float, default=0.5)
    pothole_count = db.Column(db.Integer, default=0)
    avg_severity = db.Column(db.String(20), default='moderate')
    last_updated = db.Column(db.DateTime, default=datetime.utcnow)
    report_count = db.Column(db.Integer, default=0)

class AuthorityReport(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    report_id = db.Column(db.String(50), unique=True)
    authority_name = db.Column(db.String(200))
    authority_email = db.Column(db.String(200))
    detection_ids = db.Column(db.Text)
    total_potholes = db.Column(db.Integer, default=0)
    hotspot_zones = db.Column(db.Text)
    report_date = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(50), default='pending')
    authority_response = db.Column(db.Text, nullable=True)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def create_tables():
    with app.app_context():
        db.create_all()
        
        for col_query in [
            'ALTER TABLE detection ADD COLUMN file_type VARCHAR(10) DEFAULT "image"',
            'ALTER TABLE detection ADD COLUMN severity VARCHAR(20) DEFAULT "moderate"',
            'ALTER TABLE detection ADD COLUMN road_quality_score INTEGER DEFAULT 100',
            'ALTER TABLE detection ADD COLUMN complaint_filed BOOLEAN DEFAULT 0',
            'ALTER TABLE detection ADD COLUMN complaint_id VARCHAR(100)',
            'ALTER TABLE detection ADD COLUMN complaint_date DATETIME',
            'ALTER TABLE detection ADD COLUMN gps_route TEXT',
            'ALTER TABLE detection ADD COLUMN is_night_detection BOOLEAN DEFAULT 0',
            'ALTER TABLE detection ADD COLUMN duplicate_of_id INTEGER',
            'ALTER TABLE detection ADD COLUMN reported_by_user VARCHAR(100)',
            'ALTER TABLE detection ADD COLUMN user_description TEXT',
            'ALTER TABLE detection ADD COLUMN image_hash VARCHAR(64)'
        ]:
            try:
                db.session.execute(db.text(col_query))
                db.session.commit()
            except:
                pass
        
        for col_query in [
            'ALTER TABLE user ADD COLUMN is_corporation BOOLEAN DEFAULT 0',
            'ALTER TABLE user ADD COLUMN corporation_name VARCHAR(200)',
            'ALTER TABLE user ADD COLUMN corporation_email VARCHAR(200)',
            'ALTER TABLE user ADD COLUMN corporation_city VARCHAR(100)'
        ]:
            try:
                db.session.execute(db.text(col_query))
                db.session.commit()
            except:
                pass
        
        try:
            db.session.execute(db.text("UPDATE detection SET severity = 'moderate' WHERE severity IS NULL"))
            db.session.execute(db.text("UPDATE detection SET road_quality_score = 100 WHERE road_quality_score IS NULL"))
            db.session.execute(db.text("UPDATE detection SET complaint_filed = 0 WHERE complaint_filed IS NULL"))
            db.session.commit()
        except:
            pass
        
        try:
            db.session.execute(db.text("SELECT 1 FROM authority_report LIMIT 1"))
        except:
            db.create_all()
        
        if not User.query.filter_by(username='admin').first():
            admin = User(username='admin', password=generate_password_hash('admin123'), is_admin=True)
            db.session.add(admin)
        
        if not User.query.filter_by(username='corporation').first():
            corp = User(username='corporation', password=generate_password_hash('corp123'), is_corporation=True,
                       corporation_name='Municipal Corporation', corporation_email='corp@municipality.gov', corporation_city='Default City')
            db.session.add(corp)
        
        db.session.commit()

def calculate_distance(lat1, lon1, lat2, lon2):
    R = 6371
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    a = math.sin(delta_lat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c

def detect_duplicate(lat, lng, days=7, radius_km=0.1):
    if lat is None or lng is None:
        return None
    
    week_ago = datetime.utcnow() - timedelta(days=days)
    recent_detections = Detection.query.filter(
        Detection.timestamp >= week_ago,
        Detection.latitude.isnot(None),
        Detection.longitude.isnot(None)
    ).all()
    
    for det in recent_detections:
        distance = calculate_distance(lat, lng, det.latitude, det.longitude)
        if distance <= radius_km:
            return {'duplicate': True, 'original_id': det.id, 'distance_km': round(distance, 3)}
    
    return {'duplicate': False}

def compute_image_hash(filepath):
    try:
        with open(filepath, 'rb') as f:
            return hashlib.md5(f.read()).hexdigest()
    except:
        return None

def update_hotspots():
    detections = Detection.query.filter(
        Detection.latitude.isnot(None),
        Detection.longitude.isnot(None),
        Detection.status != 'fixed'
    ).all()
    
    HotspotZone.query.delete()
    
    hotspot_groups = {}
    for det in detections:
        key = f"{round(det.latitude, 3)}_{round(det.longitude, 3)}"
        if key not in hotspot_groups:
            hotspot_groups[key] = {'lat': det.latitude, 'lng': det.longitude, 'count': 0, 'severities': []}
        hotspot_groups[key]['count'] += 1
        hotspot_groups[key]['severities'].append(det.severity)
    
    severity_order = {'severe': 4, 'high': 3, 'moderate': 2, 'low': 1}
    for zone_data in hotspot_groups.values():
        if zone_data['count'] >= 2:
            avg_severity = max(zone_data['severities'], key=lambda x: severity_order.get(x, 0))
            hotspot = HotspotZone(
                center_lat=zone_data['lat'],
                center_lng=zone_data['lng'],
                pothole_count=zone_data['count'],
                avg_severity=avg_severity,
                last_updated=datetime.utcnow(),
                report_count=zone_data['count']
            )
            db.session.add(hotspot)
    
    db.session.commit()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        role = request.form.get('role', 'admin')
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            if user.is_corporation:
                return redirect(url_for('corporation_dashboard'))
            return redirect(url_for('admin'))
        return render_template('login.html', error='Invalid credentials')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/corporation')
@login_required
def corporation_dashboard():
    if not current_user.is_corporation and not current_user.is_admin:
        return redirect(url_for('index'))
    
    year = request.args.get('year', type=int)
    month = request.args.get('month', type=int)
    
    query = Detection.query.filter(
        Detection.complaint_filed == True,
        Detection.status.in_(['pending', 'reported_to_corp', 'in_progress', 'fixed'])
    )
    
    if year:
        query = query.filter(db.extract('year', Detection.timestamp) == year)
    if month:
        query = query.filter(db.extract('month', Detection.timestamp) == month)
    
    detections = query.order_by(Detection.timestamp.desc()).all()
    total = Detection.query.count()
    total_reported = Detection.query.filter(Detection.complaint_filed == True).count()
    pending = Detection.query.filter(Detection.complaint_filed == True, Detection.status.in_(['pending', 'reported_to_corp'])).count()
    in_progress = Detection.query.filter(Detection.complaint_filed == True, Detection.status == 'in_progress').count()
    fixed = Detection.query.filter(Detection.complaint_filed == True, Detection.status == 'fixed').count()
    
    reports = AuthorityReport.query.order_by(AuthorityReport.report_date.desc()).all()
    
    years = db.session.query(db.extract('year', Detection.timestamp).distinct()).all()
    years = [y[0] for y in years if y[0]]
    
    corp_name = current_user.corporation_name or 'Municipal Corporation'
    
    return render_template('corporation.html',
                         detections=detections,
                         reports=reports,
                         total=total,
                         total_reported=total_reported,
                         pending=pending,
                         in_progress=in_progress,
                         fixed=fixed,
                         selected_year=year,
                         selected_month=month,
                         years=years,
                         corp_name=corp_name)

@app.route('/admin')
@login_required
def admin():
    if not current_user.is_admin:
        return redirect(url_for('index'))
    
    year = request.args.get('year', type=int)
    month = request.args.get('month', type=int)
    day = request.args.get('day', type=int)
    
    query = Detection.query
    
    if year:
        query = query.filter(db.extract('year', Detection.timestamp) == year)
    if month:
        query = query.filter(db.extract('month', Detection.timestamp) == month)
    if day:
        query = query.filter(db.extract('day', Detection.timestamp) == day)
    
    detections = query.order_by(Detection.timestamp.desc()).all()
    total = Detection.query.count()
    pending = Detection.query.filter_by(status='pending').count()
    fixed = Detection.query.filter_by(status='fixed').count()
    
    years = db.session.query(db.extract('year', Detection.timestamp).distinct()).all()
    years = [y[0] for y in years if y[0]]
    
    return render_template('admin.html', 
                         detections=detections, 
                         total=total, 
                         pending=pending,
                         fixed=fixed,
                         selected_year=year,
                         selected_month=month,
                         selected_day=day,
                         years=years)

@app.route('/update-status/<int:id>', methods=['POST'])
@login_required
def update_status(id):
    if not current_user.is_admin and not current_user.is_corporation:
        return jsonify({'error': 'Unauthorized'}), 403
    data = request.get_json()
    new_status = data.get('status', 'pending')
    det = Detection.query.get(id)
    if not det:
        return jsonify({'error': 'Not found'}), 404
    det.status = new_status
    db.session.commit()
    return jsonify({'success': True, 'status': new_status})

@app.route('/update-authority-report-status/<int:id>', methods=['POST'])
@login_required
def update_authority_report_status(id):
    if not current_user.is_admin and not current_user.is_corporation:
        return jsonify({'error': 'Unauthorized'}), 403
    data = request.get_json()
    new_status = data.get('status', 'pending')
    report = AuthorityReport.query.get(id)
    if not report:
        return jsonify({'error': 'Not found'}), 404
    report.status = new_status

    det_ids = json.loads(report.detection_ids) if report.detection_ids else []
    if new_status == 'in_progress':
        for did in det_ids:
            det = Detection.query.get(did)
            if det:
                det.status = 'in_progress'
    elif new_status == 'completed':
        for did in det_ids:
            det = Detection.query.get(did)
            if det:
                det.status = 'fixed'
    elif new_status == 'rejected':
        for did in det_ids:
            det = Detection.query.get(did)
            if det:
                det.status = 'rejected'
                det.complaint_filed = False

    db.session.commit()
    return jsonify({'success': True, 'status': new_status})

@app.route('/delete-authority-report/<int:id>', methods=['POST'])
@login_required
def delete_authority_report(id):
    if not current_user.is_admin and not current_user.is_corporation:
        return jsonify({'error': 'Unauthorized'}), 403
    report = AuthorityReport.query.get(id)
    if report:
        db.session.delete(report)
        db.session.commit()
        return jsonify({'success': True})
    return jsonify({'error': 'Not found'}), 404

@app.route('/api/authority-reports')
@login_required
def get_authority_reports():
    reports = AuthorityReport.query.order_by(AuthorityReport.report_date.desc()).all()
    result = []
    for r in reports:
        det_ids = json.loads(r.detection_ids) if r.detection_ids else []
        first_det = Detection.query.get(det_ids[0]) if det_ids else None
        location = ''
        filename = ''
        if first_det:
            filename = first_det.filename or ''
            if first_det.latitude and first_det.longitude:
                location = f"{first_det.latitude:.4f}, {first_det.longitude:.4f}"
            elif first_det.address:
                location = first_det.address
        result.append({
            'id': r.id, 'report_id': r.report_id, 'authority': r.authority_name,
            'email': r.authority_email, 'total_potholes': r.total_potholes,
            'date': r.report_date.strftime('%Y-%m-%d %H:%M'), 'status': r.status,
            'detection_ids': det_ids, 'filename': filename, 'location': location
        })
    return jsonify({'reports': result})

@app.route('/api/road-quality-stats')
def road_quality_stats():
    total = Detection.query.count()
    if total == 0:
        return jsonify({'avg_quality': 100, 'by_severity': {'low': 0, 'moderate': 0, 'high': 0, 'severe': 0}, 'total_detections': 0})
    
    detections = Detection.query.all()
    quality_scores = [d.road_quality_score if d.road_quality_score is not None else 100 for d in detections]
    avg_quality = sum(quality_scores) / total
    
    low_count = Detection.query.filter(db.or_(Detection.severity == 'low', Detection.severity.is_(None))).count()
    moderate_count = Detection.query.filter(Detection.severity == 'moderate').count()
    high_count = Detection.query.filter(Detection.severity == 'high').count()
    severe_count = Detection.query.filter(Detection.severity == 'severe').count()
    
    by_severity = {
        'low': low_count,
        'moderate': moderate_count,
        'high': high_count,
        'severe': severe_count
    }
    
    return jsonify({
        'avg_quality': round(avg_quality, 1),
        'by_severity': by_severity,
        'total_detections': total
    })

@app.route('/file-complaint/<int:id>', methods=['POST'])
@login_required
def file_complaint(id):
    if not current_user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 403
    
    detection = Detection.query.get(id)
    if not detection:
        return jsonify({'error': 'Not found'}), 404
    
    if detection.complaint_filed:
        return jsonify({'error': 'Complaint already filed', 'complaint_id': detection.complaint_id})
    
    complaint_id = f"MC{ datetime.now().strftime('%Y%m%d%H%M%S') }{id:04d}"
    
    detection.complaint_filed = True
    detection.complaint_id = complaint_id
    detection.complaint_date = datetime.utcnow()
    db.session.commit()
    
    return jsonify({
        'success': True,
        'complaint_id': complaint_id,
        'message': f'Complaint filed successfully! ID: {complaint_id}'
    })

@app.route('/api/complaints')
def complaints_list():
    complaints = Detection.query.filter_by(complaint_filed=True).order_by(Detection.complaint_date.desc()).all()
    
    result = []
    for c in complaints:
        result.append({
            'id': c.id,
            'complaint_id': c.complaint_id or 'N/A',
            'date': c.complaint_date.strftime('%Y-%m-%d %H:%M') if c.complaint_date else 'N/A',
            'location': c.address or f"{c.latitude}, {c.longitude}",
            'pothole_count': c.pothole_count,
            'severity': c.severity or 'moderate',
            'status': c.status
        })
    
    return jsonify({'complaints': result})

@app.route('/api/gps-track', methods=['POST'])
def gps_track():
    data = request.get_json()
    route_data = data.get('route', [])
    detections = data.get('detections', 0)
    
    if route_data:
        route_json = json.dumps(route_data)
        
        for i, coord in enumerate(route_data):
            if coord.get('latitude') and coord.get('longitude'):
                severity = calculate_severity(detections, 0)
                road_quality = calculate_road_quality(detections, severity)
                
                new_detection = Detection(
                    filename=f"gps_{uuid.uuid4().hex}.jpg",
                    file_type='image',
                    latitude=coord['latitude'],
                    longitude=coord['longitude'],
                    address=coord.get('address', 'GPS Location'),
                    pothole_count=detections,
                    avg_confidence=0,
                    severity=severity,
                    road_quality_score=road_quality,
                    status='pending',
                    gps_route=route_json
                )
                db.session.add(new_detection)
        
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'GPS route recorded'})
    
    return jsonify({'error': 'No route data'}), 400

@app.route('/results/<filename>')
def serve_result(filename):
    return send_file(os.path.join(app.config['RESULT_FOLDER'], filename))

@app.route('/uploads/<filename>')
def serve_upload(filename):
    return send_file(os.path.join(app.config['UPLOAD_FOLDER'], filename))

@app.route('/api/map-data')
def map_data():
    reported_only = request.args.get('reported', type=int, default=0)
    query = Detection.query.order_by(Detection.timestamp.desc())
    if reported_only:
        query = query.filter(Detection.complaint_filed == True, Detection.status.in_(['in_progress', 'fixed', 'completed']))
    detections = query.all()
    markers = []
    for d in detections:
        fname = d.filename if d.filename and os.path.exists(os.path.join(app.config['RESULT_FOLDER'], d.filename)) else None
        markers.append({
            'id': d.id,
            'display_id': f"PD-{d.id:05d}",
            'lat': d.latitude, 'lng': d.longitude,
            'pothole_count': d.pothole_count, 'severity': d.severity or 'moderate',
            'road_quality': d.road_quality_score if d.road_quality_score is not None else 100, 'status': d.status or 'pending',
            'avg_confidence': round(d.avg_confidence * 100) if d.avg_confidence else 0,
            'date': d.timestamp.strftime('%Y-%m-%d %H:%M') if d.timestamp else 'N/A',
            'filename': fname, 'file_type': d.file_type or 'image',
            'is_night': d.is_night_detection or False, 'complaint_filed': d.complaint_filed or False,
            'is_duplicate': d.duplicate_of_id is not None
        })
    return jsonify({'markers': markers})

@app.route('/api/analytics')
def analytics():
    reported_only = request.args.get('reported', type=int, default=0)
    query = Detection.query
    if reported_only:
        query = query.filter(Detection.complaint_filed == True, Detection.status.in_(['in_progress', 'fixed', 'completed']))
    
    total = query.count()
    pending = query.filter(Detection.status == 'pending').count() if not reported_only else 0
    in_progress = query.filter(Detection.status.in_(['in_progress', 'reported_to_corp'])).count()
    fixed = query.filter(Detection.status == 'fixed').count()
    rejected = query.filter(Detection.status == 'rejected').count()
    
    detections = query.all()
    if detections:
        avg_quality = sum(d.road_quality_score if d.road_quality_score is not None else 100 for d in detections) / len(detections)
        avg_confidence = sum(d.avg_confidence or 0 for d in detections) / len(detections)
    else:
        avg_quality = 100
        avg_confidence = 0
    
    grade = get_quality_grade(avg_quality)
    
    by_severity = {'low': 0, 'moderate': 0, 'high': 0, 'severe': 0}
    by_status = {'pending': pending, 'in_progress': in_progress, 'fixed': fixed, 'rejected': rejected}
    monthly = {}
    affected_areas = {}
    
    for d in detections:
        sev = d.severity or 'moderate'
        if sev in by_severity: by_severity[sev] += 1
        
        if d.timestamp:
            key = d.timestamp.strftime('%Y-%m')
            monthly[key] = monthly.get(key, 0) + 1
        
        if d.address:
            area = d.address.split(',')[-1].strip() if ',' in d.address else d.address
            if area not in affected_areas:
                affected_areas[area] = {'count': 0, 'total_quality': 0}
            affected_areas[area]['count'] += 1
            affected_areas[area]['total_quality'] += d.road_quality_score if d.road_quality_score is not None else 100
    
    area_list = [{'area': k, 'count': v['count'], 'avg_quality': round(v['total_quality'] / v['count'])} for k, v in affected_areas.items()]
    area_list.sort(key=lambda x: x['count'], reverse=True)
    
    monthly_list = [{'month': k, 'count': v} for k, v in sorted(monthly.items())]
    
    hotspots_list = HotspotZone.query.order_by(HotspotZone.pothole_count.desc()).limit(5).all()
    hotspot_data = [{'lat': h.center_lat, 'lng': h.center_lng, 'pothole_count': h.pothole_count, 'severity': h.avg_severity} for h in hotspots_list]
    
    return jsonify({
        'total': total, 'pending': pending, 'in_progress': in_progress, 'fixed': fixed, 'rejected': rejected,
        'avg_quality': round(avg_quality), 'avg_confidence': round(avg_confidence * 100), 'quality_grade': grade,
        'by_severity': by_severity, 'by_status': by_status,
        'monthly': monthly_list, 'affected_areas': area_list, 'hotspots': hotspot_data
    })

GRAPH_CACHE = {}

@app.route('/api/analytics-graph')
def analytics_graph():
    import hashlib
    graph_type = request.args.get('type', 'monthly')
    reported_only = request.args.get('reported', type=int, default=0)
    
    state_query = db.session.query(Detection.id, Detection.status, Detection.complaint_filed).all()
    current_state = hashlib.md5(str(state_query).encode()).hexdigest()
    cache_key = f"{graph_type}_{reported_only}_{current_state}"
    
    if cache_key in GRAPH_CACHE:
        return Response(GRAPH_CACHE[cache_key], mimetype='image/png')
        
    if len(GRAPH_CACHE) > 20:
        GRAPH_CACHE.clear()
        
    query = Detection.query
    if reported_only:
        query = query.filter(Detection.complaint_filed == True, Detection.status.in_(['in_progress', 'fixed', 'completed']))
    detections = query.all()
    
    if not HAS_MATPLOTLIB:
        return '', 204
    
    from matplotlib.figure import Figure
    fig = Figure(figsize=(8, 4))
    ax = fig.subplots()
    fig.patch.set_facecolor('#0a0a12')
    ax.set_facecolor('#0a0a12')
    
    if graph_type == 'monthly':
        monthly = {}
        for d in detections:
            if d.timestamp:
                key = d.timestamp.strftime('%Y-%m')
                monthly[key] = monthly.get(key, 0) + 1
        months = sorted(monthly.keys())
        counts = [monthly[m] for m in months]
        if months:
            x = range(len(months))
            ax.bar(x, counts, color='#00f0ff', alpha=0.8, width=0.6)
            ax.set_xticks(x)
            ax.set_xticklabels(months, rotation=45, ha='right')
        else:
            ax.text(0.5, 0.5, 'No Data', ha='center', va='center', color='#666', fontsize=16, transform=ax.transAxes)
        ax.set_title('Monthly Detections', color='white', fontsize=14)
        ax.tick_params(colors='white', labelsize=8)
        
    elif graph_type == 'severity':
        by_severity = {'Low': 0, 'Moderate': 0, 'High': 0, 'Severe': 0}
        for d in detections:
            sev = (d.severity or 'moderate').capitalize()
            if sev in by_severity: by_severity[sev] += 1
        values = list(by_severity.values())
        colors = ['#00ff88', '#ffc107', '#ff6b00', '#ff0044']
        if sum(values) > 0:
            wedges, texts, autotexts = ax.pie(
                values, labels=by_severity.keys(), colors=colors,
                autopct='%1.1f%%', textprops={'color': 'white', 'fontsize': 9},
                startangle=90
            )
            for at in autotexts:
                at.set_color('white')
        else:
            ax.text(0.5, 0.5, 'No Data', ha='center', va='center', color='#666', fontsize=16, transform=ax.transAxes)
        ax.set_title('Severity Distribution', color='white', fontsize=14)
        
    elif graph_type == 'status':
        by_status = {'Pending': 0, 'In Progress': 0, 'Fixed': 0, 'Rejected': 0}
        for d in detections:
            s = d.status or 'pending'
            if s == 'pending': by_status['Pending'] += 1
            elif s in ('in_progress', 'reported_to_corp'): by_status['In Progress'] += 1
            elif s == 'fixed': by_status['Fixed'] += 1
            elif s == 'rejected': by_status['Rejected'] += 1
        status_labels = list(by_status.keys())
        status_values = list(by_status.values())
        colors = ['#ff0044', '#ffc107', '#00ff88', '#ff4400']
        if any(status_values):
            x = range(len(status_labels))
            ax.bar(x, status_values, color=colors, alpha=0.8, width=0.5)
            ax.set_xticks(x)
            ax.set_xticklabels(status_labels, rotation=0)
        else:
            ax.text(0.5, 0.5, 'No Data', ha='center', va='center', color='#666', fontsize=16, transform=ax.transAxes)
        ax.set_title('Status Distribution', color='white', fontsize=14)
        ax.tick_params(colors='white', labelsize=9)
    
    for spine in ax.spines.values(): spine.set_color('#333')
    ax.yaxis.label.set_color('white')
    fig.tight_layout()
    
    img = io.BytesIO()
    fig.savefig(img, format='png', dpi=100, bbox_inches='tight', facecolor=fig.get_facecolor())
    
    img_data = img.getvalue()
    GRAPH_CACHE[cache_key] = img_data
    return Response(img_data, mimetype='image/png')

@app.route('/api/hotspots')
@login_required
def hotspots():
    if not current_user.is_admin and not current_user.is_corporation:
        return jsonify({'error': 'Unauthorized'}), 403
    update_hotspots()
    zones = HotspotZone.query.order_by(HotspotZone.pothole_count.desc()).all()
    return jsonify({'hotspots': [{
        'lat': z.center_lat, 'lng': z.center_lng,
        'pothole_count': z.pothole_count, 'severity': z.avg_severity,
        'radius_km': z.radius_km, 'last_updated': z.last_updated.strftime('%Y-%m-%d %H:%M') if z.last_updated else 'N/A'
    } for z in zones]})

@app.route('/delete-detection/<int:id>', methods=['POST'])
@login_required
def delete_detection(id):
    if not current_user.is_admin and not current_user.is_corporation:
        return jsonify({'error': 'Unauthorized'}), 403
    det = Detection.query.get(id)
    if det:
        if det.filename:
            res_path = os.path.join(app.config['RESULT_FOLDER'], det.filename)
            up_path = os.path.join(app.config['UPLOAD_FOLDER'], det.filename)
            try:
                if os.path.exists(res_path): os.remove(res_path)
                if os.path.exists(up_path): os.remove(up_path)
            except Exception as e:
                print(f"Error deleting file for {id}: {e}")
        db.session.delete(det)
        db.session.commit()
        return jsonify({'success': True})
    return jsonify({'error': 'Not found'}), 404

@app.route('/delete-all-detections', methods=['POST'])
@login_required
def delete_all_detections():
    if not current_user.is_admin and not current_user.is_corporation:
        return jsonify({'error': 'Unauthorized'}), 403
    
    detections = Detection.query.all()
    det_count = len(detections)
    for det in detections:
        if det.filename:
            res_path = os.path.join(app.config['RESULT_FOLDER'], det.filename)
            up_path = os.path.join(app.config['UPLOAD_FOLDER'], det.filename)
            try:
                if os.path.exists(res_path): os.remove(res_path)
                if os.path.exists(up_path): os.remove(up_path)
            except:
                pass
                
    Detection.query.delete()
    HotspotZone.query.delete()
    auth_count = AuthorityReport.query.count()
    AuthorityReport.query.delete()
    db.session.commit()
    return jsonify({'success': True, 'deleted': det_count, 'reports_deleted': auth_count})

@app.route('/report-detection-to-authority/<int:id>', methods=['POST'])
@login_required
def report_detection_to_authority(id):
    if not current_user.is_admin and not current_user.is_corporation:
        return jsonify({'error': 'Unauthorized'}), 403
    det = Detection.query.get(id)
    if not det:
        return jsonify({'error': 'Not found'}), 404
    
    try:
        det.complaint_filed = True
        det.status = 'reported_to_corp'
        
        report_id = f"PH-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{random.randint(100,999)}"
        
        report = AuthorityReport(
            report_id=report_id,
            authority_name=current_user.corporation_name if current_user.is_corporation else 'Admin',
            authority_email=current_user.corporation_email if current_user.is_corporation else 'admin@potholeai.com',
            detection_ids=json.dumps([det.id]),
            total_potholes=det.pothole_count,
            report_date=datetime.utcnow(),
            status='pending'
        )
        db.session.add(report)
        db.session.commit()
        
        return jsonify({'success': True, 'report_id': report_id})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/export-csv')
@login_required
def export_csv():
    if not current_user.is_admin and not current_user.is_corporation:
        return redirect(url_for('index'))
    
    detections = Detection.query.order_by(Detection.timestamp.desc()).all()
    csv_data = "ID,Date,Time,Latitude,Longitude,Address,Potholes,Confidence,Severity,Road Quality,Status,Night Detection,Reported\n"
    for d in detections:
        csv_data += f"{d.id},{d.timestamp.strftime('%Y-%m-%d') if d.timestamp else 'N/A'},{d.timestamp.strftime('%H:%M') if d.timestamp else 'N/A'},{d.latitude or ''},{d.longitude or ''},\"{d.address or ''}\",{d.pothole_count},{d.avg_confidence or 0},{d.severity or 'moderate'},{d.road_quality_score if d.road_quality_score is not None else 100},{d.status or 'pending'},{d.is_night_detection or False},{d.complaint_filed or False}\n"
    
    return Response(csv_data, mimetype='text/csv', headers={'Content-Disposition': 'attachment;filename=potholeai_export.csv'})

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        current_password = request.form.get('current_password')
        new_username = request.form.get('new_username')
        new_password = request.form.get('new_password')
        
        if not check_password_hash(current_user.password, current_password):
            return render_template('profile.html', error='Current password is incorrect')
        
        if new_username and new_username != current_user.username:
            existing = User.query.filter_by(username=new_username).first()
            if existing:
                return render_template('profile.html', error='Username already taken')
            current_user.username = new_username
        
        if new_password:
            if len(new_password) < 4:
                return render_template('profile.html', error='Password must be at least 4 characters')
            current_user.password = generate_password_hash(new_password)
        
        db.session.commit()
        return render_template('profile.html', success='Credentials updated successfully')
    
    return render_template('profile.html')

@app.route('/export-report')
@login_required
def export_report():
    if not current_user.is_admin and not current_user.is_corporation:
        return redirect(url_for('index'))
    
    detections = Detection.query.order_by(Detection.timestamp.desc()).all()
    total = len(detections)
    pending = sum(1 for d in detections if d.status == 'pending')
    fixed = sum(1 for d in detections if d.status == 'fixed')
    in_progress = sum(1 for d in detections if d.status in ('in_progress', 'reported_to_corp'))
    
    text = f"""
POTHOLEAI - ROAD CONDITION REPORT
{'='*50}
Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}
Total Detections: {total}
  - Pending: {pending}
  - In Progress: {in_progress}
  - Fixed: {fixed}
{'='*50}

DETECTION LIST:
"""
    for i, d in enumerate(detections[:50], 1):
        text += f"\n{i}. [{d.timestamp.strftime('%Y-%m-%d %H:%M') if d.timestamp else 'N/A'}] {d.pothole_count} potholes | Severity: {d.severity} | Quality: {d.road_quality_score}% | Status: {d.status}"
        if d.address: text += f" | Location: {d.address}"
    
    return Response(text, mimetype='text/plain', headers={'Content-Disposition': 'attachment;filename=potholeai_report.txt'})

@app.route('/export-pdf')
@login_required
def export_pdf():
    if not current_user.is_admin and not current_user.is_corporation:
        return redirect(url_for('index'))
    
    if not HAS_REPORTLAB:
        return jsonify({'error': 'ReportLab not installed'}), 500
    
    detections = Detection.query.order_by(Detection.timestamp.desc()).all()
    total = len(detections)
    pending = sum(1 for d in detections if d.status == 'pending')
    fixed = sum(1 for d in detections if d.status == 'fixed')
    in_progress = sum(1 for d in detections if d.status in ('in_progress', 'reported_to_corp'))
    avg_quality = round(sum(d.road_quality_score if d.road_quality_score is not None else 100 for d in detections) / total) if total else 100
    
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    styles = getSampleStyleSheet()
    elements = []
    
    title_style = ParagraphStyle('CustomTitle', parent=styles['Title'], fontSize=20, spaceAfter=20, textColor=colors.HexColor('#00f0ff'))
    elements.append(Paragraph('PotholeAI - Road Condition Report', title_style))
    elements.append(Paragraph(f'Generated: {datetime.utcnow().strftime("%Y-%m-%d %H:%M")}', styles['Normal']))
    elements.append(Spacer(1, 20))
    
    stats_data = [['Metric', 'Value'], ['Total Detections', str(total)], ['Pending', str(pending)], ['In Progress', str(in_progress)], ['Fixed', str(fixed)], ['Avg Road Quality', f'{avg_quality}%']]
    stat_table = Table(stats_data, colWidths=[200, 200])
    stat_table.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), colors.HexColor('#00f0ff')), ('TEXTCOLOR', (0,0), (-1,0), colors.white), ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'), ('FONTSIZE', (0,0), (-1,0), 12), ('BACKGROUND', (0,1), (-1,-1), colors.HexColor('#12121a')), ('TEXTCOLOR', (0,1), (-1,-1), colors.white), ('ALIGN', (0,0), (-1,-1), 'CENTER'), ('GRID', (0,0), (-1,-1), 1, colors.HexColor('#333'))]))
    elements.append(stat_table)
    elements.append(Spacer(1, 20))
    
    det_data = [['ID', 'Date', 'Potholes', 'Severity', 'Quality', 'Status']]
    for d in detections[:30]:
        det_data.append([str(d.id), d.timestamp.strftime('%Y-%m-%d') if d.timestamp else 'N/A', str(d.pothole_count), d.severity or 'moderate', f'{d.road_quality_score if d.road_quality_score is not None else 100}%', d.status or 'pending'])
    
    det_table = Table(det_data, colWidths=[50, 80, 70, 80, 70, 100])
    det_table.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), colors.HexColor('#bf00ff')), ('TEXTCOLOR', (0,0), (-1,-1), colors.white), ('FONTSIZE', (0,0), (-1,-1), 8), ('BACKGROUND', (0,1), (-1,-1), colors.HexColor('#12121a')), ('ALIGN', (0,0), (-1,-1), 'CENTER'), ('GRID', (0,0), (-1,-1), 1, colors.HexColor('#333'))]))
    elements.append(det_table)
    
    doc.build(elements)
    buf.seek(0)
    return send_file(buf, mimetype='application/pdf', as_attachment=True, download_name='potholeai_report.pdf')

@app.route('/detect', methods=['POST'])
def detect():
    d = get_detector()
    if d is None:
        return jsonify({'error': 'AI model not loaded. Upload best.pt to GitHub'}), 500
    lat = request.args.get('lat', type=float)
    lng = request.args.get('lng', type=float)

    if request.content_type and 'application/json' in request.content_type:
        data = request.get_json()
        image_data = data.get('image', '')
        location = data.get('location', {})
        lat = lat or location.get('latitude')
        lng = lng or location.get('longitude')

        if image_data.startswith('data:image'):
            header, encoded = image_data.split(',', 1)
            img_bytes = base64.b64decode(encoded)
            img_path = os.path.join(app.config['UPLOAD_FOLDER'], f"capture_{uuid.uuid4().hex}.jpg")
            with open(img_path, 'wb') as f:
                f.write(img_bytes)
        else:
            return jsonify({'error': 'Invalid image data'}), 400

        result_path, detections, is_night = d.detect_image(img_path)

        avg_conf = round(sum(d['confidence'] for d in detections) / len(detections), 3) if detections else 0
        severity = calculate_severity(len(detections), avg_conf)
        road_quality = calculate_road_quality(len(detections), severity, avg_conf)

        img_hash = compute_image_hash(img_path)
        if img_hash:
            existing = Detection.query.filter_by(image_hash=img_hash).first()
            if existing:
                return jsonify({'error': 'This pothole is already available in the system', 'duplicate': True, 'original_id': existing.id}), 409

        detection = Detection(
            filename=os.path.basename(result_path), file_type='image',
            latitude=lat, longitude=lng,
            pothole_count=len(detections), avg_confidence=avg_conf,
            severity=severity, road_quality_score=road_quality,
            is_night_detection=is_night, image_hash=img_hash,
        )
        db.session.add(detection)
        db.session.commit()
        update_hotspots()

        with open(result_path, 'rb') as f:
            result_b64 = base64.b64encode(f.read()).decode()

        return jsonify({
            'success': True, 'detection_id': detection.id,
            'result_image': f"data:image/jpeg;base64,{result_b64}",
            'detections': detections, 'pothole_count': len(detections),
            'avg_confidence': avg_conf, 'severity': severity,
            'road_quality': road_quality, 'is_night_mode': is_night,
            'type': 'image'
        })

    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    filename = secure_filename(file.filename)
    file_ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
    is_video = file_ext in {'mp4', 'avi', 'mov'}
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{uuid.uuid4().hex}.{file_ext}")
    file.save(file_path)

    if is_video:
        result_path, video_stats = d.detect_video(file_path)
        pothole_count = video_stats['total_detections']
        avg_conf = video_stats['avg_confidence'] / 100.0
        severity = calculate_severity(pothole_count, avg_conf)
        road_quality = calculate_road_quality(pothole_count, severity, avg_conf)
        result_url = f"/results/{os.path.basename(result_path)}"

        file_hash = compute_image_hash(file_path)
        if file_hash:
            existing = Detection.query.filter_by(image_hash=file_hash).first()
            if existing:
                return jsonify({'error': 'This pothole is already available in the system', 'duplicate': True, 'original_id': existing.id}), 409

        detection = Detection(
            filename=os.path.basename(result_path), file_type='video',
            latitude=lat, longitude=lng,
            pothole_count=pothole_count, avg_confidence=avg_conf,
            severity=severity, road_quality_score=road_quality,
            image_hash=file_hash,
        )
        db.session.add(detection)
        db.session.commit()
        update_hotspots()

        return jsonify({
            'success': True, 'detection_id': detection.id,
            'result_video': result_url, 'type': 'video',
            'detections': video_stats, 'pothole_count': pothole_count,
            'avg_confidence': avg_conf, 'severity': severity,
            'road_quality': road_quality
        })

    result_path, detections, is_night = d.detect_image(file_path)
    avg_conf = round(sum(d['confidence'] for d in detections) / len(detections), 3) if detections else 0
    severity = calculate_severity(len(detections), avg_conf)
    road_quality = calculate_road_quality(len(detections), severity, avg_conf)

    file_hash = compute_image_hash(file_path)
    if file_hash:
        existing = Detection.query.filter_by(image_hash=file_hash).first()
        if existing:
            return jsonify({'error': 'This pothole is already available in the system', 'duplicate': True, 'original_id': existing.id}), 409

    detection = Detection(
        filename=os.path.basename(result_path), file_type='image',
        latitude=lat, longitude=lng,
        pothole_count=len(detections), avg_confidence=avg_conf,
        severity=severity, road_quality_score=road_quality,
        image_hash=file_hash,
    )
    db.session.add(detection)
    db.session.commit()
    update_hotspots()

    result_url = f"/results/{os.path.basename(result_path)}"

    return jsonify({
        'success': True, 'detection_id': detection.id,
        'result_image': result_url, 'detections': detections,
        'pothole_count': len(detections), 'avg_confidence': avg_conf,
        'severity': severity, 'road_quality': road_quality,
        'type': 'image'
    })

@app.route('/api/user-reports', methods=['POST'])
def user_reports():
    d = get_detector()
    if d is None:
        return jsonify({'error': 'AI model not loaded. Upload best.pt to GitHub'}), 500
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    media = data.get('media', '')
    location = data.get('location', {})
    lat = location.get('latitude')
    lng = location.get('longitude')
    address = location.get('address', '')

    if media.startswith('data:image'):
        header, encoded = media.split(',', 1)
        img_bytes = base64.b64decode(encoded)
        img_path = os.path.join(app.config['UPLOAD_FOLDER'], f"report_{uuid.uuid4().hex}.jpg")
        with open(img_path, 'wb') as f:
            f.write(img_bytes)

        result_path, detections, _ = d.detect_image(img_path)
        avg_conf = round(sum(d['confidence'] for d in detections) / len(detections), 3) if detections else 0
        severity = calculate_severity(len(detections), avg_conf)
        road_quality = calculate_road_quality(len(detections), severity, avg_conf)

        img_hash = compute_image_hash(img_path)
        if img_hash:
            existing = Detection.query.filter_by(image_hash=img_hash).first()
            if existing:
                return jsonify({'error': 'This pothole is already available in the system', 'duplicate': True, 'original_id': existing.id}), 409

        detection = Detection(
            filename=os.path.basename(result_path), file_type='image',
            latitude=lat, longitude=lng, address=address,
            pothole_count=len(detections), avg_confidence=avg_conf,
            severity=severity, road_quality_score=road_quality,
            reported_by_user=data.get('user_name'),
            user_description=data.get('description'),
            complaint_filed=True, image_hash=img_hash,
        )
        db.session.add(detection)
        db.session.commit()
        update_hotspots()

        return jsonify({
            'success': True, 'detection_id': detection.id,
            'severity': severity, 'road_quality': road_quality,
            'pothole_count': len(detections), 'detections': detections
        })

    return jsonify({'error': 'No valid media found'}), 400

create_tables()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    debug = os.environ.get('FLASK_ENV', 'development') == 'development'
    
    if debug:
        import socket
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)
        print("\n" + "="*60)
        print("🚀 Starting PotholeAI...")
        print("="*60)
        print(f"\n💻 LAPTOP: http://localhost:{port}")
        print(f"📱 MOBILE: http://{local_ip}:{port}")
        print(f"\n🔐 LOGIN: http://localhost:{port}/login")
        print(f"   👑 Admin  -> admin / admin123")
        print(f"   🏛️  Corp   -> corporation / corp123")
        print("="*60 + "\n")
    
    app.run(debug=debug, host='0.0.0.0', port=port)
