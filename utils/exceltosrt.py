import os
import pandas as pd

def convert_to_srt(filepath, language, output_folder):
    df = pd.read_excel(filepath)
    
    language_map = {
        'ov': 'OV DIALOGUES',
        'spanish': 'SPANISH SUBTITLES',
        'english': 'ENGLISH SUBTITLES'
    }

    col = language_map.get(language)
    if col not in df.columns:
        raise ValueError(f"Column '{col}' not found in file.")

    lines = df[col].fillna('').tolist()
    srt_filename = f"{os.path.splitext(os.path.basename(filepath))[0]}_{language}.srt"
    srt_path = os.path.join(output_folder, srt_filename)

    with open(srt_path, 'w', encoding='utf-8') as f:
        for i, line in enumerate(lines, start=1):
            start_sec = i * 3
            end_sec = start_sec + 2
            f.write(f"{i}\n")
            f.write(f"00:00:{start_sec:02},000 --> 00:00:{end_sec:02},000\n")
            f.write(f"{line.strip()}\n\n")

    return srt_path
