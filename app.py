import os
import base64
import tempfile
import re
import fitz  # PyMuPDF
from flask import Flask, request, jsonify
from groq import Groq

app = Flask(__name__)

# Configuración de Groq
GROQ_API_KEY = os.environ.get('GROQ_API_KEY')
client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

def extraer_texto_pdf(contenido_bytes):
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
            tmp.write(contenido_bytes)
            temp_path = tmp.name
        
        doc = fitz.open(temp_path)
        texto = "".join([page.get_text() for page in doc])
        doc.close()
        
        texto = re.sub(r'\s+', ' ', texto).strip()
        return texto[:5000]
    except Exception as e:
        return f"Error PDF: {str(e)}"
    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)

def extraer_texto_xml(contenido_bytes):
    try:
        texto = contenido_bytes.decode('utf-8')
    except:
        texto = contenido_bytes.decode('latin-1')
    return re.sub(r'\s+', ' ', texto)[:5000]

@app.route('/auditar', methods=['POST'])
def auditar():
    try:
        data = request.get_json()
        
        # Power Automate enviará el contenido en Base64
        pdf_base64 = data.get('pdf_base64')
        xml_base64 = data.get('xml_base64')
        pdf_nombre = data.get('pdf_nombre', 'factura.pdf')
        xml_nombre = data.get('xml_nombre', 'factura.xml')

        # Decodificar
        pdf_bytes = base64.b64decode(pdf_base64)
        xml_bytes = base64.b64decode(xml_base64)

        # Extraer textos
        pdf_texto = extraer_texto_pdf(pdf_bytes)
        xml_texto = extraer_texto_xml(xml_bytes)

        # Tu lógica de IA (simplificada para la respuesta)
        prompt = f"""
        Compara PDF vs XML.
        PDF: {pdf_texto[:2000]}
        XML: {xml_texto[:1500]}
        Responde EXACTAMENTE:
        ===ANALISIS===
        [campos que coinciden]
        ===DISCREPANCIAS===
        [true o false]
        """

        completion = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.3-70b-versatile",
            temperature=0.1
        )

        respuesta = completion.choices[0].message.content
        
        # Procesar respuesta para devolver JSON limpio a Power Automate
        tiene_discrepancias = "true" in respuesta.lower().split("===discrepancias===")[-1]
        analisis = respuesta.split("===DISCREPANCIAS===")[0].replace("===ANALISIS===", "").strip()

        return jsonify({
            "coincidencia": "OK" if not tiene_discrepancias else "DISCREPANCIA",
            "observacion": analisis,
            "ruc_xml": re.search(r'<cbc:ID>(\d{11})</cbc:ID>', xml_texto).group(1) if re.search(r'<cbc:ID>(\d{11})</cbc:ID>', xml_texto) else ""
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
