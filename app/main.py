from urllib.parse import quote

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse

from app.config import settings
from app.middleware.simple_session import SimpleSessionMiddleware
from app.routes.aspecto import router as aspecto_router
from app.routes.admin import router as admin_router
from app.routes.auth import router as auth_router
from app.routes.ed import router as ed_router
from app.routes.espessura_ed import router as espessura_ed_router
from app.routes.operacoes import router as operacoes_router
from app.routes.poder_penetracao import router as poder_penetracao_router
from app.routes.pressao_filtros_pt import router as pressao_filtros_pt_router
from app.routes.pressao_filtros_ed import router as pressao_filtros_router
from app.routes.pt import router as pt_router
from app.routes.rugosidade import router as rugosidade_router
from app.routes.sigilatura import router as sigilatura_router
from app.routes.central_tintas import router as central_tintas_router
from app.routes.cabine_pintura import router as cabine_pintura_router
from app.routes.tensao_retificadores_ed import router as tensao_retificadores_router
from app.routes.temperatura_forno_ed import router as temperatura_forno_router
from app.routes.web import router as web_router
from app.services.auth_service import AdminLoginRequiredError, AdminPermissionDeniedError
from app.services.navigation import layout_context


app = FastAPI(title=settings.app_name)
templates = Jinja2Templates(directory=str(settings.templates_dir))
app.add_middleware(SimpleSessionMiddleware, secret_key=settings.secret_key)
app.mount("/static", StaticFiles(directory=str(settings.static_dir)), name="static")

app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(aspecto_router)
app.include_router(ed_router)
app.include_router(espessura_ed_router)
app.include_router(operacoes_router)
app.include_router(poder_penetracao_router)
app.include_router(pressao_filtros_pt_router)
app.include_router(pressao_filtros_router)
app.include_router(pt_router)
app.include_router(rugosidade_router)
app.include_router(sigilatura_router)
app.include_router(central_tintas_router)
app.include_router(cabine_pintura_router)
app.include_router(tensao_retificadores_router)
app.include_router(temperatura_forno_router)
app.include_router(web_router)


@app.exception_handler(AdminLoginRequiredError)
async def handle_admin_login_required(request: Request, exc: AdminLoginRequiredError):
    return RedirectResponse(url=f"/login?next={quote(exc.next_url, safe='/?=&')}", status_code=303)


@app.exception_handler(AdminPermissionDeniedError)
async def handle_admin_permission_denied(request: Request, _exc: AdminPermissionDeniedError):
    context = {
        "request": request,
        "page_title": "Acesso restrito",
        "page_description": "Esta área está disponível apenas para administradores.",
        "message_title": "Acesso restrito",
        "message_body": "Esta área está disponível apenas para administradores.",
        **layout_context(str(request.url.path), scope_source=request.query_params),
    }
    return templates.TemplateResponse(request=request, name="auth/access_restricted.html", context=context, status_code=403)


