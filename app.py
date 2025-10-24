# --- START OF FINAL, COMPLETE app.py FILE ---

# NOTE: This application requires: pip install Pillow Flask-SQLAlchemy Flask-Login Werkzeug Authlib google-analytics-data bleach cssutils sendgrid pyppeteer
import requests
from flask import Flask, render_template, request, jsonify, Response, send_file, redirect, url_for, flash, send_from_directory, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadTimeSignature
from authlib.integrations.flask_client import OAuth
from bs4 import BeautifulSoup
from bs4.element import Tag
import re
import asyncio
from pyppeteer import launch
from urllib.parse import urljoin, unquote, urlparse, parse_qs
import traceback
import time
import webcolors
from PIL import Image, UnidentifiedImageError
import io
import os
import sys # Added for asyncio workaround
from typing import Optional, Set, List, Dict, Tuple, Any, Union
from datetime import datetime, timedelta
from functools import wraps
import click
import shutil
import tempfile
from sqlalchemy import func, and_, or_
from werkzeug.exceptions import RequestEntityTooLarge
import logging
import bleach
from bleach.css_sanitizer import CSSSanitizer
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    DateRange,
    Dimension,
    Metric,
    RunReportRequest,
    RunRealtimeReportRequest,
)
from google.api_core import exceptions as google_exceptions
import json
from dotenv import load_dotenv
from flask_wtf.csrf import CSRFProtect
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, From
import subprocess # NEW IMPORT for running external tools

load_dotenv()

app = Flask(__name__, instance_relative_config=True)
csrf = CSRFProtect(app)

logging.basicConfig(level=logging.INFO)

app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY')
if not app.config['SECRET_KEY']:
    raise ValueError("No SECRET_KEY set for Flask application")

os.makedirs(app.instance_path, exist_ok=True)
DATABASE_URL = os.environ.get('DATABASE_URL')
app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL or f"sqlite:///{os.path.join(app.instance_path, 'users.db')}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

app.config['UPLOAD_FOLDER'] = os.path.join(app.instance_path, 'uploads')
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024

@app.errorhandler(413)
@app.errorhandler(RequestEntityTooLarge)
def handle_request_entity_too_large(e):
    # Check if the request expects a JSON response (typical for fetch/AJAX)
    # The compressor and Quill uploader are AJAX, so we check their paths specifically.
    if request.path in [url_for('compress_image'), url_for('upload_image_for_editor')]:
        limit_mb = app.config.get('MAX_CONTENT_LENGTH', MAX_FILE_SIZE) // (1024 * 1024)
        return jsonify({'error': f'File size exceeds the server limit of {limit_mb}MB.'}), 413

    # Fallback for traditional form submissions (like the post editor)
    flash('The submitted data or file is too large. Please reduce the size of images or content.', 'error')
    return redirect(request.referrer or url_for('home'))

app.config['GOOGLE_CLIENT_ID'] = os.environ.get('GOOGLE_CLIENT_ID')
app.config['GOOGLE_CLIENT_SECRET'] = os.environ.get('GOOGLE_CLIENT_SECRET')
GA_PROPERTY_ID = os.environ.get('GA_PROPERTY_ID')

oauth = OAuth(app)
oauth.register(
    name='google',
    client_id=app.config["GOOGLE_CLIENT_ID"],
    client_secret=app.config["GOOGLE_CLIENT_SECRET"],
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile'}
)

app.config['SENDGRID_API_KEY'] = os.environ.get('SENDGRID_API_KEY')
app.config['MAIL_DEFAULT_SENDER'] = ('Web Asset Suite', 'noreply@webassetsuite.com')
s = URLSafeTimedSerializer(app.config['SECRET_KEY'])

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = None

MAX_FILE_SIZE: int = 10 * 1024 * 1024
MAX_IMAGE_DIMENSIONS: Tuple[int, int] = (8000, 8000)
MAX_ANON_USES = 3

post_tags = db.Table('post_tags',
    db.Column('post_id', db.Integer, db.ForeignKey('post.id'), primary_key=True),
    db.Column('tag_id', db.Integer, db.ForeignKey('tag.id'), primary_key=True)
)

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(80), nullable=True)
    last_name = db.Column(db.String(80), nullable=True)
    username = db.Column(db.String(80), unique=True, nullable=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_seen = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(20), nullable=False, default='pending')
    role = db.Column(db.String(20), nullable=False, default='user')
    location = db.Column(db.String(100), nullable=True)
    posts = db.relationship('Post', backref='author', lazy='dynamic')
    confirmed = db.Column(db.Boolean, nullable=False, default=False)
    confirmed_on = db.Column(db.DateTime, nullable=True)

    @property
    def is_admin(self):
        return self.role == 'admin'

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return self.password_hash and check_password_hash(self.password_hash, password)

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(200), unique=True, nullable=False)
    content = db.Column(db.Text, nullable=False)
    pub_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=True)
    featured_image = db.Column(db.String(255), nullable=True)
    status = db.Column(db.String(20), nullable=False, default='draft')
    views = db.Column(db.Integer, default=0)
    meta_title = db.Column(db.String(200), nullable=True)
    meta_description = db.Column(db.String(300), nullable=True)
    tags = db.relationship('Tag', secondary=post_tags, lazy='subquery',
                           backref=db.backref('posts', lazy=True))

class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    slug = db.Column(db.String(100), unique=True, nullable=False)
    posts = db.relationship('Post', backref='category', lazy='dynamic')

class Tag(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)

