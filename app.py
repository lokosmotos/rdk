import os
import re
import logging
import atexit
import shutil
from datetime import datetime, timedelta
from flask import Flask, render_template, request, send_from_directory
from werkzeug.utils import secure_filename
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from utils.excel_to_srt import convert_to_srt
from utils.word_renamer import rename_word_file
from utils.profanity_checker import check_profanity, clean_profanity, final_qc

# Application Configuration
class Config:
    UPLOAD_FOLDER = 'uploads'
    OUTPUT_FOLDER = 'outputs'
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB limit
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your-secret-key-here'

# Initialize Flask app
app = Flask(__name__)
app.config.from_object(Config)

# Security and Rate Limiting
csrf = CSRFProtect(app)
limiter = Limiter(
    app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)

# Ensure upload directories exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['OUTPUT_FOLDER'], exist_ok=True)

# Configure logging
handler = RotatingFileHandler('app.log', maxBytes=10000, backupCount=3)
handler.setLevel(logging.INFO)
app.logger.addHandler(handler)

# File cleanup at exit
def cleanup_old_files():
    """Remove files older than 24 hours"""
    now = datetime.now()
    for folder in [app.config['UPLOAD_FOLDER'], app.config['OUTPUT_FOLDER']]:
        for filename in os.listdir(folder):
            filepath = os.path.join(folder, filename)
            if os.path.isfile(filepath):
                mtime = datetime.fromtimestamp(os.path.getmtime(filepath))
                if now - mtime > timedelta(hours=24):
                    try:
                        os.remove(filepath)
                        app.logger.info(f"Cleaned up old file: {filepath}")
                    except Exception as e:
                        app.logger.error(f"Error cleaning up {filepath}: {str(e)}")

atexit.register(cleanup_old_files)

