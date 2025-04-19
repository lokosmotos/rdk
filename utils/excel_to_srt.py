import pandas as pd
import os
import langdetect

def convert_to_srt(filepath, output_folder):
    df = pd.read_excel(filepath)

    if df.shape[1] < 2:
        raise ValueError("Excel must have at least 2 columns: start time and text.")

    # Detect language from first few lines
    sample_text = ' '.join(df.iloc[:5, 1].astype(str))
    try:
        language = langdetect.detect(sample_text)
    except:
        language = 'unknown'

    srt_lines = []
    for i, row in df.iterrows():
        start = row[0]
        text = row[1]
        end = df.iloc[i+1, 0] if i + 1 < len(df) else "00:00:10,000"  # default end time if missing
        srt_lines.append(f"{i+1}\n{start} --> {end}\n{text}\n")

    output_filename = os.path.splitext(os.path.basename(filepath))[0] + f"_{language}.srt"
    output_path = os.path.join(output_folder, output_filename)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write('\n'.join(srt_lines))

    return output_path
