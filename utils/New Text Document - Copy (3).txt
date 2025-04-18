# utils/word_renamer.py

from docx import Document

def rename_word_file(file_path):
    doc = Document(file_path)
    # Assuming the header text is in the first paragraph
    header = doc.paragraphs[0].text
    # Get the directory and filename
    dir_name, old_filename = os.path.split(file_path)
    new_filename = f"{header}.docx"
    new_path = os.path.join(dir_name, new_filename)
    os.rename(file_path, new_path)
    return new_path