class ToolUsage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    tool_name = db.Column(db.String(50), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    metadata_json = db.Column(db.Text, nullable=True)
    user = db.relationship('User', backref=db.backref('tool_usages', lazy='dynamic', cascade="all, delete-orphan"))

class UserActivityLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    action = db.Column(db.String(100), nullable=False)
    details = db.Column(db.String(255), nullable=True)
    user = db.relationship('User', backref=db.backref('activity_logs', lazy='dynamic', cascade="all, delete-orphan"))

class Subscriber(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    subscribed_on = db.Column(db.DateTime, default=datetime.utcnow)

def send_email(to, subject, template):
    api_key = app.config.get('SENDGRID_API_KEY')
    sender_tuple = app.config.get('MAIL_DEFAULT_SENDER')

    if not api_key:
        app.logger.error("CRITICAL: SENDGRID_API_KEY not set in config. Email sending is disabled.")
        return

    from_object = From(email=sender_tuple[1], name=sender_tuple[0])
    app.logger.info(f"Email configuration - From: {from_object.get()}, To: {to}, Subject: {subject}")

    message = Mail(
        from_email=from_object,
        to_emails=to,
        subject=subject,
        html_content=template
    )
    
    try:
        sendgrid_client = SendGridAPIClient(api_key)
        response = sendgrid_client.send(message)
        
        if 200 <= response.status_code < 300:
            app.logger.info(f"Email successfully sent to {to}. Status Code: {response.status_code}")
        else:
            app.logger.error(f"Failed to send email to {to}. SendGrid returned status code: {response.status_code}")
            app.logger.error(f"SendGrid response body: {response.body.decode('utf-8') if response.body else 'No body'}")
            
    except Exception as e:
        error_body = e.body if hasattr(e, 'body') else str(e)
        app.logger.error(f"An exception occurred while trying to send email via SendGrid.")
        app.logger.error(f"DETAILED SENDGRID ERROR: {error_body}")

def sanitize_html(html_content):
    if not html_content:
        return ""
    allowed_tags = [
        'p', 'br', 'strong', 'em', 'u', 's', 'a', 'ul', 'ol', 'li', 'blockquote',
        'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'pre', 'code', 'img', 'span', 'div'
    ]
    allowed_protocols = list(bleach.ALLOWED_PROTOCOLS) + ['data']
    allowed_attributes = {
        '*': ['class', 'style'], 'a': ['href', 'title', 'target'],
        'img': ['src', 'alt', 'width', 'height'],
    }
    allowed_css_properties = [
        'color', 'background-color', 'font-family', 'font-size', 'font-weight', 'text-align',
        'float', 'margin', 'margin-left', 'margin-right', 'padding', 'padding-left', 'padding-right', 
        'width', 'height', 'border', 'text-decoration', 'list-style-type'
    ]
    css_sanitizer = CSSSanitizer(allowed_css_properties=allowed_css_properties)
    cleaned_html = bleach.clean(
        html_content, tags=allowed_tags, attributes=allowed_attributes,
        protocols=allowed_protocols, css_sanitizer=css_sanitizer, strip=True
    )
    return cleaned_html

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def moderator_or_admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or (current_user.role not in ['admin', 'moderator']):
            flash("You do not have permission to access this page.", "error")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash("You do not have permission to access this page.", "error")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def log_user_activity(action, details=None):
    if current_user.is_authenticated:
        log_entry = UserActivityLog(user_id=current_user.id, action=action, details=details)
        db.session.add(log_entry)
        db.session.commit()

def check_and_increment_usage():
    if current_user.is_authenticated:
        return True
    
    usage_count = session.get('usage_count', 0)
    
    if usage_count >= MAX_ANON_USES:
        return False
        
    session['usage_count'] = usage_count + 1
    session.modified = True 
    return True

@app.cli.command("make-admin")
@click.argument("email")
def make_admin(email):
    user = User.query.filter_by(email=email).first()
    if user:
        user.role = 'admin'
        db.session.commit()
        print(f"User {email} is now an admin.")
    else:
        print(f"User {email} not found.")

def create_slug(title, model, existing_id=None):
    if not title:
        title = "untitled"
    slug = re.sub(r'[^\w\s-]', '', title).strip().lower()
    slug = re.sub(r'[\s_-]+', '-', slug)
    original_slug = slug
    counter = 1
    while True:
        query = model.query.filter_by(slug=slug)
        if existing_id:
            query = query.filter(model.id != existing_id)
        if not query.first():
            break
        slug = f"{original_slug}-{counter}"
        counter += 1
    return slug

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.cli.command("init-db")
def init_db_command():
    db.create_all()
    print("Initialized the database.")

@app.context_processor
def inject_ga_id():
    return dict(GA_MEASUREMENT_ID=os.environ.get('GA_MEASUREMENT_ID'))

@app.before_request
def before_request_callback():
    scheduled_posts = Post.query.filter(Post.status == 'scheduled', Post.pub_date <= datetime.utcnow()).all()
    for post in scheduled_posts:
        post.status = 'published'
    if scheduled_posts:
        db.session.commit()

    if current_user.is_authenticated:
        current_user.last_seen = datetime.utcnow()
        
        if request.endpoint and request.endpoint != 'static':
             log_user_activity('page_visit', details=request.path)
        
        allowed_endpoints = ['logout', 'login', 'static'] 
        if current_user.status != 'active' and request.endpoint not in allowed_endpoints:
            status_message = current_user.status
            logout_user()
            if status_message == 'suspended':
                flash('Your account has been suspended. Please contact support.', 'error')
            elif status_message == 'pending':
                flash('Your account is not yet active. Please check your email for a confirmation link.', 'error')
            else:
                flash('Your account is not currently active.', 'error')
            return redirect(url_for('login'))
        
        db.session.commit()

def get_google_analytics_data(property_id, reports: List[str] = ['overview']):
    if not property_id or not os.environ.get('GOOGLE_APPLICATION_CREDENTIALS'):
        print("GA_PROPERTY_ID or GOOGLE_APPLICATION_CREDENTIALS not set. Skipping GA fetch.")
        return None
        
    try:
        client = BetaAnalyticsDataClient()
        thirty_days_ago = (datetime.utcnow() - timedelta(days=29)).strftime('%Y-%m-%d')
        today = datetime.utcnow().strftime('%Y-%m-%d')
        date_range = DateRange(start_date=thirty_days_ago, end_date=today)
        
        ga_data = {}

        if 'overview' in reports:
            request_visitors = RunReportRequest(property=f"properties/{property_id}", metrics=[Metric(name="totalUsers")], date_ranges=[date_range])
            response_visitors = client.run_report(request_visitors)
            ga_data["total_visitors_30_days"] = int(response_visitors.rows[0].metric_values[0].value) if response_visitors.rows else 0
            request_country = RunReportRequest(property=f"properties/{property_id}", dimensions=[Dimension(name="country")], metrics=[Metric(name="totalUsers")], date_ranges=[date_range], limit=100)
            response_country = client.run_report(request_country)
            ga_data["user_map_data"] = {row.dimension_values[0].value: int(row.metric_values[0].value) for row in response_country.rows}

        if 'acquisition' in reports:
            request_channels = RunReportRequest(property=f"properties/{property_id}", dimensions=[Dimension(name="sessionDefaultChannelGroup")], metrics=[Metric(name="sessions")], date_ranges=[date_range])
            response_channels = client.run_report(request_channels)
            ga_data["sessions_by_channel"] = {row.dimension_values[0].value: int(row.metric_values[0].value) for row in response_channels.rows}
            request_referrals = RunReportRequest(property=f"properties/{property_id}", dimensions=[Dimension(name="sessionSource")], metrics=[Metric(name="sessions")], date_ranges=[date_range], limit=10)
            response_referrals = client.run_report(request_referrals)
            ga_data["top_referrals"] = {row.dimension_values[0].value: int(row.metric_values[0].value) for row in response_referrals.rows if row.dimension_values[0].value != '(direct)'}
        
        if 'engagement' in reports:
            request_duration = RunReportRequest(property=f"properties/{property_id}", metrics=[Metric(name="averageSessionDuration")], date_ranges=[date_range])
            response_duration = client.run_report(request_duration)
            duration_seconds = float(response_duration.rows[0].metric_values[0].value) if response_duration.rows else 0
            ga_data["avg_session_duration"] = f"{int(duration_seconds // 60)}m {int(duration_seconds % 60)}s"
            
        if 'realtime' in reports:
            request_total = RunRealtimeReportRequest(property=f"properties/{property_id}", metrics=[Metric(name="activeUsers")])
            response_total = client.run_realtime_report(request_total)
            ga_data["realtime_total"] = int(response_total.rows[0].metric_values[0].value) if response_total.rows else 0
            request_details = RunRealtimeReportRequest(
                property=f"properties/{property_id}",
                dimensions=[Dimension(name="country"), Dimension(name="city"), Dimension(name="deviceCategory"), Dimension(name="unifiedScreenName")],
                metrics=[Metric(name="activeUsers")],
                limit=100
            )
            response_details = client.run_realtime_report(request_details)
            realtime_page_views = []
            for row in response_details.rows:
                realtime_page_views.append({
                    "country": row.dimension_values[0].value, "city": row.dimension_values[1].value,
                    "device": row.dimension_values[2].value, "page": row.dimension_values[3].value
                })
            ga_data["realtime_user_list"] = realtime_page_views
        
        return ga_data
        
    except google_exceptions.PermissionDenied:
        print("Google Analytics API permission denied.")
        return None
    except Exception as e:
        print(f"An error occurred while fetching Google Analytics data: {e}")
        traceback.print_exc()
        return None

GOOGLE_FONTS_API_CACHE: Optional[Dict[str, str]] = None
MYFONTS_KNOWN_LIST: Set[str] = {'circular std', 'gt walsheim pro', 'avenir next', 'futura pt', 'neue haas unica', 'aktiv grotesk', 'brandon grotesque', 'gilroy', 'gotham', 'helvetica now', 'din next'}
ICON_FONT_TERMS: Set[str] = {'icon', 'awesome', 'glyph', 'yootheme', 'eicons'}
SYSTEM_FONTS: Set[str] = {'arial', 'helvetica neue', 'helvetica', 'times new roman', 'georgia', 'verdana', 'tahoma', '-apple-system', 'segoe ui'}
SYSTEM_FONTS_CANONICAL = {re.sub(r'[\s_-]', '', s.lower()) for s in SYSTEM_FONTS}

def load_google_fonts_from_api() -> Dict[str, str]:
    global GOOGLE_FONTS_API_CACHE
    if GOOGLE_FONTS_API_CACHE is not None: return GOOGLE_FONTS_API_CACHE
    print("Loading Google Fonts from API...")
    api_key = os.getenv('GOOGLE_FONTS_API_KEY')
    if not api_key:
        print("Warning: GOOGLE_FONTS_API_KEY not set.")
        GOOGLE_FONTS_API_CACHE = {}
        return {}
    api_url = f"https://www.googleapis.com/webfonts/v1/webfonts?key={api_key}&sort=popularity"
    try:
        response = requests.get(api_url, timeout=10)
        response.raise_for_status()
        data = response.json()
        font_map = {item['family'].lower(): item['family'] for item in data.get('items', [])}
        print(f"Loaded {len(font_map)} fonts from Google API.")
        GOOGLE_FONTS_API_CACHE = font_map
        return font_map
    except requests.exceptions.RequestException as e:
        print(f"Error fetching Google Fonts: {e}")
        GOOGLE_FONTS_API_CACHE = {}
        return {}

def get_largest_from_srcset(srcset: Optional[str]) -> Optional[str]:
    if not srcset: return None
    sources: List[Tuple[int, str]] = []
    for s in srcset.split(','):
        parts = s.strip().split()
        if len(parts) >= 1:
            url = parts[0]
            width = 1
            if len(parts) == 2 and 'w' in parts[1]:
                width = int(re.sub(r'\D', '', parts[1]))
            sources.append((width, url))
    return max(sources, key=lambda x: x[0])[1] if sources else None

def extract_all_images_from_html(soup: BeautifulSoup, base_url: str) -> Set[str]:
    image_urls: Set[str] = set()
    for img in soup.find_all('img'):
        src_to_use: Optional[str] = None
        if isinstance(parent := img.find_parent('picture'), Tag):
            for source in parent.find_all('source'):
                if isinstance(source, Tag) and (srcset_attr := source.get('srcset')) and isinstance(srcset_attr, str):
                    if src_to_use := get_largest_from_srcset(srcset_attr): break
        if not src_to_use:
            srcset_val = img.get('data-srcset') or img.get('srcset')
            src_val = img.get('data-src') or img.get('src')
            src_to_use = get_largest_from_srcset(srcset_val) if isinstance(srcset_val, str) else src_val
        if isinstance(src_to_use, str) and not src_to_use.startswith(('data:image', 'about:blank')):
            if len(full_url := urljoin(base_url, src_to_use)) < 2048: image_urls.add(full_url)
    return image_urls

def extract_css_background_images(soup: BeautifulSoup, base_url: str) -> Set[str]:
    image_urls: Set[str] = set()
    for element in soup.select('[style*="background-image"]'):
        if isinstance(style := element.get('style'), str) and (match := re.search(r'url\((.*?)\)', style)):
            if (url := match.group(1).strip("'\"")) and not url.startswith('data:image'):
                if len(full_url := urljoin(base_url, url)) < 2048:
                    image_urls.add(full_url)
    for link in soup.find_all('link', rel='stylesheet', href=True):
        if isinstance(href := link.get('href'), str):
            css_url = urljoin(base_url, href)
            try:
                css_response = requests.get(css_url, timeout=10)
                css_response.raise_for_status()
                urls_in_css = re.findall(r'url\((.*?)\)', css_response.text)
                for url in urls_in_css:
                    clean_url = url.strip("'\"")
                    if not clean_url.startswith(('data:image', '#')):
                        full_url = urljoin(css_url, clean_url)
                        if len(full_url) < 2048:
                            image_urls.add(full_url)
            except requests.RequestException as e:
                print(f"Could not fetch or parse CSS file: {css_url}. Reason: {e}")
                continue
    return image_urls

def extract_fonts_from_google_links(soup: BeautifulSoup) -> List[str]:
    found_fonts: Set[str] = set()
    for link in soup.find_all('link', href=True):
        if isinstance(link, Tag) and isinstance(href := link.get('href'), str) and 'fonts.googleapis.com/css' in href:
            if 'family' in (query_params := parse_qs(urlparse(href).query)):
                for family_str in query_params['family']:
                    for font_name in family_str.split('|'):
                        found_fonts.add(font_name.split(':')[0].replace('+', ' ').strip())
    return list(found_fonts)

def detect_adobe_fonts_usage(soup: BeautifulSoup) -> bool:
    for el_type in ['link', 'script']:
        for el in soup.find_all(el_type, href=True):
            if isinstance(href := el.get('href'), str) and 'use.typekit.net' in href:
                print("Adobe Fonts loader detected."); return True
    print("Adobe Fonts loader not found."); return False

def process_fonts(computed_fonts: List[str], google_link_fonts: List[str], is_adobe_site: bool) -> List[Dict[str, str]]:
    raw_font_names: Set[str] = set(google_link_fonts)
    generic_fallbacks: Set[str] = {'sans-serif', 'serif', 'monospace', 'cursive', 'fantasy', 'system-ui', 'ui-sans-serif', 'ui-serif', 'apple-system', 'blinkmacsystemfont'}
    for font_stack in computed_fonts:
        for font in [f.strip("'\" ") for f in font_stack.split(',')]:
            if font and font.lower() not in generic_fallbacks and not any(term in font.lower() for term in ['emoji', 'symbol']):
                raw_font_names.add(font)
    garbage_pattern = re.compile(r'^(wf_|webfont-|var--|mktype-)|([a-f0-9]{8,})')
    human_readable_names = {name for name in raw_font_names if not garbage_pattern.search(name.lower())}
    font_map: Dict[str, str] = {}
    suffix_pattern = re.compile(r'[_\-\s]?(regular|italic|bold|medium|light|black|heavy|thin|condensed|expanded|oblique|book|roman|pro|std|w[0-9]{1,2}|[1-9]00|demi|semi|extra|cf)\b', re.IGNORECASE)
    prefix_pattern = re.compile(r'^(orig|original)[_\-\s]', re.IGNORECASE)
    for name in human_readable_names:
        base_name_for_key = prefix_pattern.sub('', name)
        temp_name = ""
        while temp_name != base_name_for_key:
            temp_name = base_name_for_key
            base_name_for_key = suffix_pattern.sub('', temp_name).strip()
        key = re.sub(r'[\s_-]', '', base_name_for_key.lower())
        if not key: continue
        if key not in font_map or len(name) < len(font_map[key]):
            font_map[key] = name
    google_fonts_map = load_google_fonts_from_api()
    final_results = []
    for classification_key, display_name in font_map.items():
        font_type = None
        if classification_key in SYSTEM_FONTS_CANONICAL:
            font_type = 'system'
        else:
            if any(term in classification_key for term in ICON_FONT_TERMS): font_type = 'icon'
            elif classification_key in google_fonts_map: font_type = 'google'
            elif classification_key in MYFONTS_KNOWN_LIST: font_type = 'myfonts_direct'
            elif is_adobe_site: font_type = 'adobe'
            else: font_type = 'myfonts_search'
        if font_type != 'icon':
            search_base_1 = suffix_pattern.sub('', display_name).strip()
            search_base_2 = prefix_pattern.sub('', search_base_1).strip()
            human_search_name = re.sub(r'[_\-]+', ' ', search_base_2).strip()
            result = {'displayName': display_name, 'searchName': human_search_name, 'type': font_type}
            if font_type == 'google':
                result['urlName'] = google_fonts_map.get(classification_key, display_name)
            final_results.append(result)
    return final_results

def get_clustered_color_palette(color_data: Dict[str, float], threshold: float = 45.0) -> Dict[str, List[str]]:
    hex_scores: Dict[str, float] = {}
    for color_str, score in color_data.items():
        try:
            if 'rgba' in color_str and (rgba := re.findall(r'[\d.]+', color_str)) and len(rgba) == 4 and float(rgba[3]) < 0.5: continue
            if (rgb_values := re.findall(r'\d+', color_str)) and len(rgb_values) >= 3:
                rgb: Tuple[int, int, int] = (int(rgb_values[0]), int(rgb_values[1]), int(rgb_values[2]))
                hex_color = webcolors.rgb_to_hex(rgb).upper()
                hex_scores[hex_color] = hex_scores.get(hex_color, 0) + score
        except (ValueError, IndexError): continue
    if not hex_scores: return {}
    sorted_colors = sorted(hex_scores.items(), key=lambda item: item[1], reverse=True)
    merged_colors: List[Dict[str, Any]] = []
    for hex_color, score in sorted_colors:
        rgb_color = tuple(int(hex_color.lstrip('#')[i:i+2], 16) for i in (0, 2, 4))
        found_cluster = False
        for cluster in merged_colors:
            cluster_rgb = tuple(int(cluster['hex'].lstrip('#')[i:i+2], 16) for i in (0, 2, 4))
            if sum((c1 - c2) ** 2 for c1, c2 in zip(rgb_color, cluster_rgb)) ** 0.5 < threshold:
                cluster['score'] += score; found_cluster = True; break
        if not found_cluster: merged_colors.append({'hex': hex_color, 'score': score})
    final_sorted = sorted(merged_colors, key=lambda item: item['score'], reverse=True)
    color_groups: Dict[str, List[str]] = {}
    if primary := [c['hex'] for c in final_sorted[:8]]: color_groups["Primary Palette"] = primary
    if secondary := [c['hex'] for c in final_sorted[8:24]]: color_groups["Secondary Colors"] = secondary
    return color_groups

async def extract_assets_from_page_async(url: str, options: Dict[str, Any]) -> Tuple[Set[str], List[Dict[str, str]], Dict[str, float]]:
    print(f"Analyzing page using Enhanced Hybrid Method: {url}")
    browser = None
    try:
        browser = await launch(
            headless=True,
            args=[
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage'
            ]
        )
        page = await browser.newPage()
        await page.goto(url, {'waitUntil': 'networkidle2', 'timeout': 30000})

        if options.get('extract_images'):
            print("Scrolling to trigger lazy-loading...")
            await page.evaluate('''
                async () => {
                    await new Promise((resolve) => {
                        let totalHeight = 0;
                        const distance = 100;
                        const timer = setInterval(() => {
                            const scrollHeight = document.body.scrollHeight;
                            window.scrollBy(0, distance);
                            totalHeight += distance;
                            if (totalHeight >= scrollHeight) {
                                clearInterval(timer);
                                resolve();
                            }
                        }, 100);
                    });
                }
            ''')
            await asyncio.sleep(2)

        final_html = await page.content()
        soup = BeautifulSoup(final_html, 'html.parser')

        images, fonts, colors = set(), [], {}

        if options.get('extract_images'):
            images = extract_all_images_from_html(soup, url).union(extract_css_background_images(soup, url))

        if options.get('extract_fonts') or options.get('extract_colors'):
            assets = await page.evaluate('''() => {
                const elements = document.querySelectorAll('*:not(script):not(style):not(link):not(meta)');
                const fontFamilies = new Set();
                const colorsByArea = {};
                elements.forEach(el => {
                    const style = window.getComputedStyle(el);
                    const rect = el.getBoundingClientRect();
                    const area = rect.width * rect.height;
                    if (area < 1) return;
                    if (style.fontFamily) fontFamilies.add(style.fontFamily);
                    ['color', 'backgroundColor'].forEach(prop => {
                        const c = style[prop];
                        if (c && c !== 'rgba(0, 0, 0, 0)') {
                            colorsByArea[c] = (colorsByArea[c] || 0) + area;
                        }
                    });
                });
                return { fonts: Array.from(fontFamilies), colors: colorsByArea };
            }''')

            if options.get('extract_colors'):
                colors = assets.get('colors', {})

            if options.get('extract_fonts'):
                is_adobe_site = 'use.typekit.net' in final_html
                google_link_fonts = extract_fonts_from_google_links(soup)
                computed_fonts = assets.get('fonts', [])
                fonts = process_fonts(computed_fonts, google_link_fonts, is_adobe_site)
        
        return images, fonts, colors

    finally:
        if browser:
            await browser.close()

def extract_assets_from_page(url: str, options: Dict[str, Any]) -> Tuple[Set[str], List[Dict[str, str]], Dict[str, float]]:
    if sys.version_info >= (3, 8) and os.name == 'posix':
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            asyncio.set_event_loop(asyncio.new_event_loop())
    return asyncio.run(extract_assets_from_page_async(url, options))
    
FlaskResponse = Union[Response, Tuple[Union[str, Response], int]]

def track_usage(tool_name: str, metadata: Optional[Dict] = None):
    if current_user.is_authenticated:
        data_to_store = json.dumps(metadata) if metadata else None
        usage = ToolUsage(
            user_id=current_user.id,
            tool_name=tool_name,
            metadata_json=data_to_store
        )
        db.session.add(usage)
        db.session.commit()
        log_user_activity('tool_usage', details=tool_name)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        
        if user and user.check_password(password):
            if not user.confirmed:
                flash('Please confirm your account first. A confirmation link was sent to your email.', 'error')
                return render_template('login.html', show_resend_link=True, email=email)
            if user.status == 'suspended':
                flash('Your account has been suspended. Please contact support.', 'error')
                return redirect(url_for('login'))
            if user.status == 'pending':
                flash('Your account is pending approval by an administrator.', 'error')
                return redirect(url_for('login'))
            login_user(user, remember=True)
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('home'))
        else:
            flash('Invalid email or password. Please try again.', 'error')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    if request.method == 'POST':
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        if password != confirm_password:
            flash('Passwords do not match. Please try again.', 'error')
            return redirect(url_for('register'))
        if User.query.filter_by(email=email).first():
            flash('Email address already exists.', 'error')
            return redirect(url_for('register'))
        new_user = User(
            email=email, 
            first_name=first_name, 
            last_name=last_name,
            confirmed=False
        )
        new_user.set_password(password)
        try:
            db.session.add(new_user)
            db.session.commit()
            token = s.dumps(email, salt='email-confirm-salt')
            confirm_url = url_for('confirm_email', token=token, _external=True)
            html = render_template('email/confirm_account.html', confirm_url=confirm_url)
            send_email(email, "Please confirm your email", html)
            flash('A confirmation email has been sent to your email address. Please check your inbox to activate your account.', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"An error occurred during user registration for email {email}: {e}")
            app.logger.error(traceback.format_exc())
            flash('Could not create account due to a server issue. Please try again later.', 'error')
            return redirect(url_for('register'))
    return render_template('register.html')

@app.route('/confirm/<token>')
def confirm_email(token):
    try:
        email = s.loads(token, salt='email-confirm-salt', max_age=3600)
    except (SignatureExpired, BadTimeSignature):
        flash('The confirmation link is invalid or has expired.', 'error')
        return redirect(url_for('login'))
    user = User.query.filter_by(email=email).first_or_404()
    if user.confirmed:
        flash('Account already confirmed. Please login.', 'success')
    else:
        user.confirmed = True
        user.confirmed_on = datetime.utcnow()
        user.status = 'active'
        db.session.commit()
        login_user(user)
        flash('You have confirmed your account. Thanks!', 'success')
    return redirect(url_for('home'))

@app.route('/resend-confirmation', methods=['POST'])
def resend_confirmation():
    email = request.form.get('email')
    user = User.query.filter_by(email=email).first()
    if user and not user.confirmed:
        token = s.dumps(email, salt='email-confirm-salt')
        confirm_url = url_for('confirm_email', token=token, _external=True)
        html = render_template('email/confirm_account.html', confirm_url=confirm_url)
        send_email(email, "Please confirm your email", html)
        flash('A new confirmation email has been sent.', 'success')
    elif user and user.confirmed:
        flash('Your account has already been confirmed.', 'success')
    else:
        flash('If that email address is in our database, we have sent a new confirmation link.', 'success')
    return redirect(url_for('login'))

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))

