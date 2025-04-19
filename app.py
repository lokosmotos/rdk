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

# Import custom utilities
from utils.excel_to_srt import convert_to_srt
from utils.word_renamer import rename_word_file
from utils.profanity_checker import check_profanity, clean_profanity, final_qc

# Configuration
class Config:
    UPLOAD_FOLDER = 'uploads'
    OUTPUT_FOLDER = 'outputs'
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your-very-secret-key-123!'
    USE_REDIS = False

# Initialize Flask app
app = Flask(__name__)
app.config.from_object(Config)

# Security and rate limiting
csrf = CSRFProtect(app)
limiter = Limiter(app=app, key_func=get_remote_address, default_limits=["200 per day", "50 per hour"])

# Warnings suppression
import warnings
warnings.filterwarnings("ignore", message="Using the in-memory storage")

# Ensure upload/output folders exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['OUTPUT_FOLDER'], exist_ok=True)

# Logging setup
log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler = RotatingFileHandler('app.log', maxBytes=10000, backupCount=3)
handler.setFormatter(log_formatter)
handler.setLevel(logging.INFO)
app.logger.addHandler(handler)
app.logger.setLevel(logging.INFO)

# Cleanup function
def cleanup_old_files():
    now = datetime.now()
    for folder in [app.config['UPLOAD_FOLDER'], app.config['OUTPUT_FOLDER']]:
        for filename in os.listdir(folder):
            filepath = os.path.join(folder, filename)
            if os.path.isfile(filepath):
                mtime = datetime.fromtimestamp(os.path.getmtime(filepath))
                if now - mtime > timedelta(hours=24):
                    try:
                        os.remove(filepath)
                        app.logger.info(f"Removed old file: {filepath}")
                    except Exception as e:
                        app.logger.error(f"Error deleting file: {filepath} - {str(e)}")

atexit.register(cleanup_old_files)

# Helpers
def allowed_file(filename, extensions):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in extensions

def validate_srt_file(file_stream):
    try:
        first_line = file_stream.readline().decode('utf-8', errors='ignore')
        file_stream.seek(0)
        return first_line.strip().isdigit()
    except Exception:
        return False

# Home
@app.route('/')
def home():
    return render_template('index.html')

# Remove CC from SRT
@app.route('/remove_cc', methods=['GET', 'POST'])
@limiter.limit("10 per minute")
def remove_cc_route():
    if request.method == 'POST':
        file = request.files.get('srtfile')
        if not file or file.filename == '':
            return "No file selected", 400
        if not allowed_file(file.filename, ['srt']):
            return "Invalid file type", 400
        if not validate_srt_file(file.stream):
            return "Invalid SRT file", 400

        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        try:
            cleaned_filename = remove_cc_from_srt(filepath)
            return send_from_directory(app.config['OUTPUT_FOLDER'], cleaned_filename, as_attachment=True)
        except Exception as e:
            app.logger.error(f"Error removing CC: {str(e)}")
            return str(e), 500

    return render_template('remove_cc.html')

def remove_cc_from_srt(file_path):
    output_filename = f"cleaned_{os.path.basename(file_path)}"
    output_path = os.path.join(app.config['OUTPUT_FOLDER'], output_filename)

    cc_pattern = re.compile(r'\[(.*?)\]|\((.*?)\)', re.IGNORECASE)

    with open(file_path, 'r', encoding='utf-8', errors='ignore') as infile, \
         open(output_path, 'w', encoding='utf-8') as outfile:
        for line in infile:
            if re.match(r'^\d+$', line.strip()) or '-->' in line:
                outfile.write(line)
            else:
                cleaned_line = cc_pattern.sub('', line).strip()
                outfile.write(cleaned_line + '\n' if cleaned_line else '\n')

    return output_filename

# Excel to SRT
@app.route('/convert', methods=['GET', 'POST'])
@limiter.limit("10 per minute")
def convert_route():
    if request.method == 'POST':
        file = request.files.get('excel')
        if not file or file.filename == '':
            return "No file selected", 400
        if not allowed_file(file.filename, ['xlsx', 'xls']):
            return "Invalid file type", 400

        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        try:
            srt_path = convert_to_srt(filepath, app.config['OUTPUT_FOLDER'])
            return send_from_directory(app.config['OUTPUT_FOLDER'], os.path.basename(srt_path), as_attachment=True)
        except Exception as e:
            app.logger.error(f"Excel-to-SRT conversion error: {str(e)}")
            return str(e), 500

    return render_template('convert.html')

# Rename Word File
@app.route('/rename', methods=['GET', 'POST'])
@limiter.limit("10 per minute")
def rename():
    if request.method == 'POST':
        file = request.files.get('wordfile')
        if not file or file.filename == '':
            return "No file selected", 400
        if not allowed_file(file.filename, ['docx', 'doc']):
            return "Invalid file type", 400

        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        try:
            new_name = rename_word_file(filepath)
            return f"Renamed file: {new_name}"
        except Exception as e:
            app.logger.error(f"Rename error: {str(e)}")
            return str(e), 500

    return render_template('rename.html')

# Profanity Check
@app.route('/profanity', methods=['GET', 'POST'])
@limiter.limit("10 per minute")
def profanity():
    if request.method == 'POST':
        file = request.files.get('file')
        if not file or file.filename == '':
            return "No file selected", 400
        if not allowed_file(file.filename, ['srt', 'xlsx', 'xls', 'docx', 'txt']):
            return "Invalid file type", 400

        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        try:
            scan_result = check_profanity(filepath)
            if not scan_result["results"]:
                return "✅ No profanities detected."

            return render_template(
                'profanity_review.html',
                results=scan_result["results"],
                filetype=scan_result["filetype"],
                filename=filename
            )
        except Exception as e:
            app.logger.error(f"Profanity check error: {str(e)}")
            return str(e), 500

    return render_template('profanity.html')

# Add your profanity clean/QC routes here if needed...

# Run server
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
