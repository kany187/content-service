from fastapi import FastAPI

from app.routes import generate 

app = FastAPI(title='AI Content Service')

app.include_router(generate.router)