def google_authorize():
    redirect_uri = url_for('google_auth_callback', _external=True)
    return oauth.google.authorize_redirect(redirect_uri)    

@app.route('/login/google')
def login_with_google():
    session['google_oauth_intent'] = 'login'
    return google_authorize()

@app.route('/register/google')
def register_with_google():
    session['google_oauth_intent'] = 'register'
    return google_authorize()

# --- THIS IS THE FINAL, CORRECTED FUNCTION ---
@app.route('/login/google/callback')
def google_auth_callback():
    try:
        token = oauth.google.authorize_access_token()
        user_info = token.get('userinfo')
        if not user_info:
            flash('Could not retrieve user information from Google.', 'error')
            return redirect(url_for('login'))
    except Exception as e:
        flash('An error occurred during Google authentication. Please try again.', 'error')
        app.logger.error(f"OAuth Error: {e}")
        return redirect(url_for('login'))
    
    # Get the user's original intent from the session
    intent = session.pop('google_oauth_intent', 'login') # Default to 'login' if not found
    
    user_email = user_info['email']
    user = User.query.filter_by(email=user_email).first()

    if intent == 'login':
        # --- USER STARTED FROM THE LOGIN PAGE ---
        if user:
            # User exists, this is correct. Log them in.
            if not user.confirmed:
                flash('Your account is not confirmed. Please check your email for a confirmation link.', 'error')
                return redirect(url_for('login'))
            if user.status != 'active':
                flash('Your account is not active. Please contact support.', 'error')
                return redirect(url_for('login'))
            
            login_user(user, remember=True)
            return redirect(url_for('home'))
        else:
            # User does NOT exist. This is an error. Send them to register.
            flash("You don't have an account with that email. Please create one.", 'error')
            return redirect(url_for('register'))

    elif intent == 'register':
        # --- USER STARTED FROM THE REGISTER PAGE ---
        if user:
            # User already exists. This is an error. Send them to log in.
            flash('An account with this email already exists. Please log in.', 'error')
            return redirect(url_for('login'))
        else:
            # User does NOT exist. This is correct. Create account and send email.
            new_user = User(
                email=user_email,
                first_name=user_info.get('given_name'),
                last_name=user_info.get('family_name'),
                confirmed=False,
                status='pending'
            )
            try:
                db.session.add(new_user)
                db.session.commit()
                
                token = s.dumps(user_email, salt='email-confirm-salt')
                confirm_url = url_for('confirm_email', token=token, _external=True)
                html = render_template('email/confirm_account.html', confirm_url=confirm_url)
                send_email(user_email, "Please confirm your email", html)

                return redirect(url_for('check_email_page'))
            except Exception as e:
                db.session.rollback()
                app.logger.error(f"An error occurred during Google registration: {e}")
                flash('Could not create account due to a server issue. Please try again.', 'error')
                return redirect(url_for('register'))
    
    # Fallback in case something goes wrong
    return redirect(url_for('login'))

