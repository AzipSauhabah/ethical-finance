from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from api.config import API_VERSION  # si tu l’as déjà ailleurs

app = FastAPI(
    title="Ethical Finance Platform API",
    version=API_VERSION,
    description="Sauhabah — Backtest, signals & reporting engine",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
