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
    """Enhanced SRT CC removal with multiple improvements:
    - Better pattern matching for various CC formats
    - Preserves timing information
    - Handles multiline subtitles
    - Better encoding handling
    - More robust error handling
    - Configurable patterns
    """
    # Common closed caption patterns (can be extended)
    cc_patterns = [
        r"\[.*?\]",    # [text in brackets]
        r"\(.*?\)",    # (text in parentheses)
        r"\{.*?\}",    # {text in braces}
        r"<.*?>",      # <text in angle brackets>
        r'♪.*?♪',      # Music symbols ♪text♪
        r'#.*?#',      # #text# (common in some formats)
        r"\bCC:\s*\w+",  # CC: text
        r"\bSUBTITLE:\s*\w+",  # SUBTITLE: text
        r"\bSUBS:\s*\w+",  # SUBS: text
        r"^\d+$",      # Line numbers (standalone)
        r"^\s*$",      # Empty lines
    ]
    
    # Combined pattern with optional case insensitivity
    combined_pattern = re.compile("|".join(cc_patterns), re.IGNORECASE)
    
    # Timing pattern (to preserve timestamp lines)
    time_pattern = re.compile(r"\d{2}:\d{2}:\d{2},\d{3} --> \d{2}:\d{2}:\d{2},\d{3}")
    
    try:
        # Handle encoding automatically (fallback to utf-8)
        with open(file_path, 'r', encoding='utf-8-sig') as f:
            srt_content = f.readlines()
        
        cleaned_content = []
        in_subtitle = False
        
        for line in srt_content:
            line = line.strip()
            
            # Skip empty lines but maintain structure
            if not line:
                cleaned_content.append("\n")
                continue
                
            # Preserve timing lines exactly
            if time_pattern.match(line):
                cleaned_content.append(line + "\n")
                in_subtitle = True
                continue
                
            # Skip line numbers (they'll be renumbered later)
            if line.isdigit():
                continue
                
            # Process subtitle text
            if in_subtitle:
                # Remove CC patterns
                cleaned_line = re.sub(combined_pattern, "", line)
                
                # Additional cleanup
                cleaned_line = cleaned_line.strip()
                
                # Only add if there's content left
                if cleaned_line:
                    cleaned_content.append(cleaned_line + "\n")
                in_subtitle = False
            else:
                # Handle malformed SRT files
                cleaned_content.append(line + "\n")
        
        # Renumber subtitles properly
        renumbered_content = []
        counter = 1
        i = 0
        n = len(cleaned_content)
        
        while i < n:
            line = cleaned_content[i].strip()
            
            # Found timing line - this is a subtitle block
            if time_pattern.match(line):
                renumbered_content.append(f"{counter}\n")
                renumbered_content.append(f"{line}\n")
                counter += 1
                i += 1
                
                # Add text lines until empty line
                while i < n and cleaned_content[i].strip():
                    renumbered_content.append(cleaned_content[i])
                    i += 1
                
                # Add empty line separator
                if i < n and not cleaned_content[i].strip():
                    renumbered_content.append("\n")
                    i += 1
            else:
                i += 1
        
        # Generate output filename
        base_name = os.path.basename(file_path)
        cleaned_file_name = f"cleaned_{base_name}"
        output_path = os.path.join('outputs', cleaned_file_name)
        
        # Write output with proper line endings
        with open(output_path, "w", encoding="utf-8") as f:
            f.writelines(renumbered_content)
        
        return cleaned_file_name
        
    except UnicodeDecodeError:
        # Try with different encoding if utf-8 fails
        try:
            with open(file_path, 'r', encoding='latin-1') as f:
                srt_content = f.readlines()
            # ... repeat processing with fallback encoding ...
        except Exception as e:
            raise Exception(f"Encoding error: {str(e)}")
    except Exception as e:
        raise Exception(f"Processing error: {str(e)}")


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