@app.route('/check-email')
def check_email_page():
    return render_template('check_email.html')

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        if not app.config.get('SENDGRID_API_KEY'):
            flash('The email server is not configured. Please contact an administrator.', 'error')
            return redirect(url_for('forgot_password'))
        user = User.query.filter_by(email=email).first()
        if user:
            token = s.dumps(email, salt='password-reset-salt')
            reset_link = url_for('reset_password', token=token, _external=True)
            email_html = render_template('email/reset_password.html', reset_link=reset_link)
            send_email(email, "Your Password Reset Link for Web Asset Suite", email_html)

        flash('If an account with that email exists, a password reset link has been sent.', 'success')
        return redirect(url_for('login'))
    return render_template('forgot_password.html')

@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    try:
        email = s.loads(token, salt='password-reset-salt', max_age=3600)
    except (SignatureExpired, BadTimeSignature):
        flash('The password reset link is invalid or has expired.', 'error')
        return redirect(url_for('forgot_password'))
    if request.method == 'POST':
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first_or_404()
        user.set_password(password)
        db.session.commit()
        flash('Your password has been updated successfully! Please log in.', 'success')
        return redirect(url_for('login'))
    return render_template('reset_password.html', token=token)

@app.route('/')
def home() -> str: return render_template('index.html')

