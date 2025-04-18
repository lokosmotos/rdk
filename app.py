import os
from flask import Flask, render_template, request, send_from_directory
from utils.excel_to_srt import convert_to_srt

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

if __name__ == "__main__":
    app.run(debug=True)
