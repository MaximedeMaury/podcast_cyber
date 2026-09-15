from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import os

app = FastAPI()

# Création du dossier pour stocker les podcasts
os.makedirs("public/audio", exist_ok=True)
# On rend le dossier accessible sur le web
app.mount("/audio", StaticFiles(directory="public/audio"), name="audio")


@app.post("/api/upload")
async def upload_episode(
        title: str = Form(...),
        description: str = Form(...),
        media_file: UploadFile = File(...)
):
    # Sauvegarde du fichier MP3 reçu d'Antigravity
    file_location = f"public/audio/{media_file.filename}"
    with open(file_location, "wb+") as file_object:
        file_object.write(media_file.file.read())

    print(f"Nouvel épisode reçu : {title}")
    return {"status": "success", "message": "Épisode publié !"}


@app.get("/", response_class=HTMLResponse)
async def read_root():
    # Affiche la belle interface visuelle
    with open("index.html", "r", encoding="utf-8") as f:
        return f.read()