from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.config import API_VERSION

app = FastAPI(title="Ethical Finance Platform API", version=API_VERSION)

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
