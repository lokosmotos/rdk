from flask import Flask, render_template, request, send_file
from utils.excel_to_srt import convert_to_srt
from utils.word_renamer import rename_word_file
import os

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
OUTPUT_FOLDER = 'outputs'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['OUTPUT_FOLDER'] = OUTPUT_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# Existing Excel to SRT route...
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/convert', methods=['POST'])
def convert_route():
    uploaded_file = request.files['excel']
    language = request.form.get('language')
    if not uploaded_file.filename.endswith(('.xlsx', '.xls')):
        return "Invalid file type. Please upload an Excel file.", 400
    filepath = os.path.join(UPLOAD_FOLDER, uploaded_file.filename)
    uploaded_file.save(filepath)
    try:
        srt_path = convert_to_srt(filepath, language, OUTPUT_FOLDER)
    except Exception as e:
        return str(e), 500
    return send_file(srt_path, as_attachment=True)

# ✅ NEW: Word Renamer route
@app.route('/rename', methods=['GET', 'POST'])
def rename():
    if request.method == 'POST':
        uploaded_file = request.files['wordfile']
        if uploaded_file.filename.endswith('.docx'):
            file_path = os.path.join(UPLOAD_FOLDER, uploaded_file.filename)
            uploaded_file.save(file_path)
            renamed_path = rename_word_file(file_path)  # You define this logic
            return send_file(renamed_path, as_attachment=True)
        return "Invalid file type. Please upload a DOCX file.", 400
    return render_template('rename.html')

# Ensure Render uses the right port
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host="0.0.0.0", port=port)
