from flask import Flask, render_template, request, jsonify, send_from_directory
import pytesseract
from PIL import Image, ImageEnhance, ImageFilter
import os
import spacy
import re
from reportlab.pdfgen import canvas
from threading import Thread
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Folder for uploads
UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Load spaCy model
nlp = spacy.load("en_core_web_sm")

# Ensure the uploads folder exists
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# Image preprocessing for better OCR
def preprocess_image(image):
    image = image.convert('L')  # Grayscale
    enhancer = ImageEnhance.Contrast(image)
    image = enhancer.enhance(2)  # Increase contrast
    image = image.point(lambda p: p > 150 and 255)  # Binarization
    image = image.filter(ImageFilter.SHARPEN)
    return image

# Extract medicine-like lines from OCR text
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
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['image']
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
    file.save(filepath)

    image = Image.open(filepath)
    processed_image = preprocess_image(image)
    text = pytesseract.image_to_string(processed_image, config='--psm 6 --oem 3')
    meds = extract_medicines(text)

    return jsonify({'text': text, 'medicines': meds})

# Generate PDF from extracted text
def generate_pdf(text, filepath):
    c = canvas.Canvas(filepath)
    c.setFont("Helvetica", 12)
    y = 800
    c.drawString(50, y, "Prescription")
    y -= 20
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, y, "Extracted Text:")
    y -= 25

    c.setFont("Helvetica", 12)
    for line in text.split('\n'):
        c.drawString(50, y, line)
        y -= 15
        if y < 50:
            c.showPage()
            c.setFont("Helvetica", 12)
            y = 800
    c.save()

@app.route('/download_pdf', methods=['POST'])
def download_pdf():
    data = request.get_json()
    text = data['text']
    filename = 'prescription.pdf'
    filepath = os.path.join(UPLOAD_FOLDER, filename)

    # PDF generation in a separate thread
    Thread(target=generate_pdf, args=(text, filepath)).start()

    return jsonify({'url': f'/uploads/{filename}'})

@app.route('/uploads/<filename>')
def serve_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    # For local and Render compatibility
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=True)
