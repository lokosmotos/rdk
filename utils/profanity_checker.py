import os
import pandas as pd
import re

# Profanity dictionary
PROFANITY_CATEGORIES = {
    "Mild": ["damn", "hell", "crap", "sucks", "piss", "pissed off"],
    "Moderate": ["ass", "asshole", "bastard", "bitch", "dick", "dickhead", "prick"],
    "Strong": ["fuck", "fucking", "motherfucker", "shit", "cunt", "cocksucker", "goddamn"],
    "Religious": ["jesus", "jesus christ", "god", "oh my god", "goddamn", "christ almighty", "holy", "for god's sake", "swear to god"]
}

def classify_profanity(word):
    word_lower = word.lower()
    for category, words in PROFANITY_CATEGORIES.items():
        for profane in words:
            if re.search(rf'\b{re.escape(profane)}\b', word_lower):
                return category, profane
    return None, None

def extract_text_from_file(filepath):
    ext = os.path.splitext(filepath)[1].lower()
    if ext == '.srt':
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.readlines(), 'srt'
    elif ext in ['.xlsx', '.xls']:
        df = pd.read_excel(filepath)
        return df, 'excel'
    else:
        raise ValueError("Unsupported file type")

def check_profanity(filepath):
    content, filetype = extract_text_from_file(filepath)
    results = []

    if filetype == 'srt':
        for i, line in enumerate(content):
            category, profane = classify_profanity(line)
            if category:
                results.append({"line": i+1, "text": line.strip(), "category": category, "word": profane})
    else:  # Excel
        for index, row in content.iterrows():
            for col in content.columns:
                cell = str(row[col])
                category, profane = classify_profanity(cell)
                if category:
                    results.append({"row": index+1, "column": col, "text": cell, "category": category, "word": profane})

    return {
        "results": results,
        "filetype": filetype,
        "original": content
    }

def clean_profanity(results, original_content, filetype, replacements):
    if filetype == 'srt':
        for r in results:
            original_line = original_content[r["line"] - 1]
            clean_line = re.sub(rf'\b{re.escape(r["word"])}\b', replacements[r["word"]], original_line, flags=re.IGNORECASE)
            original_content[r["line"] - 1] = clean_line
        return original_content

    else:
        for r in results:
            old_text = original_content.loc[r["row"] - 1, r["column"]]
            new_text = re.sub(rf'\b{re.escape(r["word"])}\b', replacements[r["word"]], str(old_text), flags=re.IGNORECASE)
            original_content.loc[r["row"] - 1, r["column"]] = new_text
        return original_content

def final_qc(content, filetype):
    dummy_path = 'qc_temp.srt' if filetype == 'srt' else 'qc_temp.xlsx'
    if filetype == 'srt':
        with open(dummy_path, 'w', encoding='utf-8') as f:
            f.writelines(content)
    else:
        content.to_excel(dummy_path, index=False)

    result = check_profanity(dummy_path)
    os.remove(dummy_path)
    return result["results"]
