from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os
import shutil
from fastapi import UploadFile, File, HTTPException

from app.config import UPLOAD_DIR
from app.document_processor import is_supported, process_file
from app.embeddings import embed_texts
from app.vector_store import get_vector_store
from pydantic import BaseModel
from app.rag import ask
from fastapi.staticfiles import StaticFiles
from typing import Optional, List

app = FastAPI(title="Kendi Dokümanların ile Sohbet Et")

app.mount("/static", StaticFiles(directory="app/static"), name="static")

class ChatRequest(BaseModel):
    question: str
    sources: Optional[List[str]] = None
@app.get("/")
def read_root():
    return FileResponse("app/static/index.html")
@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    if not is_supported(file.filename):
        raise HTTPException(status_code=400, detail="Desteklenmeyen dosya formatı.")

    file_path = os.path.join(UPLOAD_DIR, file.filename)

    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    chunks = process_file(file_path)

    if not chunks:
        raise HTTPException(status_code=400, detail="Dosyadan metin çıkarılamadı.")

    texts = [c.text for c in chunks]
    embeddings = embed_texts(texts)

    store = get_vector_store()
    store.add_chunks(chunks, embeddings)

    return {
        "filename": file.filename,
        "chunk_count": len(chunks),
        "message": "Doküman başarıyla işlendi ve indekslendi.",
    }

@app.post("/chat")
def chat(request: ChatRequest):
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Soru boş olamaz.")

    result = ask(request.question, sources=request.sources)

    return {
        "answer": result["answer"],
        "sources": result["sources"],
    }

@app.get("/files")
def list_files():
    store = get_vector_store()
    return {"files": store.list_sources()}