@app.route('/extractor')
def extractor_page() -> str: return render_template('extractor.html')

@app.route('/compressor')
def compressor_page() -> str: return render_template('compressor.html')

@app.route('/contrast-checker')
def contrast_checker_page() -> str: return render_template('contrast_checker.html')

@app.route('/font-pairings')
def font_pairings_page() -> str: return render_template('font_pairings.html')

@app.route('/about')
def about_page() -> str: return render_template('about.html')

@app.route('/contact')
def contact_page() -> str: return render_template('contact.html')

@app.route('/privacy-policy')
def privacy_page() -> str: return render_template('privacy.html')

@app.route('/terms-and-conditions')
def terms_page() -> str: return render_template('terms.html')

@app.route('/disclaimer')
def disclaimer_page() -> str: return render_template('disclaimer.html')

@app.route('/subscribe', methods=['POST'])
def subscribe():
    email = request.form.get('email')
    if not email:
        flash('Please enter an email address.', 'error')
        return redirect(request.referrer or url_for('home'))

    existing_subscriber = Subscriber.query.filter_by(email=email).first()
    if existing_subscriber:
        flash('This email is already subscribed. Thank you!', 'success')
    else:
        new_subscriber = Subscriber(email=email)
        db.session.add(new_subscriber)
        db.session.commit()
        flash('Thank you for subscribing!', 'success')
        
    return redirect(request.referrer or url_for('home'))

@app.route('/api/google-fonts')
@csrf.exempt
def get_google_fonts():
    if not check_and_increment_usage():
        return jsonify({'error': 'Usage limit reached. Please create an account to continue.'}), 403

    api_key = os.getenv('GOOGLE_FONTS_API_KEY')
    if not api_key: return jsonify({'error': 'Google Fonts API key is not configured on the server.'}), 500
    api_url = f"https://www.googleapis.com/webfonts/v1/webfonts?key={api_key}&sort=popularity"
    try:
        response = requests.get(api_url, timeout=10)
        response.raise_for_status() 
        return Response(response.content, content_type=response.headers['Content-Type'])
    except requests.exceptions.RequestException as e:
        return jsonify({'error': f'Failed to fetch font data: {e}'}), 502

@app.route('/extract', methods=['POST'])
@csrf.exempt
def handle_extraction_request() -> FlaskResponse:
    if not check_and_increment_usage():
        return jsonify({'error': 'Usage limit reached. Please create an account to continue.'}), 403
        
    options = request.get_json()
    if not options or not (url := options.get('url')):
        return jsonify({'error': 'URL is required'}), 400
    
    url = 'https://' + url if not url.startswith(('http://', 'https://')) else url
    
    try:
        images, fonts, colors_data = extract_assets_from_page(url, options)
        
        final_response: Dict[str, Any] = {}
        assets_found = False
        
        if options.get('extract_images') and (image_list := sorted(list(images))):
            final_response['images'] = image_list
            assets_found = True
        if options.get('extract_fonts') and (font_list := sorted(fonts, key=lambda x: x.get('displayName', ''))):
            final_response['fonts'] = font_list
            assets_found = True
        if options.get('extract_colors') and (color_palette := get_clustered_color_palette(colors_data)):
            final_response['colors'] = color_palette
            assets_found = True

        if any(options.get(k) for k in ['extract_images', 'extract_fonts', 'extract_colors']) and not assets_found:
            return jsonify({'error': 'Could not extract any assets. The site may be protected or empty.'}), 500
        
        track_usage('extractor', metadata={'url': url})
        print(f"Scan Complete. Found {len(final_response.get('images', []))} images, {len(final_response.get('fonts', []))} fonts.")
        return jsonify(final_response)
    
    except Exception as e:
        traceback.print_exc()
        error_message = str(e)
        if "net::ERR_NAME_NOT_RESOLVED" in error_message:
            return jsonify({'error': 'The domain name could not be found. Please check the URL.'}), 500
        return jsonify({'error': f'An unexpected server error occurred: {e}'}), 500

