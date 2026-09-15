import os
from datetime import datetime
from fastapi import FastAPI, File, UploadFile, HTTPException, Depends
from fastapi.security import APIKeyHeader
from fastapi.responses import FileResponse
from supabase import create_client, Client

app = FastAPI()

# 1. Récupération des clés
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
API_KEY = os.getenv("SITE_API_KEY")

if SUPABASE_URL and SUPABASE_KEY:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

header_scheme = APIKeyHeader(name="X-API-Key")

def verify_api_key(api_key: str = Depends(header_scheme)):
    if API_KEY and api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Clé API invalide")
    return api_key

# 2. Route pour RECEVOIR les nouveaux épisodes de l'agent
@app.post("/api/upload")
async def upload_episode(file: UploadFile = File(...), api_key: str = Depends(verify_api_key)):
    if not file.filename.endswith('.mp3'):
        raise HTTPException(status_code=400, detail="Seuls les MP3 sont acceptés")
    try:
        file_content = await file.read()
        supabase.storage.from_("podcasts-audio").upload(
            file=file_content,
            path=file.filename,
            file_options={"content-type": "audio/mpeg", "upsert": "true"}
        )
        return {"message": "Épisode sauvegardé sur Supabase"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# 3. Route pour LISTER les épisodes pour ton site web
@app.get("/api/episodes")
def liste_episodes():
    try:
        fichiers = supabase.storage.from_("podcasts-audio").list()
        episodes = []
        
        for fichier in fichiers:
            if fichier['name'].endswith('.mp3'):
                titre = fichier['name'].replace(".mp3", "").replace("_", " ").capitalize()
                date_obj = datetime.fromisoformat(fichier['created_at'].replace('Z', '+00:00'))
                date_fr = date_obj.strftime("%d/%m/%Y à %H:%M")
                url_publique = supabase.storage.from_("podcasts-audio").get_public_url(fichier['name'])
                
                episodes.append({
                    "titre": titre,
                    "date": date_fr,
                    "url": url_publique,
                    "timestamp": date_obj.timestamp()
                })
                
        episodes.sort(key=lambda x: x["timestamp"], reverse=True)
        return episodes
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# 4. Route pour AFFICHER la page d'accueil du site
@app.get("/")
def afficher_site():
    return FileResponse("index.html")
