from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.services.auth_service import authenticate_user, login_user, logout_user


templates = Jinja2Templates(directory=str(settings.templates_dir))
router = APIRouter(tags=["auth"])


@router.get("/login", name="login")
def login_form(request: Request, next: str | None = None):
    context = {
        "page_title": "Entrar",
        "next_url": next or "/turno-atual",
        "error_message": None,
    }
    return templates.TemplateResponse(request=request, name="auth/login.html", context=context)


@router.post("/login", name="login_post")
def login_post(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    next_url: str = Form("/turno-atual"),
    db: Session = Depends(get_db),
):
    user = authenticate_user(db, username, password)
    if user is None:
        context = {
            "page_title": "Entrar",
            "next_url": next_url,
            "error_message": "Usuario ou senha invalidos.",
        }
        return templates.TemplateResponse(request=request, name="auth/login.html", context=context, status_code=400)

    login_user(request, user)
    return RedirectResponse(url=next_url or "/turno-atual", status_code=303)


@router.get("/logout", name="logout")
def logout(request: Request):
    logout_user(request)
    return RedirectResponse(url="/turno-atual", status_code=303)
