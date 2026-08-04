from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from models.database import get_db
from models.models import User
from utils.auth import get_password_hash, verify_password, create_access_token, get_current_user
from utils.i18n import t

router = APIRouter(prefix="/auth", tags=["auth"])
templates = Jinja2Templates(directory="templates")


def get_common_context(request: Request, db: Session):
    user = get_current_user(request, db)
    lang = request.cookies.get("lang", "zh")
    theme = request.cookies.get("theme", "light")
    return {
        "request": request,
        "user": user,
        "lang": lang,
        "theme": theme,
        "t": lambda key: t(key, lang),
    }


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if ctx["user"]:
        return RedirectResponse(url="/", status_code=302)
    return templates.TemplateResponse("login.html", ctx)


@router.post("/login")
async def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.username == username).first()
    if not user or not verify_password(password, user.password_hash):
        ctx = get_common_context(request, db)
        ctx["message"] = t("invalid_credentials", ctx["lang"])
        ctx["message_type"] = "error"
        return templates.TemplateResponse("login.html", ctx)
    
    user.last_login_at = datetime.utcnow()
    db.commit()
    
    access_token = create_access_token(
        data={"sub": str(user.id)},
        expires_delta=timedelta(days=7)
    )
    response = RedirectResponse(url="/", status_code=302)
    response.set_cookie(
        "access_token",
        access_token,
        max_age=7*24*60*60,
        httponly=True
    )
    return response


@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if ctx["user"]:
        return RedirectResponse(url="/", status_code=302)
    return templates.TemplateResponse("register.html", ctx)


@router.post("/register")
async def register(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
    nickname: str = Form(None),
    db: Session = Depends(get_db)
):
    ctx = get_common_context(request, db)
    
    if password != confirm_password:
        ctx["message"] = t("password_mismatch", ctx["lang"])
        ctx["message_type"] = "error"
        return templates.TemplateResponse("register.html", ctx)
    
    if db.query(User).filter(User.username == username).first():
        ctx["message"] = t("username_taken", ctx["lang"])
        ctx["message_type"] = "error"
        return templates.TemplateResponse("register.html", ctx)
    
    user = User(
        username=username,
        nickname=nickname or username,
        password_hash=get_password_hash(password),
        language=ctx["lang"],
        theme=ctx["theme"]
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    
    access_token = create_access_token(
        data={"sub": str(user.id)},
        expires_delta=timedelta(days=7)
    )
    response = RedirectResponse(url="/", status_code=302)
    response.set_cookie(
        "access_token",
        access_token,
        max_age=7*24*60*60,
        httponly=True
    )
    return response


@router.get("/logout")
async def logout(request: Request):
    response = RedirectResponse(url="/auth/login", status_code=302)
    response.delete_cookie("access_token")
    return response
