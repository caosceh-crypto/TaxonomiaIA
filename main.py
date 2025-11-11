# ================================================
# main.py
# Plataforma de Taxonomía con IA (Versión Gemini + MongoDB Atlas)
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
app = FastAPI(title="Plataforma Taxonómica IA (Gemini + Atlas)", version="3.2")

# Permitir CORS (para frontend)
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
# CARGAR VARIABLES DE ENTORNO
# -------------------------------
load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
DATABASE_NAME = os.getenv("DATABASE_NAME", "taxonomiaIA")

if not MONGO_URI:
    raise Exception("⚠️ No se encontró MONGO_URI en el archivo .env")

# Conexión a MongoDB Atlas
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
# SERVIR ARCHIVOS ESTÁTICOS (Frontend)
# -------------------------------
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def serve_index():
    index_path = os.path.join("static", "index.html")
    if not os.path.exists(index_path):
        raise HTTPException(status_code=404, detail="index.html no encontrado")
    return FileResponse(index_path)

# -------------------------------
# FUNCIÓN DE IA (Gemini)
# -------------------------------
async def classify_microorganism(genome_text: str, image_path: Optional[str] = None) -> dict:
    """
    Clasifica microorganismo usando Google Gemini.
    """
    model = genai.GenerativeModel("gemini-2.5-flash")

    prompt = f"""
    Eres un microbiólogo experto en taxonomía.
    Analiza el siguiente genoma y proporciona:
    - Nombre científico probable del microorganismo
    - Nivel de confianza (0 a 1)
    - Evidencia basada en marcadores genómicos
    - Comentarios morfológicos si hay imagen

    Genoma (parcial): {genome_text[:2000]}...
    """

    if image_path:
        prompt += f"\nTambién analiza la imagen en {image_path}."

    try:
        response = model.generate_content(prompt)
        text = response.text.strip()

        try:
            result = json.loads(text)
        except json.JSONDecodeError:
            result = {
                "classification": text,
                "confidence": 0.9,
                "evidence": "Análisis textual (sin formato JSON)"
            }

        return result

    except Exception as e:
        print("❌ Error con Gemini:", e)
        return {"classification": "Unknown", "confidence": 0.0, "error": str(e)}

# -------------------------------
# PROCESAMIENTO DE MUESTRAS
# -------------------------------
async def process_sample(sample_id: str):
    sample = samples.find_one({"sample_id": sample_id})
    if not sample:
        print(f"❌ Sample {sample_id} no encontrado")
        return

    try:
        genome_files = [f for f in os.listdir(UPLOAD_DIR) if f.startswith(f"{sample_id}_genome")]
        image_files = [f for f in os.listdir(UPLOAD_DIR) if f.startswith(f"{sample_id}_image")]

        if not genome_files:
            raise Exception("No se encontró archivo de genoma.")

        genome_path = os.path.join(UPLOAD_DIR, genome_files[0])
        with open(genome_path, "r", encoding="utf-8", errors="ignore") as f:
            genome_text = f.read()

        image_path = os.path.join(UPLOAD_DIR, image_files[0]) if image_files else None

        print(f"🔬 Analizando muestra {sample_id} con Gemini...")
        result = await classify_microorganism(genome_text, image_path)
        
        samples.update_one(
            {"sample_id": sample_id},
            {"$set": {"result": result, "status": "completed"}}
        )
        print(f"✅ Resultado almacenado para {sample_id}")

    except Exception as e:
        print(f"❌ Error procesando {sample_id}: {e}")
        samples.update_one(
            {"sample_id": sample_id},
            {"$set": {"status": "error", "result": {"error": str(e)}}}
        )

def process_sample_sync(sample_id: str):
    asyncio.run(process_sample(sample_id))

# -------------------------------
# ENDPOINTS PRINCIPALES
# -------------------------------
@app.post("/api/samples")
async def create_sample(qr_code: str = Form(...)):
    sample_id = str(uuid.uuid4())
    sample = {"sample_id": sample_id, "qr_code": qr_code, "status": "pending_data", "result": None}
    samples.insert_one(sample)
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

    try:
        genome_path = os.path.join(UPLOAD_DIR, f"{sample_id}_genome_{genome_file.filename}")
        with open(genome_path, "wb") as buffer:
            shutil.copyfileobj(genome_file.file, buffer)

        if image_file:
            image_path = os.path.join(UPLOAD_DIR, f"{sample_id}_image_{image_file.filename}")
            with open(image_path, "wb") as buffer:
                shutil.copyfileobj(image_file.file, buffer)

        samples.update_one({"sample_id": sample_id}, {"$set": {"status": "processing"}})
        background_tasks.add_task(process_sample_sync, sample_id)

        return {"message": f"Archivos recibidos para {sample_id}. Análisis iniciado."}

    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/api/samples/{sample_id}/result")
async def get_sample_result(sample_id: str):
    sample = samples.find_one({"sample_id": sample_id}, {"_id": 0})
    if not sample:
        raise HTTPException(status_code=404, detail="Sample not found")
    if sample["status"] != "completed":
        return {"status": sample["status"], "message": "Análisis aún en progreso."}
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

    return {"message": f"Corrección recibida y almacenada para {sample_id}."}

@app.get("/api/samples")
async def list_samples():
    all_samples = list(samples.find({}, {"_id": 0}))
    return {"count": len(all_samples), "samples": all_samples}

# -------------------------------
# NUEVOS ENDPOINTS DE RESULTADOS
# -------------------------------
@app.get("/api/results")
async def list_results():
    results = list(samples.find({"status": "completed"}, {"_id": 0, "sample_id": 1, "result": 1}))
    return results or []

@app.get("/api/results/{sample_id}")
async def get_result_by_id(sample_id: str):
    sample = samples.find_one({"sample_id": sample_id}, {"_id": 0, "sample_id": 1, "result": 1, "status": 1})
    if not sample:
        raise HTTPException(status_code=404, detail="Resultado no encontrado.")
    return sample
