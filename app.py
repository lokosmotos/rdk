import os
import re
import logging
import atexit
from datetime import datetime, timedelta
from logging.handlers import RotatingFileHandler
from flask import Flask, render_template, request, send_from_directory
from werkzeug.utils import secure_filename
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# Import your custom utilities
from utils.excel_to_srt import convert_to_srt
from utils.word_renamer import rename_word_file
from utils.profanity_checker import check_profanity, clean_profanity, final_qc

# Application Configuration
class Config:
    UPLOAD_FOLDER = 'uploads'
    OUTPUT_FOLDER = 'outputs'
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB limit
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your-secure-key-here'

# Initialize Flask app
app = Flask(__name__)
app.config.from_object(Config)

# Security and Rate Limiting
csrf = CSRFProtect(app)
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)

# Suppress warnings
import warnings
warnings.filterwarnings("ignore", message="Using the in-memory storage")

# Ensure upload directories exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['OUTPUT_FOLDER'], exist_ok=True)

# Configure logging
log_formatter = logging.Formatter('%(asctime)s %(levelname)s: %(message)s')
handler = RotatingFileHandler('app.log', maxBytes=10000, backupCount=3)
handler.setFormatter(log_formatter)
handler.setLevel(logging.INFO)
app.logger.addHandler(handler)
app.logger.setLevel(logging.INFO)

# File cleanup at exit
def cleanup_old_files():
    now = datetime.now()
    for folder in [app.config['UPLOAD_FOLDER'], app.config['OUTPUT_FOLDER']]:
        if not os.path.exists(folder):
            continue
        for filename in os.listdir(folder):
            filepath = os.path.join(folder, filename)
            try:
                if os.path.isfile(filepath):
                    mtime = datetime.fromtimestamp(os.path.getmtime(filepath))
                    if now - mtime > timedelta(hours=24):
                        os.remove(filepath)
                        app.logger.info(f"Cleaned up: {filepath}")
            except Exception as e:
                app.logger.error(f"Cleanup error: {str(e)}")

atexit.register(cleanup_old_files)

# Helper functions
def allowed_file(filename, extensions):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in extensions

def validate_srt_file(file_stream):
    try:
        first_line = file_stream.readline().decode('utf-8', errors='ignore')
        file_stream.seek(0)
        return first_line.strip().isdigit()
    except Exception:
        return False

# Routes
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/remove_cc', methods=['GET', 'POST'])
@limiter.limit("10 per minute")
def remove_cc_route():
    if request.method == 'POST':
        if 'srtfile' not in request.files:
            return "No file selected", 400
        file = request.files['srtfile']
        if file.filename == '':
            return "No file selected", 400
        if not allowed_file(file.filename, ['srt']):
            return "Invalid file type", 400
        if not validate_srt_file(file.stream):
            return "Invalid SRT file", 400

        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        app.logger.info(f"Uploaded: {filename}")

        try:
            cleaned_file = remove_cc_from_srt(filepath)
            return send_from_directory(app.config['OUTPUT_FOLDER'], cleaned_file, as_attachment=True)
        except Exception as e:
            app.logger.error(f"Error: {str(e)}")
            return str(e), 500

    return render_template('remove_cc.html')

# ... [Include all your other routes here following the same pattern] ...

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
