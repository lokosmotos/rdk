import pandas as pd
from langdetect import detect

def convert_to_srt(excel_path, output_folder):
    try:
        df = pd.read_excel(excel_path)
        srt_content = []
        
        for index, row in df.iterrows():
            srt_content.append(f"{index+1}\n")
            srt_content.append(f"{row['start_time']} --> {row['end_time']}\n")
            srt_content.append(f"{row['text']}\n\n")
        
        output_path = f"{output_folder}/output.srt"
        with open(output_path, 'w', encoding='utf-8') as f:
            f.writelines(srt_content)
            
        return output_path
    except Exception as e:
        raise Exception(f"Conversion error: {str(e)}")
