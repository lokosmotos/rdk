import pandas as pd

BAD_WORDS = {'badword1', 'badword2', 'damn', 'hell'}  # Add more words

def check_profanity(filepath):
    ext = os.path.splitext(filepath)[1]
    results = []

    if ext in ['.xlsx', '.xls']:
        df = pd.read_excel(filepath)
        for col in df.columns:
            for i, text in enumerate(df[col].astype(str)):
                if any(word in text.lower() for word in BAD_WORDS):
                    results.append((col, i+2, text))  # +2 for Excel row numbering
    elif ext == '.srt':
        with open(filepath, encoding='utf-8') as f:
            lines = f.readlines()
            for i, line in enumerate(lines):
                if any(word in line.lower() for word in BAD_WORDS):
                    results.append(('line', i+1, line.strip()))
    else:
        return ["Unsupported file format."]

    return results if results else ["No profanity found."]