# Helper functions
def allowed_file(filename, extensions):
    """Check if file has allowed extension"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in extensions

def validate_srt_file(file_stream):
    """Quick validation that this might be an SRT file"""
    first_line = file_stream.readline().decode('utf-8', errors='ignore')
    file_stream.seek(0)  # Rewind the file
    return first_line.strip().isdigit()  # SRT files typically start with a number

# ===== CC Removal =====
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
            return "Invalid file type. Please upload an SRT file.", 400
            
        if not validate_srt_file(file.stream):
            return "File doesn't appear to be a valid SRT file", 400

        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        app.logger.info(f"SRT file uploaded: {filename}")

        try:
            cleaned_file = remove_cc_from_srt(filepath)
            app.logger.info(f"Successfully processed: {filename} -> {cleaned_file}")
            return send_from_directory(
                app.config['OUTPUT_FOLDER'], 
                cleaned_file, 
                as_attachment=True
            )
        except Exception as e:
            app.logger.error(f"Error processing {filename}: {str(e)}")
            return str(e), 500

    return render_template('remove_cc.html')

def remove_cc_from_srt(file_path):
    """Enhanced SRT CC removal with multiple improvements"""
    cc_patterns = [
        r"\[.*?\]", r"\(.*?\)", r"\{.*?\}", r"<.*?>", r'♪.*?♪', r'#.*?#',
        r"\bCC:\s*\w+", r"\bSUBTITLE:\s*\w+", r"\bSUBS:\s*\w+", r'\\[A-Za-z]+',
        r'\{[^}]*\}', r'<!--.*?-->', r'^M[\d\s]+$', r'^\d+$', r"^\s*$"
    ]
    
    combined_pattern = re.compile("|".join(cc_patterns), re.IGNORECASE)
    time_pattern = re.compile(r"\d{2}:\d{2}:\d{2},\d{3} --> \d{2}:\d{2}:\d{2},\d{3}")
    
    try:
        # Try UTF-8 first, fallback to latin-1
        try:
            with open(file_path, 'r', encoding='utf-8-sig') as f:
                srt_content = f.readlines()
        except UnicodeDecodeError:
            with open(file_path, 'r', encoding='latin-1') as f:
                srt_content = f.readlines()
        
        cleaned_content = []
        in_subtitle = False
        
        for line in srt_content:
            line = line.strip()
            
            if not line:
                cleaned_content.append("\n")
                continue
                
            if time_pattern.match(line):
                cleaned_content.append(line + "\n")
                in_subtitle = True
                continue
                
            if line.isdigit():
                continue
                
            if in_subtitle:
                cleaned_line = re.sub(combined_pattern, "", line).strip()
                if cleaned_line:
                    cleaned_content.append(cleaned_line + "\n")
                in_subtitle = False
            else:
                cleaned_content.append(line + "\n")
        
        # Renumber subtitles
        renumbered_content = []
        counter = 1
        i = 0
        n = len(cleaned_content)
        
        while i < n:
            line = cleaned_content[i].strip()
            
            if time_pattern.match(line):
                renumbered_content.append(f"{counter}\n{line}\n")
                counter += 1
                i += 1
                
                while i < n and cleaned_content[i].strip():
                    renumbered_content.append(cleaned_content[i])
                    i += 1
                
                if i < n and not cleaned_content[i].strip():
                    renumbered_content.append("\n")
                    i += 1
            else:
                i += 1
        
        # Save output
        base_name = os.path.basename(file_path)
        cleaned_file_name = f"cleaned_{base_name}"
        output_path = os.path.join(app.config['OUTPUT_FOLDER'], cleaned_file_name)
        
        with open(output_path, "w", encoding="utf-8") as f:
            f.writelines(renumbered_content)
        
        return cleaned_file_name
        
    except Exception as e:
        raise Exception(f"SRT processing failed: {str(e)}")

# ===== Excel to SRT =====
@app.route('/convert', methods=['GET', 'POST'])
@limiter.limit("10 per minute")
def convert_route():
    if request.method == 'POST':
        if 'excel' not in request.files:
            return "No file selected", 400
            
        file = request.files['excel']
        if file.filename == '':
            return "No file selected", 400
            
        if not allowed_file(file.filename, ['xlsx', 'xls']):
            return "Invalid file type. Please upload an Excel file.", 400

        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        app.logger.info(f"Excel file uploaded: {filename}")

        try:
            srt_path = convert_to_srt(filepath, output_folder=app.config['OUTPUT_FOLDER'])
            app.logger.info(f"Converted Excel to SRT: {filename} -> {os.path.basename(srt_path)}")
            return send_from_directory(
                app.config['OUTPUT_FOLDER'], 
                os.path.basename(srt_path), 
                as_attachment=True
            )
        except Exception as e:
            app.logger.error(f"Error converting {filename}: {str(e)}")
            return str(e), 500

    return render_template('convert.html')

# ===== Word File Renamer =====
@app.route('/rename', methods=['GET', 'POST'])
@limiter.limit("10 per minute")
def rename():
    if request.method == 'POST':
        if 'wordfile' not in request.files:
            return "No file selected", 400
            
        file = request.files['wordfile']
        if file.filename == '':
            return "No file selected", 400
            
        if not allowed_file(file.filename, ['docx', 'doc']):
            return "Invalid file type. Please upload a Word file.", 400

        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        app.logger.info(f"Word file uploaded: {filename}")

        try:
            new_name = rename_word_file(filepath)
            app.logger.info(f"Renamed Word file: {filename} -> {new_name}")
            return f"Renamed file: {new_name}"
        except Exception as e:
            app.logger.error(f"Error renaming {filename}: {str(e)}")
            return str(e), 500

    return render_template('rename.html')

# ===== Profanity Checker =====
@app.route('/profanity', methods=['GET', 'POST'])
@limiter.limit("10 per minute")
def profanity():
    if request.method == 'POST':
        if 'file' not in request.files:
            return "No file selected", 400
            
        file = request.files['file']
        if file.filename == '':
            return "No file selected", 400
            
        if not allowed_file(file.filename, ['srt', 'xlsx', 'xls', 'docx', 'txt']):
            return "Invalid file type", 400

        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        app.logger.info(f"File uploaded for profanity check: {filename}")

        try:
            scan_result = check_profanity(filepath)
            if not scan_result["results"]:
                app.logger.info(f"No profanities found in {filename}")
                return "✅ No profanities detected."

            app.logger.info(f"Profanities found in {filename}: {len(scan_result['results'])} items")
            return render_template('profanity_review.html', 
                               results=scan_result["results"],
                               filetype=scan_result["filetype"], 
                               filename=filename)
        except Exception as e:
            app.logger.error(f"Error scanning {filename}: {str(e)}")
            return str(e), 500

    return render_template('profanity.html')

@app.route('/profanity/clean', methods=['POST'])
@limiter.limit("10 per minute")
def profanity_clean():
    if not request.form.get('filename'):
        return "Invalid request", 400
        
    filename = secure_filename(request.form.get('filename'))
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    
    if not os.path.exists(filepath):
        return "File not found", 404

    try:
        scan_result = check_profanity(filepath)
        replacements = {}
        
        for word in request.form:
            if word.startswith("replace_"):
                profane_word = word.replace("replace_", "")
                replacements[profane_word] = request.form[word]

        cleaned = clean_profanity(
            scan_result["results"], 
            scan_result["original"],
            scan_result["filetype"], 
            replacements
        )

        remaining = final_qc(cleaned, scan_result["filetype"])
        output_filename = f"cleaned_{filename}"
        output_path = os.path.join(app.config['OUTPUT_FOLDER'], output_filename)

        if scan_result["filetype"] == "srt":
            with open(output_path, "w", encoding="utf-8") as f:
                f.writelines(cleaned)
        else:
            cleaned.to_excel(output_path, index=False)

        app.logger.info(f"Profanity cleaned: {filename} -> {output_filename}")
        
        if remaining:
            app.logger.warning(f"QC failed for {filename}: {len(remaining)} remaining items")
            return render_template("qc_failed.html", remaining=remaining)
        else:
            return send_from_directory(
                app.config["OUTPUT_FOLDER"], 
                output_filename, 
                as_attachment=True
            )
            
    except Exception as e:
        app.logger.error(f"Error cleaning {filename}: {str(e)}")
        return str(e), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
