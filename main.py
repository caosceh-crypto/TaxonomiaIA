# ================================================
# main.py
# Plataforma de Taxonomía con IA (Gemini + MongoDB)
# Versión FINAL corregida
# ================================================

from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from typing import Optional
from pymongo import MongoClient
from dotenv import load_dotenv
import shutil, os, uuid, asyncio, json
import google.generativeai as genai

# -------------------------------
# CONFIGURACIÓN INICIAL
# -------------------------------
app = FastAPI(title="Plataforma Taxonómica IA (Gemini + Atlas)", version="3.3")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# -------------------------------
# VARIABLES DE ENTORNO
# -------------------------------
load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
DATABASE_NAME = os.getenv("DATABASE_NAME", "taxonomiaIA")

if not MONGO_URI:
    raise Exception("⚠️ No se encontró MONGO_URI en el archivo .env")

# Conexión a MongoDB
try:
    client = MongoClient(MONGO_URI)
    db = client["taxonomiaIA"]
    samples = db["samples"]
    print("✅ Conectado correctamente a MongoDB Atlas")
except Exception as e:
    print("❌ Error conectando a MongoDB Atlas:", e)
    raise e

# Configurar Gemini
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

# -------------------------------
# FRONTEND (static)
# -------------------------------
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def serve_index():
    index_path = os.path.join("static", "index.html")
    if not os.path.exists(index_path):
        raise HTTPException(status_code=404, detail="index.html no encontrado")
    return FileResponse(index_path)

# -------------------------------
# FUNCIÓN IA (Gemini)
# -------------------------------
async def classify_microorganism(genome_text: str, image_path: Optional[str] = None) -> dict:
    model = genai.GenerativeModel("gemini-2.5-flash")

    prompt = f"""
    Eres un microbiólogo experto en taxonomía.
    Analiza el siguiente genoma y proporciona:
    - Nombre científico probable
    - Nivel de confianza (0 a 1)
    - Evidencia basada en marcadores genómicos
    - Comentarios morfológicos si hay imagen

    Genoma (inicio): {genome_text[:2000]}...
    """

    if image_path:
        prompt += f"\nTambién analiza la imagen en {image_path}."

    try:
        response = model.generate_content(prompt)
        text = response.text.strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {
                "classification": text,
                "confidence": 0.9,
                "evidence": "Análisis textual (respuesta no estructurada)"
            }

    except Exception as e:
        return {"classification": "Unknown", "confidence": 0.0, "error": str(e)}

# -------------------------------
# PROCESAMIENTO DE MUESTRAS
# -------------------------------
async def process_sample(sample_id: str):
    sample = samples.find_one({"sample_id": sample_id})
    if not sample:
        print("❌ Sample no encontrado:", sample_id)
        return

    try:
        genome_files = [f for f in os.listdir(UPLOAD_DIR) if f.startswith(f"{sample_id}_genome")]
        image_files = [f for f in os.listdir(UPLOAD_DIR) if f.startswith(f"{sample_id}_image")]

        if not genome_files:
            raise Exception("Archivo de genoma no encontrado")

        genome_path = os.path.join(UPLOAD_DIR, genome_files[0])

        with open(genome_path, "r", encoding="utf-8", errors="ignore") as f:
            genome_text = f.read()

        image_path = os.path.join(UPLOAD_DIR, image_files[0]) if image_files else None

        print(f"🔬 Procesando muestra {sample_id}...")
        result = await classify_microorganism(genome_text, image_path)

        samples.update_one(
            {"sample_id": sample_id},
            {"$set": {"result": result, "status": "completed"}}
        )

        print("✅ Resultado almacenado para", sample_id)

    except Exception as e:
        samples.update_one(
            {"sample_id": sample_id},
            {"$set": {"status": "error", "result": {"error": str(e)}}}
        )
        print("❌ Error procesando muestra:", e)

def process_sample_sync(sample_id: str):
    asyncio.run(process_sample(sample_id))

# -------------------------------
# ENDPOINTS PRINCIPALES
# -------------------------------

