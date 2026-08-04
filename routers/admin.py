from fastapi import APIRouter, Request, Depends
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func

from models.database import get_db
from models.models import User, JingwuRole
from utils.auth import get_current_user
from utils.i18n import t

router = APIRouter(prefix="/admin", tags=["admin"])
templates = Jinja2Templates(directory="templates")


def get_common_context(request: Request, db: Session):
    user = get_current_user(request, db)
    if not user or not user.is_admin:
        return None
    lang = request.cookies.get("lang", "zh")
    theme = request.cookies.get("theme", "light")
    return {
        "request": request,
        "user": user,
        "lang": lang,
        "theme": theme,
        "t": lambda key: t(key, lang),
    }


@router.get("", response_class=HTMLResponse)
async def admin_dashboard(request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    
    total_users = db.query(func.count(User.id)).scalar()
    total_jw_chars = db.query(func.count(JingwuRole.id)).scalar()
    recent_users = db.query(User).order_by(User.created_at.desc()).limit(10).all()
    
    ctx.update({
        "total_users": total_users,
        "total_jw_chars": total_jw_chars,
        "recent_users": recent_users,
    })
    return templates.TemplateResponse("admin/dashboard.html", ctx)


@router.get("/users", response_class=HTMLResponse)
async def admin_users(request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    
    users = db.query(User).order_by(User.created_at.desc()).all()
    ctx["users"] = users
    return templates.TemplateResponse("admin/users.html", ctx)
