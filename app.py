import os
from fastapi import FastAPI, File, UploadFile, HTTPException, Depends
from fastapi.security import APIKeyHeader
from supabase import create_client, Client

app = FastAPI()

# 1. Récupération des clés Supabase et du mot de passe du site
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
API_KEY = os.getenv("SITE_API_KEY")

# Connexion à Supabase
if SUPABASE_URL and SUPABASE_KEY:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# 2. Système de sécurité (Vérification de la clé)
header_scheme = APIKeyHeader(name="X-API-Key")

def verify_api_key(api_key: str = Depends(header_scheme)):
    if API_KEY and api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Clé API invalide")
    return api_key

# 3. La route qui reçoit le MP3 de l'agent et l'envoie sur Supabase
@app.post("/api/upload")
async def upload_episode(file: UploadFile = File(...), api_key: str = Depends(verify_api_key)):
    if not file.filename.endswith('.mp3'):
        raise HTTPException(status_code=400, detail="Seuls les fichiers MP3 sont acceptés")

    try:
        # On lit la musique envoyée par l'agent
        file_content = await file.read()
        
        # On l'envoie directement dans ton Bucket 'podcasts-audio' sur Supabase
        supabase.storage.from_("podcasts-audio").upload(
            file=file_content,
            path=file.filename,
            file_options={"content-type": "audio/mpeg", "upsert": "true"}
        )
        
        return {"message": f"Épisode {file.filename} sauvegardé pour l'éternité sur Supabase !"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur Supabase: {str(e)}")