@app.post("/api/samples")
async def create_sample(qr_code: str = Form(...)):
    sample_id = str(uuid.uuid4())
    samples.insert_one({
        "sample_id": sample_id,
        "qr_code": qr_code,
        "status": "pending_data",
        "result": None
    })
    return {"sample_id": sample_id, "status": "pending_data"}


@app.post("/api/samples/{sample_id}/upload")
async def upload_sample_data(
    sample_id: str,
    background_tasks: BackgroundTasks,
    genome_file: UploadFile = File(...),
    image_file: Optional[UploadFile] = None
):
    sample = samples.find_one({"sample_id": sample_id})
    if not sample:
        raise HTTPException(status_code=404, detail="Sample ID not found")

    genome_path = os.path.join(UPLOAD_DIR, f"{sample_id}_genome_{genome_file.filename}")
    with open(genome_path, "wb") as buffer:
        shutil.copyfileobj(genome_file.file, buffer)

    if image_file:
        image_path = os.path.join(UPLOAD_DIR, f"{sample_id}_image_{image_file.filename}")
        with open(image_path, "wb") as buffer:
            shutil.copyfileobj(image_file.file, buffer)

    samples.update_one({"sample_id": sample_id}, {"$set": {"status": "processing"}})
    background_tasks.add_task(process_sample_sync, sample_id)

    return {"message": f"Archivos recibidos. Procesando {sample_id}..."}


@app.get("/api/samples/{sample_id}/result")
async def get_sample_result(sample_id: str):
    sample = samples.find_one({"sample_id": sample_id}, {"_id": 0})
    if not sample:
        raise HTTPException(status_code=404, detail="Sample not found")

    if sample["status"] != "completed":
        return {"status": sample["status"], "message": "Análisis aún en progreso"}

    return sample["result"]


@app.put("/api/samples/{sample_id}/correction")
async def correct_sample(sample_id: str, corrected_taxonomy: str = Form(...)):
    sample = samples.find_one({"sample_id": sample_id})
    if not sample:
        raise HTTPException(status_code=404, detail="Sample not found")

    samples.update_one(
        {"sample_id": sample_id},
        {"$set": {"correction": corrected_taxonomy, "status": "corrected"}}
    )

    return {"message": f"Corrección almacenada para {sample_id}"}


@app.get("/api/samples")
async def list_samples():
    data = list(samples.find({}, {"_id": 0}))
    return {"count": len(data), "samples": data}

# -------------------------------
# ENDPOINTS DE RESULTADOS
# -------------------------------
@app.get("/api/results")
async def list_results():
    return list(samples.find({"status": "completed"}, {"_id": 0, "sample_id": 1, "result": 1}))

@app.get("/api/results/{sample_id}")
async def get_result_by_id(sample_id: str):
    sample = samples.find_one({"sample_id": sample_id}, {"_id": 0})
    if not sample:
        raise HTTPException(status_code=404, detail="Resultado no encontrado")

    return sample

# -------------------------------
# CHAT IA 
# -------------------------------
@app.post("/api/chat/{sample_id}")
async def chat_with_ai(sample_id: str, question: str = Form(...)):
    """
    Chat usando FormData (compatible con tu frontend).
    """

    sample = samples.find_one({"sample_id": sample_id})
    if not sample:
        raise HTTPException(status_code=404, detail="Sample not found")

    if not sample.get("result"):
        raise HTTPException(status_code=400, detail="La muestra no tiene resultado aún")

    context = json.dumps(sample["result"], ensure_ascii=False)
    model = genai.GenerativeModel("gemini-2.5-flash")

    prompt = f"""
    Eres un microbiólogo experto en taxonomía.
    Resultado de la muestra {sample_id}:

    {context}

    Pregunta del usuario:
    "{question}"

    Responde de forma clara, científica y útil.
    """

    try:
        response = model.generate_content(prompt)
        return {"answer": response.text.strip()}

    except Exception as e:
        return {"error": str(e)}