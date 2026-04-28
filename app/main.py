from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.middleware.simple_session import SimpleSessionMiddleware
from app.routes.aspecto import router as aspecto_router
from app.routes.admin import router as admin_router
from app.routes.auth import router as auth_router
from app.routes.ed import router as ed_router
from app.routes.espessura_ed import router as espessura_ed_router
from app.routes.poder_penetracao import router as poder_penetracao_router
from app.routes.pressao_filtros_ed import router as pressao_filtros_router
from app.routes.rugosidade import router as rugosidade_router
from app.routes.sigilatura import router as sigilatura_router
from app.routes.central_tintas import router as central_tintas_router
from app.routes.tensao_retificadores_ed import router as tensao_retificadores_router
from app.routes.temperatura_forno_ed import router as temperatura_forno_router
from app.routes.web import router as web_router


app = FastAPI(title=settings.app_name)
app.add_middleware(SimpleSessionMiddleware, secret_key=settings.secret_key)
app.mount("/static", StaticFiles(directory=str(settings.static_dir)), name="static")

app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(aspecto_router)
app.include_router(ed_router)
app.include_router(espessura_ed_router)
app.include_router(poder_penetracao_router)
app.include_router(pressao_filtros_router)
app.include_router(rugosidade_router)
app.include_router(sigilatura_router)
app.include_router(central_tintas_router)
app.include_router(tensao_retificadores_router)
app.include_router(temperatura_forno_router)
app.include_router(web_router)


