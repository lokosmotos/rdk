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