# --- START: NEW ADVANCED COMPRESS IMAGE FUNCTION ---
@app.route('/compress-image', methods=['POST'])
@csrf.exempt
def compress_image() -> FlaskResponse:
    if not check_and_increment_usage():
        return jsonify({'error': 'Usage limit reached. Please create an account to continue.'}), 403

    if 'image' not in request.files or not (file := request.files['image']).filename:
        return jsonify({'error': 'No image file provided'}), 400

    original_bytes = file.read()
    original_size = len(original_bytes)
    if original_size > MAX_FILE_SIZE:
        return jsonify({'error': f'File size exceeds {MAX_FILE_SIZE // (1024*1024)}MB'}), 413

    # Use a temporary directory to handle files safely
    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            target_reduction = max(0, min(90, int(request.form.get('target_reduction', 50))))
            target_size = original_size * (1 - (target_reduction / 100))
            
            ext = os.path.splitext(file.filename)[1].lower()
            input_path = os.path.join(temp_dir, f"original{ext}")
            output_path = os.path.join(temp_dir, f"compressed{ext}")

            with open(input_path, 'wb') as f:
                f.write(original_bytes)

            final_bytes = None
            mimetype, ext_out = '', ''

            if ext in ['.jpg', '.jpeg']:
                mimetype, ext_out = 'image/jpeg', 'jpg'
                
                # Command-line tools check
                if not shutil.which("mozjpeg"):
                    raise RuntimeError("mozjpeg command not found on the server.")

                # High-fidelity pass (no chroma subsampling)
                cmd_hi_fi = [
                    "mozjpeg", "-quality", "85", "-outfile", output_path,
                    "-sample", "1x1", # This is equivalent to subsampling=0
                    input_path
                ]
                subprocess.run(cmd_hi_fi, check=True, capture_output=True)
                
                with open(output_path, 'rb') as f:
                    hi_fi_bytes = f.read()
                
                if len(hi_fi_bytes) <= target_size:
                    final_bytes = hi_fi_bytes
                else:
                    # Fallback to iterative search with standard (faster) subsampling
                    best_effort_bytes = hi_fi_bytes
                    for quality in range(85, 74, -5): # Quality floor of 75
                        cmd = ["mozjpeg", "-quality", str(quality), "-outfile", output_path, input_path]
                        subprocess.run(cmd, check=True, capture_output=True)
                        with open(output_path, 'rb') as f:
                            current_bytes = f.read()
                        
                        if len(current_bytes) < len(best_effort_bytes):
                            best_effort_bytes = current_bytes
                        
                        if len(current_bytes) <= target_size:
                            final_bytes = current_bytes
                            break
                    
                    if final_bytes is None:
                        final_bytes = best_effort_bytes

            elif ext == '.png':
                mimetype, ext_out = 'image/png', 'png'
                
                # Command-line tools check
                if not shutil.which("oxipng") or not shutil.which("pngquant"):
                     raise RuntimeError("oxipng or pngquant command not found on the server.")

                # Lossless compression with OxiPNG
                cmd_lossless = ["oxipng", "-o", "4", "-s", "--strip", "safe", "-a", "-Z", "-out", output_path, input_path]
                subprocess.run(cmd_lossless, check=True, capture_output=True)
                with open(output_path, 'rb') as f:
                    lossless_bytes = f.read()

                if len(lossless_bytes) <= target_size or target_reduction <= 30:
                    final_bytes = lossless_bytes
                else:
                    # Lossy compression with pngquant
                    cmd_lossy = ["pngquant", "--force", "--output", output_path, "--quality", "70-95", "256", input_path]
                    subprocess.run(cmd_lossy, check=True, capture_output=True)
                    with open(output_path, 'rb') as f:
                        lossy_bytes = f.read()
                    
                    # Use the smaller of the two results
                    final_bytes = lossy_bytes if len(lossy_bytes) < len(lossless_bytes) else lossless_bytes
            else:
                return jsonify({'error': 'Unsupported format. Use JPG or PNG.'}), 400

            if final_bytes is None:
                raise RuntimeError("Compression resulted in an empty file.")

            final_size = len(final_bytes)
            success = final_size <= target_size

            if final_size < original_size:
                track_usage('compressor', metadata={
                    'file_type': ext.replace('.', '').upper(), 'original_size': original_size,
                    'compressed_size': final_size, 'target_reduction': target_reduction
                })

            filename = f"compressed_{os.path.splitext(file.filename)[0]}.{ext_out}"
            resp = send_file(io.BytesIO(final_bytes), mimetype=mimetype, as_attachment=True, download_name=filename)
            resp.headers['X-Original-Size'] = str(original_size)
            resp.headers['X-Compressed-Size'] = str(final_size)
            resp.headers['X-Compression-Successful'] = str(success).lower()
            return resp

        except subprocess.CalledProcessError as e:
            app.logger.error(f"Compression tool failed. STDERR: {e.stderr.decode()}")
            return jsonify({'error': 'The compression engine failed. The image may be corrupt or in an unsupported format.'}), 500
        except RuntimeError as e:
             app.logger.error(f"Server configuration error: {e}")
             return jsonify({'error': str(e)}), 500
        except Exception as e:
            traceback.print_exc()
            return jsonify({'error': f'An unexpected server error occurred during compression.'}), 500
# --- END: NEW ADVANCED COMPRESS IMAGE FUNCTION ---

@app.route('/download-image')
@login_required
def download_image() -> FlaskResponse:
    if not (image_url := request.args.get('url')) or not (page_url := request.args.get('page_url')):
        return "Missing URL parameters", 400
    try:
        headers = {'User-Agent': 'Mozilla/5.0', 'Referer': unquote(page_url)}
        resp = requests.get(unquote(image_url), headers=headers, stream=True, timeout=10)
        resp.raise_for_status()
        mimetype = resp.headers.get('Content-Type', 'application/octet-stream')
        name = re.sub(r'[^a-zA-Z0-9_-]', '', os.path.splitext(unquote(image_url).split('/')[-1].split('?')[0])[0] or 'image')
        if 'svg' in mimetype: ext = 'svg'
        elif 'gif' in mimetype: ext = 'gif'
        else: ext = 'png'
        final_bytes = resp.content
        if ext == 'png' and 'svg' not in mimetype and 'gif' not in mimetype:
            final_bytes_io = io.BytesIO()
            Image.open(io.BytesIO(resp.content)).convert("RGBA").save(final_bytes_io, format='PNG')
            final_bytes = final_bytes_io.getvalue()
        return Response(final_bytes, mimetype=mimetype, headers={"Content-Disposition": f"attachment; filename=\"{name[:100]}.{ext}\""})
    except Exception as e:
        traceback.print_exc()
        return f"Failed to process image: {e}", 500

@app.route('/admin')
@app.route('/admin/dashboard')
@login_required
@admin_required
def admin_dashboard():
    now = datetime.utcnow()
    day_ago, week_ago, month_ago, two_months_ago = now - timedelta(days=1), now - timedelta(days=7), now - timedelta(days=30), now - timedelta(days=60)
    total_users = User.query.count()
    new_users_day, new_users_week, new_users_month = User.query.filter(User.created_at >= day_ago).count(), User.query.filter(User.created_at >= week_ago).count(), User.query.filter(User.created_at >= month_ago).count()
    dau, mau = User.query.filter(User.last_seen >= day_ago).count(), User.query.filter(User.last_seen >= month_ago).count()
    churn_cohort_total = User.query.filter(User.created_at.between(two_months_ago, month_ago)).count()
    churn_rate = 0.0
    if churn_cohort_total > 0:
        churn_cohort_active = User.query.filter(User.created_at.between(two_months_ago, month_ago), User.last_seen >= month_ago).count()
        churn_rate = (1 - (churn_cohort_active / churn_cohort_total)) * 100
    days = [(now.date() - timedelta(days=i)) for i in range(29, -1, -1)]
    signups_map = {str(date_obj): count for date_obj, count in db.session.query(func.date(User.created_at), func.count(User.id)).filter(User.created_at >= month_ago).group_by(func.date(User.created_at)).all()}
    signup_data = [signups_map.get(str(day), 0) for day in days]
    chart_labels = [day.strftime('%b %d') for day in days]
    tool_usage_counts = db.session.query(ToolUsage.tool_name, func.count(ToolUsage.id)).group_by(ToolUsage.tool_name).all()
    recent_users = User.query.order_by(User.created_at.desc()).limit(5).all()
    ga_data = get_google_analytics_data(GA_PROPERTY_ID, reports=['overview'])
    funnel_data = {'visitors': ga_data.get('total_visitors_30_days', 0) if ga_data else 0, 'signups': total_users, 'active_users': mau}
    active_v_inactive = {'active': mau, 'inactive': total_users - mau}
    return render_template(
        'admin/dashboard.html',
        dau=dau, mau=mau, new_users_day=new_users_day, new_users_week=new_users_week, new_users_month=new_users_month,
        churn_rate=churn_rate, funnel_data=funnel_data, total_users=total_users, chart_labels=chart_labels, signup_data=signup_data,
        tool_usage_counts=dict(tool_usage_counts), recent_users=recent_users, ga_data=ga_data, active_v_inactive=active_v_inactive
    )

