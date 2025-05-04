from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_cors import CORS
import pytesseract
from PIL import Image, ImageFilter
import os
import re
import platform
import spacy
from reportlab.pdfgen import canvas
from threading import Thread

# Detect OS and set tesseract path only for Windows
if platform.system() == 'Windows':
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# Flask app setup
app = Flask(__name__)
CORS(app)

UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
nlp = spacy.load("en_core_web_sm")

# Ensure uploads folder exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Preprocess the image before OCR
def preprocess_image(image):
    image = image.convert('L')  # grayscale
    image = image.point(lambda p: 255 if p > 180 else 0)  # thresholding
    image = image.filter(ImageFilter.SHARPEN)  # sharpen text
    return image

# Extract medicine-like patterns
def extract_medicines(text):
    meds = []
    lines = text.split('\n')
    for line in lines:
        if re.search(r'\b(\d+(\.\d+)?)\s*(mg|ml|tablet|capsule|injection|syrup)\b', line, re.IGNORECASE):
            meds.append(line.strip())
    return meds

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_image():
    if 'image' not in request.files:
        return jsonify({'error': 'No image uploaded'}), 400
    file = request.files['image']
    if file.filename == '':
        return jsonify({'error': 'Empty filename'}), 400

    filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
    file.save(filepath)

    try:
        image = Image.open(filepath)
        processed_image = preprocess_image(image)
        text = pytesseract.image_to_string(processed_image, config='--psm 6 --oem 3')
        medicines = extract_medicines(text)
        return jsonify({'text': text.strip(), 'medicines': medicines})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# PDF generation function
def generate_pdf(text, filepath):
    c = canvas.Canvas(filepath)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, 800, "Prescription Extract")
    y = 770

    c.setFont("Helvetica", 12)
    for line in text.split('\n'):
        c.drawString(50, y, line)
        y -= 15
        if y < 50:
            c.showPage()
            y = 800
            c.setFont("Helvetica", 12)
    c.save()

@app.route('/download_pdf', methods=['POST'])
def download_pdf():
    data = request.get_json()
    text = data.get('text', '').strip()
    if not text:
        return jsonify({'error': 'No text provided for PDF'}), 400

    filename = 'prescription.pdf'
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)

    thread = Thread(target=generate_pdf, args=(text, filepath))
    thread.start()
    thread.join()  # Wait for PDF to finish writing

    return jsonify({'url': f'/uploads/{filename}'})

@app.route('/uploads/<filename>')
def serve_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    # Runs locally
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=True)
