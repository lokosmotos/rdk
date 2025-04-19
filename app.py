import os
import re
from flask import Flask, render_template, request, send_from_directory
from utils.excel_to_srt import convert_to_srt
from utils.word_renamer import rename_word_file
from utils.profanity_checker import check_profanity, clean_profanity, final_qc

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
OUTPUT_FOLDER = 'outputs'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['OUTPUT_FOLDER'] = OUTPUT_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# ===== CC Removal =====
@app.route('/remove_cc', methods=['GET', 'POST'])
def remove_cc_route():
    if request.method == 'POST':
        file = request.files['srtfile']
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file.save(filepath)

        try:
            cleaned_file = remove_cc_from_srt(filepath)
            return send_from_directory(app.config['OUTPUT_FOLDER'], cleaned_file, as_attachment=True)
        except Exception as e:
            return str(e), 500

    return render_template('remove_cc.html')


def remove_cc_from_srt(file_path):
    # Open the SRT file
    with open(file_path, 'r', encoding="utf-8") as f:
        srt_content = f.readlines()

    # Define the CC pattern (this may vary depending on your SRT files)
    cc_pattern = re.compile(r"\[.*?\]|\(.*?\)|\".*?\"")  # Text inside [], (), or ""

    # Remove CC and create cleaned content
    cleaned_content = []
    for line in srt_content:
        cleaned_line = re.sub(cc_pattern, "", line)
        cleaned_content.append(cleaned_line)

    # Save cleaned SRT to the output folder
    cleaned_file_name = f"cleaned_{os.path.basename(file_path)}"
    output_path = os.path.join('outputs', cleaned_file_name)

    with open(output_path, "w", encoding="utf-8") as f:
        f.writelines(cleaned_content)

    return cleaned_file_name


# ===== Excel to SRT =====
@app.route('/convert', methods=['GET', 'POST'])
def convert_route():
    if request.method == 'POST':
        uploaded_file = request.files['excel']

        if not uploaded_file.filename.endswith(('.xlsx', '.xls')):
            return "Invalid file type. Please upload an Excel file.", 400

        filepath = os.path.join(app.config['UPLOAD_FOLDER'], uploaded_file.filename)
        uploaded_file.save(filepath)

        try:
            srt_path = convert_to_srt(filepath, output_folder=app.config['OUTPUT_FOLDER'])
        except Exception as e:
            return str(e), 500

        return send_from_directory(app.config['OUTPUT_FOLDER'], os.path.basename(srt_path), as_attachment=True)

    return render_template('convert.html')

# ===== Word File Renamer =====
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

# ===== Profanity Checker =====
@app.route('/profanity', methods=['GET', 'POST'])
def profanity():
    if request.method == 'POST':
        file = request.files['file']
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file.save(filepath)

        try:
            scan_result = check_profanity(filepath)
            if not scan_result["results"]:
                return "✅ No profanities detected."

            return render_template('profanity_review.html', results=scan_result["results"],
                                   filetype=scan_result["filetype"], filename=file.filename)

        except Exception as e:
            return str(e), 500

    return render_template('profanity.html')

@app.route('/profanity/clean', methods=['POST'])
def profanity_clean():
    filename = request.form.get('filename')
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    scan_result = check_profanity(filepath)
    replacements = {}

    for word in request.form:
        if word.startswith("replace_"):
            profane_word = word.replace("replace_", "")
            replacements[profane_word] = request.form[word]

    cleaned = clean_profanity(scan_result["results"], scan_result["original"],
                               scan_result["filetype"], replacements)

    # Final QC
    remaining = final_qc(cleaned, scan_result["filetype"])

    # Save output
    output_filename = f"cleaned_{filename}"
    output_path = os.path.join(app.config['OUTPUT_FOLDER'], output_filename)

    if scan_result["filetype"] == "srt":
        with open(output_path, "w", encoding="utf-8") as f:
            f.writelines(cleaned)
    else:
        cleaned.to_excel(output_path, index=False)

    if remaining:
        return render_template("qc_failed.html", remaining=remaining)
    else:
        return send_from_directory(app.config["OUTPUT_FOLDER"], output_filename, as_attachment=True)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