@app.route('/admin/analytics/acquisition')
@login_required
@admin_required
def acquisition_analytics():
    ga_data = get_google_analytics_data(GA_PROPERTY_ID, reports=['acquisition'])
    return render_template('admin/acquisition_analytics.html', ga_data=ga_data)

@app.route('/admin/analytics/engagement')
@login_required
@admin_required
def engagement_analytics():
    now = datetime.utcnow()
    retention_data = {}
    for days in [7, 30, 90]:
        cohort_start, cohort_end, activity_start = now - timedelta(days=days*2), now - timedelta(days=days), now - timedelta(days=days)
        cohort_total = User.query.filter(User.created_at.between(cohort_start, cohort_end)).count()
        retention_data[f'{days}_day'] = ((User.query.filter(User.created_at.between(cohort_start, cohort_end), User.last_seen >= activity_start).count() / cohort_total) * 100) if cohort_total > 0 else None
    tool_usage_counts = db.session.query(ToolUsage.tool_name, func.count(ToolUsage.id)).group_by(ToolUsage.tool_name).order_by(func.count(ToolUsage.id).desc()).all()
    ga_data = get_google_analytics_data(GA_PROPERTY_ID, reports=['engagement'])
    return render_template('admin/engagement_analytics.html', ga_data=ga_data, retention_data=retention_data, tool_usage_counts=dict(tool_usage_counts))

@app.route('/admin/analytics/creative-insights')
@login_required
@admin_required
def creative_insights():
    compressor_usages = ToolUsage.query.filter_by(tool_name='compressor').all()
    total_original_size, total_compressed_size, file_type_counts = 0, 0, {}
    for usage in compressor_usages:
        if usage.metadata_json:
            try:
                data = json.loads(usage.metadata_json)
                total_original_size += data.get('original_size', 0)
                total_compressed_size += data.get('compressed_size', 0)
                file_type = data.get('file_type')
                if file_type: file_type_counts[file_type] = file_type_counts.get(file_type, 0) + 1
            except json.JSONDecodeError: continue
    avg_compression_ratio = (1 - (total_compressed_size / total_original_size)) * 100 if total_original_size > 0 else 0
    sorted_file_types = dict(sorted(file_type_counts.items(), key=lambda item: item[1], reverse=True))
    return render_template('admin/creative_insights.html', avg_compression_ratio=avg_compression_ratio, file_type_counts=sorted_file_types)

@app.route('/admin/analytics/real-time')
@login_required
@admin_required
def real_time_analytics():
    ga_data = get_google_analytics_data(GA_PROPERTY_ID, reports=['realtime'])
    fifteen_minutes_ago = datetime.utcnow() - timedelta(minutes=15)
    recent_tool_usages = db.session.query(ToolUsage.tool_name, func.count(ToolUsage.id)).filter(ToolUsage.timestamp >= fifteen_minutes_ago).group_by(ToolUsage.tool_name).all()
    return render_template('admin/real_time_analytics.html', ga_data=ga_data, recent_tool_usages=dict(recent_tool_usages))

@app.route('/admin/users')
@login_required
@admin_required
def manage_users():
    page = request.args.get('page', 1, type=int)
    query = request.args.get('query', '')
    status_filter = request.args.get('status', '')
    role_filter = request.args.get('role', '')
    base_query = User.query
    if query:
        search_term = f"%{query}%"
        base_query = base_query.filter(
            or_(
                User.first_name.ilike(search_term),
                User.last_name.ilike(search_term),
                User.username.ilike(search_term),
                User.email.ilike(search_term)
            )
        )
    if status_filter:
        base_query = base_query.filter(User.status == status_filter)
    if role_filter:
        base_query = base_query.filter(User.role == role_filter)
    users = base_query.order_by(User.id.desc()).paginate(page=page, per_page=20)
    return render_template('admin/manage_users.html', users=users, query=query, status_filter=status_filter, role_filter=role_filter)

@app.route('/admin/subscribers')
@login_required
@admin_required
def manage_subscribers():
    subscribers = Subscriber.query.order_by(Subscriber.subscribed_on.desc()).all()
    return render_template('admin/manage_subscribers.html', subscribers=subscribers)

@app.route('/admin/subscribers/delete/<int:subscriber_id>', methods=['POST'])
@login_required
@admin_required
def delete_subscriber(subscriber_id):
    subscriber = Subscriber.query.get_or_404(subscriber_id)
    db.session.delete(subscriber)
    db.session.commit()
    flash(f'Subscriber {subscriber.email} has been deleted.', 'success')
    return redirect(url_for('manage_subscribers'))

@app.route('/admin/users/view/<int:user_id>')
@login_required
@admin_required
def view_user(user_id):
    user = User.query.get_or_404(user_id)
    page = request.args.get('page', 1, type=int)
    activity_log = user.activity_logs.order_by(UserActivityLog.timestamp.desc()).paginate(page=page, per_page=15)
    usage_stats = db.session.query(
        ToolUsage.tool_name, func.count(ToolUsage.id)
    ).filter(ToolUsage.user_id == user_id).group_by(ToolUsage.tool_name).all()
    return render_template('admin/user_details.html', user=user, activity_log=activity_log, usage_stats=dict(usage_stats))

