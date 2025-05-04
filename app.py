from flask import Flask, render_template, request, jsonify, send_from_directory
import pytesseract
from PIL import Image, ImageEnhance, ImageFilter
import os
import spacy
import re
from reportlab.pdfgen import canvas
from threading import Thread
from flask_cors import CORS

# Tesseract executable path (make sure this path is correct on your system)
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'  # Update path if needed

app = Flask(__name__)
CORS(app)

UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
nlp = spacy.load("en_core_web_sm")

# Ensure the uploads folder exists
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def preprocess_image(image):
    """Preprocess image before OCR."""
    image = image.convert('L')  # Convert to grayscale
    image = image.point(lambda p: p > 200 and 255)  # Binarize image
    image = image.filter(ImageFilter.SHARPEN)  # Enhance sharpness
    return image

def extract_medicines(text):
    """Extract possible medicines from the OCR text."""
    meds = []
    lines = text.split('\n')
    for line in lines:
        if re.search(r'\b(\d+(\.\d+)?)\s*(mg|ml|tablet|capsule|injection|syrup)\b', line, re.IGNORECASE):
            meds.append(line.strip())
    return meds

@app.route('/')
def index():
    """Render the main page."""
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_image():
    """Handle image upload and OCR processing."""
    if 'image' not in request.files:
        print("❌ No image uploaded")
        return jsonify({'error': 'No image uploaded'}), 400
    
    file = request.files['image']
    
    if file.filename == '':
        print("❌ Empty filename")
        return jsonify({'error': 'Empty filename'}), 400

    filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
    
    try:
        print(f"Saving file to {filepath}")
        file.save(filepath)

        # Open the image and preprocess it
        image = Image.open(filepath)
        processed_image = preprocess_image(image)
        
        # Extract text using Tesseract OCR
        text = pytesseract.image_to_string(processed_image, config='--psm 6 --oem 3')
        print(f"Extracted Text: {text}")

        # Extract medicines from the OCR text
        medicines = extract_medicines(text)
        print(f"Detected Medicines: {medicines}")

        return jsonify({'text': text.strip(), 'medicines': medicines})

    except Exception as e:
        print(f"❌ Error processing image: {str(e)}")
        return jsonify({'error': f'Error processing image: {str(e)}'}), 500

def generate_pdf(text, filepath):
    """Generate a PDF with the extracted text."""
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
    """Generate and download a PDF with the extracted text."""
    data = request.get_json()
    text = data['text']
    filename = 'prescription.pdf'
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    
    try:
        # Start PDF generation in a separate thread
        Thread(target=generate_pdf, args=(text, filepath)).start()
        return jsonify({'url': f'/uploads/{filename}'})
    except Exception as e:
        print(f"❌ Error generating PDF: {str(e)}")
        return jsonify({'error': f'Error generating PDF: {str(e)}'}), 500

@app.route('/uploads/<filename>')
def serve_file(filename):
    """Serve the generated PDF file."""
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    # Remove duplicate debug parameter
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
