import os
from flask import Flask, render_template, request, send_from_directory
from utils.excel_to_srt import convert_to_srt
from utils.profanity_checker import check_profanity
from werkzeug.utils import secure_filename

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

# === Tool 1: Excel to SRT ===
@app.route('/srt', methods=['GET', 'POST'])
def excel_to_srt():
    if request.method == 'POST':
        file = request.files['excel']
        language = request.form['language']

        if file and file.filename.endswith(('.xlsx', '.xls')):
            filename = secure_filename(file.filename)
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            file.save(filepath)

            srt_path = convert_to_srt(filepath, language, OUTPUT_FOLDER)
            return send_from_directory(OUTPUT_FOLDER, os.path.basename(srt_path), as_attachment=True)
        else:
            return "Invalid Excel file.", 400

    return render_template('srt_converter.html')


# === Tool 2: Profanity Checker ===
@app.route('/profanity', methods=['GET', 'POST'])
def profanity_tool():
    if request.method == 'POST':
        file = request.files['file']

        if file:
            filename = secure_filename(file.filename)
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            file.save(filepath)

            results = check_profanity(filepath)
            return render_template('profanity_result.html', results=results, filename=filename)
        else:
            return "No file uploaded.", 400

    return render_template('profanity_checker.html')


if __name__ == "__main__":
    app.run(debug=True)
from utils.word_renamer import rename_doc_file

@app.route('/rename', methods=['GET', 'POST'])
def rename_word_file():
    if request.method == 'POST':
        file = request.files['word']
        if file and file.filename.endswith('.docx'):
            filename = secure_filename(file.filename)
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            file.save(filepath)

            renamed_filename = rename_doc_file(filepath, UPLOAD_FOLDER)
            if renamed_filename:
                return f"File renamed to: {renamed_filename}"
            else:
                return "Could not extract header text for renaming.", 400
        else:
            return "Please upload a valid .docx file.", 400

    return render_template('word_renamer.html')