@app.route('/admin/users/edit/<int:user_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_user(user_id):
    user = User.query.get_or_404(user_id)
    if request.method == 'POST':
        user.first_name = request.form.get('first_name')
        user.last_name = request.form.get('last_name')
        user.email = request.form.get('email')
        user.role = request.form.get('role')
        user.status = request.form.get('status')
        db.session.commit()
        flash(f'User {user.email} updated successfully.', 'success')
        return redirect(url_for('manage_users'))
    return render_template('admin/edit_user.html', user=user)

@app.route('/admin/users/delete/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash("You cannot delete your own account.", "error")
        return redirect(url_for('manage_users'))
    db.session.delete(user)
    db.session.commit()
    flash(f'User {user.email} has been deleted.', 'success')
    return redirect(url_for('manage_users'))

@app.route('/admin/users/toggle_status/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def toggle_user_status(user_id):
    user = User.query.get_or_404(user_id)
    if user.status == 'active':
        user.status = 'suspended'
        flash(f'User {user.email} has been suspended.', 'success')
    else:
        user.status = 'active'
        flash(f'User {user.email} has been activated.', 'success')
    db.session.commit()
    return redirect(url_for('manage_users'))

@app.route('/admin/posts')
@login_required
@moderator_or_admin_required
def manage_posts():
    page = request.args.get('page', 1, type=int)
    search_query = request.args.get('search', '')
    category_filter = request.args.get('category', '')
    status_filter = request.args.get('status', '')
    sort_by = request.args.get('sort', 'date_desc')
    base_query = Post.query.outerjoin(User).outerjoin(Category)
    if search_query:
        search_term = f"%{search_query}%"
        base_query = base_query.filter(or_(Post.title.ilike(search_term), User.first_name.ilike(search_term)))
    if category_filter:
        base_query = base_query.filter(Category.slug == category_filter)
    if status_filter:
        base_query = base_query.filter(Post.status == status_filter)
    if sort_by == 'date_asc':
        base_query = base_query.order_by(Post.pub_date.asc())
    elif sort_by == 'views_desc':
        base_query = base_query.order_by(Post.views.desc())
    else:
        base_query = base_query.order_by(Post.pub_date.desc())
    posts = base_query.paginate(page=page, per_page=15)
    categories = Category.query.all()
    return render_template('admin/manage_posts.html', posts=posts, categories=categories,
                           search=search_query, category_filter=category_filter,
                           status_filter=status_filter, sort_by=sort_by)

@app.route('/admin/posts/editor', methods=['GET'])
@app.route('/admin/posts/editor/<int:post_id>', methods=['GET'])
@login_required
@moderator_or_admin_required
def post_editor(post_id=None):
    post = Post.query.get_or_404(post_id) if post_id else None
    categories = Category.query.order_by(Category.name).all()
    tags = [tag.name for tag in post.tags] if post and post.tags else []
    return render_template('admin/post_editor.html', post=post, categories=categories, tags=json.dumps(tags))

@app.route('/admin/posts/upload_image', methods=['POST'])
@login_required
@moderator_or_admin_required
def upload_image_for_editor():
    if 'image' not in request.files:
        return jsonify({'error': 'No image file provided'}), 400
    file = request.files['image']
    if file.filename == '' or not allowed_file(file.filename):
        return jsonify({'error': 'Invalid file type'}), 400
    try:
        file.seek(0, os.SEEK_END)
        file_length = file.tell()
        if file_length > MAX_FILE_SIZE: 
             return jsonify({'error': f'Image file size exceeds the limit of {MAX_FILE_SIZE // (1024*1024)}MB.'}), 413
        file.seek(0)
        img = Image.open(file)
        img.verify()
        file.seek(0)
        filename = secure_filename(f"{int(datetime.utcnow().timestamp())}-{file.filename}")
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        image_url = url_for('uploaded_file', filename=filename)
        return jsonify({'location': image_url})
    except UnidentifiedImageError:
        return jsonify({'error': 'The uploaded file is not a valid image.'}), 400
    except Exception as e:
        print(f"Error during editor image upload: {e}")
        return jsonify({'error': 'Server error during image upload.'}), 500

@app.route('/admin/posts/save', methods=['POST'])
@login_required
@moderator_or_admin_required
def save_post():
    post_id = request.form.get('post_id')
    if post_id:
        post = Post.query.get_or_404(post_id)
    else:
        post = Post(author_id=current_user.id)
    post.title = request.form.get('title')
    post.slug = create_slug(post.title, Post, post.id)
    if not post_id:
        db.session.add(post)
    raw_content = request.form.get('content')
    post.content = sanitize_html(raw_content)
    post.meta_title = request.form.get('meta_title')
    post.meta_description = request.form.get('meta_description')
    post.status = request.form.get('status')
    category_name = request.form.get('category_name', '').strip()
    if category_name:
        category = Category.query.filter(func.lower(Category.name) == func.lower(category_name)).first()
        if not category:
            new_slug = create_slug(category_name, Category)
            category = Category(name=category_name, slug=new_slug)
            db.session.add(category)
        post.category = category
    else:
        post.category = None
    pub_date_str = request.form.get('pub_date')
    if pub_date_str:
        try:
            post.pub_date = datetime.strptime(pub_date_str, '%Y-%m-%d %H:%M')
        except ValueError:
            flash('Invalid date format. Please use YYYY-MM-DD HH:MM.', 'error')
    else:
        post.pub_date = datetime.utcnow()
    tags_json = request.form.get('tags', '[]')
    tag_names = [item['value'] for item in json.loads(tags_json)]
    post.tags.clear()
    for name in tag_names:
        tag = Tag.query.filter_by(name=name).first()
        if not tag:
            tag = Tag(name=name)
            db.session.add(tag)
        post.tags.append(tag)
    if 'featured_image' in request.files:
        file = request.files['featured_image']
        if file and file.filename != '' and allowed_file(file.filename):
            file.seek(0, os.SEEK_END)
            file_length = file.tell()
            if file_length > MAX_FILE_SIZE:
                flash(f'Featured image file size exceeds the limit of {MAX_FILE_SIZE // (1024*1024)}MB.', 'error')
                return redirect(request.referrer or url_for('post_editor', post_id=post.id))
            file.seek(0)
            try:
                img = Image.open(file)
                img.verify()
                file.seek(0)
            except UnidentifiedImageError:
                flash('The uploaded file is not a valid image.', 'error')
                return redirect(request.referrer or url_for('post_editor', post_id=post.id))
            filename = secure_filename(f"{int(datetime.utcnow().timestamp())}-{file.filename}")
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            post.featured_image = filename
    db.session.commit()
    flash(f'Post "{post.title}" saved successfully!', 'success')
    return redirect(url_for('manage_posts'))

@app.route('/admin/posts/delete/<int:post_id>', methods=['POST'])
@login_required
@moderator_or_admin_required
def delete_post(post_id):
    post = Post.query.get_or_404(post_id)
    db.session.delete(post)
    db.session.commit()
    flash('Blog post deleted successfully.', 'success')
    return redirect(url_for('manage_posts'))

@app.route('/admin/posts/bulk_action', methods=['POST'])
@login_required
@moderator_or_admin_required
def bulk_post_action():
    action = request.form.get('action')
    post_ids = request.form.getlist('post_ids')
    if not action or not post_ids:
        flash('No action or posts selected.', 'error')
        return redirect(url_for('manage_posts'))
    posts = Post.query.filter(Post.id.in_(post_ids)).all()
    if action == 'delete':
        for post in posts:
            db.session.delete(post)
        flash(f'{len(posts)} posts deleted.', 'success')
    elif action in ['draft', 'published', 'scheduled']:
        for post in posts:
            post.status = action
        flash(f'Status changed to "{action}" for {len(posts)} posts.', 'success')
    db.session.commit()
    return redirect(url_for('manage_posts'))

@app.route('/admin/posts/preview/<int:post_id>')
@login_required
@moderator_or_admin_required
def preview_post(post_id):
    post = Post.query.get_or_404(post_id)
    return render_template('post.html', post=post, is_preview=True)

@app.route('/admin/categories', methods=['GET', 'POST'])
@login_required
@moderator_or_admin_required
def manage_categories():
    if request.method == 'POST':
        category_id = request.form.get('category_id')
        name = request.form.get('name')
        if category_id:
            category = Category.query.get_or_404(category_id)
            category.name = name
            category.slug = create_slug(name, Category, category.id)
            flash('Category updated.', 'success')
        else:
            new_cat = Category(name=name, slug=create_slug(name, Category))
            db.session.add(new_cat)
            flash('Category created.', 'success')
        db.session.commit()
        return redirect(url_for('manage_categories'))
    categories = Category.query.order_by(Category.name).all()
    return render_template('admin/manage_categories.html', categories=categories)

@app.route('/admin/categories/delete/<int:category_id>', methods=['POST'])
@login_required
@moderator_or_admin_required
def delete_category(category_id):
    category = Category.query.get_or_404(category_id)
    if category.posts.count() > 0:
        flash('Cannot delete a category that has posts associated with it.', 'error')
    else:
        db.session.delete(category)
        db.session.commit()
        flash('Category deleted.', 'success')
    return redirect(url_for('manage_categories'))

@app.route('/blog')
def blog_list():
    page = request.args.get('page', 1, type=int)
    selected_category_slug = request.args.get('category')
    posts_query = Post.query.filter_by(status='published')
    if selected_category_slug:
        posts_query = posts_query.join(Category).filter(Category.slug == selected_category_slug)
    posts = posts_query.order_by(Post.pub_date.desc()).paginate(page=page, per_page=9)
    categories = Category.query.order_by(Category.name).all()
    return render_template('blog.html', posts=posts, categories=categories, selected_category_slug=selected_category_slug)

@app.route('/blog/<string:slug>')
def view_post(slug):
    post = Post.query.filter_by(slug=slug, status='published').first()
    is_preview = False
    if not post:
        if current_user.is_authenticated and current_user.role in ['admin', 'moderator']:
            post = Post.query.filter_by(slug=slug).first_or_404()
            flash('This is a preview of a non-published post.', 'success')
            is_preview = True
        else:
            return "Post not found", 404
    if post.status == 'published' and (not current_user.is_authenticated or current_user.id != post.author_id):
        post.views = (post.views or 0) + 1
        db.session.commit()
    soup = BeautifulSoup(post.content, 'html.parser')
    text_content = soup.get_text()
    word_count = len(text_content.split())
    read_time = max(1, round(word_count / 200))
    toc = []
    headings = soup.find_all(['h2', 'h3'])
    for heading in headings:
        heading_text = heading.get_text()
        slug_id = re.sub(r'[^\w\s-]', '', heading_text).strip().lower()
        heading_id = re.sub(r'[\s_-]+', '-', slug_id)
        heading['id'] = heading_id
        toc.append({'id': heading_id, 'text': heading_text, 'level': heading.name})
    updated_content = str(soup)
    return render_template('post.html', post=post, is_preview=is_preview, 
                           read_time=read_time, toc=toc, content=updated_content)

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    DEBUG_MODE = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    app.run(debug=DEBUG_MODE)

# --- END OF FINAL, COMPLETE app.py FILE ---