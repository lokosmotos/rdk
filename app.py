import os
from flask import Flask, render_template, request, send_from_directory, redirect, url_for
from utils.excel_to_srt import convert_to_srt
from utils.word_renamer import rename_word_file
from utils.profanity_checker import check_profanity

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
OUTPUT_FOLDER = 'outputs'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['OUTPUT_FOLDER'] = OUTPUT_FOLDER

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

@app.route('/rename', methods=['GET', 'POST'])
def rename():
    if request.method == 'POST':
        file = request.files['wordfile']
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file.save(filepath)

        try:
            new_name = rename_word_file(filepath)
            return f"Renamed file: {new_name}"
        except Exception as e:
            return str(e), 500

    return render_template('rename.html')

@app.route('/profanity', methods=['GET', 'POST'])
def profanity():
    if request.method == 'POST':
        file = request.files['file']
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file.save(filepath)

        try:
            results = check_profanity(filepath)
            return render_template('profanity_result.html', results=results)
        except Exception as e:
            return str(e), 500

    return render_template('profanity.html')

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
