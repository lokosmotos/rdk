import os
from flask import Flask, render_template, request, send_from_directory
from utils.excel_to_srt import convert_to_srt
from utils.profanity_checker import check_profanity
from utils.word_renamer import rename_word_file

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
OUTPUT_FOLDER = 'outputs'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['OUTPUT_FOLDER'] = OUTPUT_FOLDER

# Create folders if not exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

@app.route('/')
def index():
    return render_template('index.html')

# Excel to SRT
@app.route('/convert', methods=['POST'])
def convert_route():
    uploaded_file = request.files['excel']
    language = request.form.get('language')

    if not uploaded_file.filename.endswith(('.xlsx', '.xls')):
        return "Invalid file type. Please upload an Excel file.", 400

    filepath = os.path.join(app.config['UPLOAD_FOLDER'], uploaded_file.filename)
    uploaded_file.save(filepath)

    try:
        srt_path = convert_to_srt(filepath, language, app.config['OUTPUT_FOLDER'])
    except Exception as e:
        return str(e), 500

    return send_from_directory(app.config['OUTPUT_FOLDER'], os.path.basename(srt_path), as_attachment=True)

# Profanity Checker
@app.route('/check_profanity', methods=['POST'])
def profanity_checker():
    uploaded_file = request.files['file']
    language = request.form.get('language')

    if not uploaded_file.filename.endswith(('.txt', '.srt')):
        return "Invalid file type. Please upload a text or SRT file.", 400

    filepath = os.path.join(app.config['UPLOAD_FOLDER'], uploaded_file.filename)
    uploaded_file.save(filepath)

    try:
        contains_profanity = check_profanity(filepath, language)
    except Exception as e:
        return str(e), 500

    if contains_profanity:
        return "Profanity detected in the file!", 400
    else:
        return "No profanity detected.", 200

# Word Renamer
@app.route('/rename_word', methods=['POST'])
def rename_word():
    uploaded_file = request.files['word_file']

    if not uploaded_file.filename.endswith('.docx'):
        return "Invalid file type. Please upload a Word document.", 400

    filepath = os.path.join(app.config['UPLOAD_FOLDER'], uploaded_file.filename)
    uploaded_file.save(filepath)

    try:
        renamed_file = rename_word_file(filepath)
    except Exception as e:
        return str(e), 500

    return send_from_directory(app.config['OUTPUT_FOLDER'], os.path.basename(renamed_file), as_attachment=True)

if __name__ == "__main__":
    # Get the port from the environment variable, or default to 5000
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
