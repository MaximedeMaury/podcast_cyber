import os
import re
import logging
from datetime import datetime, timezone
from typing import Optional
from xml.sax.saxutils import escape

from fastapi import FastAPI, File, UploadFile, HTTPException, Depends, Query
from fastapi.security import APIKeyHeader
from fastapi.responses import FileResponse, Response
from supabase import create_client, Client

# --- Config générale ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("podcast_cyber")

app = FastAPI(title="Cyber & IA Hebdo")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
API_KEY = os.getenv("SITE_API_KEY")
SITE_URL = os.getenv("SITE_URL", "http://localhost:8000")
BUCKET_NAME = "podcasts-audio"

# --- Client Supabase (ne plante plus si les variables sont absentes) ---
supabase: Optional[Client] = None
if SUPABASE_URL and SUPABASE_KEY:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
else:
    logger.warning("SUPABASE_URL / SUPABASE_KEY manquants : les routes /api/* renverront une erreur 503.")

header_scheme = APIKeyHeader(name="X-API-Key")


def verify_api_key(api_key: str = Depends(header_scheme)):
    if not API_KEY:
        raise HTTPException(status_code=500, detail="SITE_API_KEY n'est pas configurée côté serveur")
    if api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Clé API invalide")
    return api_key


def get_supabase() -> Client:
    if supabase is None:
        raise HTTPException(status_code=503, detail="Stockage indisponible (Supabase non configuré)")
    return supabase


# Nom de fichier strict : lettres, chiffres, points, tirets, underscores, extension .mp3
SAFE_FILENAME = re.compile(r"^[A-Za-z0-9._-]+\.mp3$")


def clean_title(filename: str) -> str:
    return filename[:-4].replace("_", " ").replace("-", " ").strip().capitalize()


# --- 1. Upload d'un épisode (par l'agent) ---
@app.post("/api/upload")
async def upload_episode(file: UploadFile = File(...), api_key: str = Depends(verify_api_key)):
    filename = os.path.basename(file.filename or "")
    if not SAFE_FILENAME.match(filename):
        raise HTTPException(
            status_code=400,
            detail="Nom de fichier invalide : seuls les .mp3 (lettres, chiffres, '_', '-') sont acceptés",
        )

    client = get_supabase()
    try:
        file_content = await file.read()
        if not file_content:
            raise HTTPException(status_code=400, detail="Fichier vide")

        client.storage.from_(BUCKET_NAME).upload(
            file=file_content,
            path=filename,
            file_options={"content-type": "audio/mpeg", "upsert": "true"},
        )
        logger.info(f"Épisode uploadé : {filename} ({len(file_content)} octets)")
        return {"message": "Épisode sauvegardé sur Supabase", "filename": filename}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Échec de l'upload")
        raise HTTPException(status_code=500, detail=str(e))


def _list_episodes():
    client = get_supabase()
    fichiers = client.storage.from_(BUCKET_NAME).list()
    episodes = []
    for fichier in fichiers:
        if not fichier["name"].endswith(".mp3"):
            continue
        try:
            date_obj = datetime.fromisoformat(fichier["created_at"].replace("Z", "+00:00"))
        except (KeyError, ValueError, TypeError):
            date_obj = datetime.now(timezone.utc)

        episodes.append(
            {
                "titre": clean_title(fichier["name"]),
                "date": date_obj.strftime("%d/%m/%Y à %H:%M"),
                "date_iso": date_obj.isoformat(),
                "url": client.storage.from_(BUCKET_NAME).get_public_url(fichier["name"]),
                "timestamp": date_obj.timestamp(),
            }
        )
    episodes.sort(key=lambda x: x["timestamp"], reverse=True)
    return episodes


# --- 2. Liste des épisodes pour le site (avec recherche optionnelle) ---
@app.get("/api/episodes")
def liste_episodes(q: Optional[str] = Query(default=None, description="Filtre par titre")):
    try:
        episodes = _list_episodes()
        if q:
            q_lower = q.lower()
            episodes = [e for e in episodes if q_lower in e["titre"].lower()]
        return episodes
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Échec de la récupération des épisodes")
        raise HTTPException(status_code=500, detail=str(e))


# --- 3. Flux RSS : indispensable pour Apple Podcasts, Spotify, etc. ---
@app.get("/rss.xml")
def rss_feed():
    try:
        episodes = _list_episodes()
    except HTTPException:
        episodes = []

    items = ""
    for ep in episodes:
        items += f"""
    <item>
      <title>{escape(ep['titre'])}</title>
      <enclosure url="{escape(ep['url'])}" type="audio/mpeg"/>
      <guid isPermaLink="false">{escape(ep['url'])}</guid>
      <pubDate>{escape(ep['date_iso'])}</pubDate>
    </item>"""

    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd">
  <channel>
    <title>Cyber &amp; IA Hebdo</title>
    <link>{escape(SITE_URL)}</link>
    <description>L'actualité tech décryptée par Antigravity</description>
    <language>fr-fr</language>
    <itunes:image href="{escape(SITE_URL)}/logo_podcast.png"/>{items}
  </channel>
</rss>"""
    return Response(content=xml.encode("utf-8"), media_type="application/rss+xml; charset=utf-8")


# --- 4. Santé du service (utile pour le monitoring / uptime checks) ---
@app.get("/health")
def health():
    return {"status": "ok", "supabase_configured": supabase is not None}


# --- 5. Page d'accueil et assets statiques ---
@app.get("/")
def afficher_site():
    return FileResponse("index.html")


@app.get("/logo_podcast.png")
def afficher_logo():
    return FileResponse("logo_podcast.png")
