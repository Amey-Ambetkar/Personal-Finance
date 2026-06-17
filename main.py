from fastapi import FastAPI, Request, Form, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

from sqlalchemy import create_engine, String, Float, ForeignKey, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, Session, sessionmaker

import jwt, bcrypt
from datetime import datetime, timedelta

# =========================
# CONFIG
# =========================

SECRET_KEY = "mysecretkey"
ALGORITHM = "HS256"
DATABASE_URL = "sqlite:///expense_tracker.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

app = FastAPI()

templates = Jinja2Templates(directory="Frontend/templates")
app.mount("/static", StaticFiles(directory="Frontend/static"), name="static")

# =========================
# DB BASE
# =========================

class Base(DeclarativeBase):
    pass

# =========================
# MODELS
# =========================

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50))
    email: Mapped[str] = mapped_column(String(100), unique=True)
    password: Mapped[str] = mapped_column(String(255))


class Expense(Base):
    __tablename__ = "expenses"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(100))
    amount: Mapped[float] = mapped_column(Float)
    category: Mapped[str] = mapped_column(String(50))
    description: Mapped[str] = mapped_column(String(255))
    date: Mapped[str] = mapped_column(String(50))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))


class Budget(Base):
    __tablename__ = "budgets"
    id: Mapped[int] = mapped_column(primary_key=True)
    monthly_limit: Mapped[float] = mapped_column(Float)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))

Base.metadata.create_all(bind=engine)

# =========================
# DEPENDENCIES
# =========================

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def require_user(user):
    if not user:
        return RedirectResponse("/login", status_code=303)

# =========================
# HELPERS
# =========================

def q_user(db, email):
    return db.scalars(select(User).where(User.email == email)).first()

def q_expenses(db, uid):
    return db.scalars(select(Expense).where(Expense.user_id == uid)).all()

def q_budget(db, uid):
    return db.scalars(select(Budget).where(Budget.user_id == uid)).first()

# =========================
# AUTH UTILS
# =========================

def hash_password(p):
    return bcrypt.hashpw(p.encode(), bcrypt.gensalt()).decode()

def verify_password(p, h):
    return bcrypt.checkpw(p.encode(), h.encode())

def create_token(email):
    payload = {"sub": email, "exp": datetime.utcnow() + timedelta(hours=2)}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def get_current_user(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get("access_token")
    if not token:
        return None
    try:
        email = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM]).get("sub")
    except:
        return None
    return q_user(db, email)

# =========================
# AUTH ROUTES
# =========================

@app.get("/")
def home():
    return RedirectResponse("/login")

@app.get("/signup", response_class=HTMLResponse)
def signup_page(request: Request):
    return templates.TemplateResponse("signup.html", {"request": request})

@app.post("/signup")
def signup(name: str = Form(...), email: str = Form(...), password: str = Form(...), db: Session = Depends(get_db), request: Request = None):
    if q_user(db, email):
        return templates.TemplateResponse("signup.html", {"request": request, "error": "Email exists"})

    db.add(User(name=name, email=email, password=hash_password(password)))
    db.commit()
    return RedirectResponse("/login", status_code=303)

@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
def login(email: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    user = q_user(db, email)

    if not user or not verify_password(password, user.password):
        return RedirectResponse("/login", status_code=303)

    token = create_token(user.email)
    resp = RedirectResponse("/dashboard", status_code=303)
    resp.set_cookie("access_token", token, httponly=True)
    return resp

@app.get("/logout")
def logout():
    resp = RedirectResponse("/login", status_code=303)
    resp.delete_cookie("access_token")
    return resp

# =========================
# DASHBOARD
# =========================

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    if (r := require_user(current_user)):
        return r

    expenses = q_expenses(db, current_user.id)
    budget = q_budget(db, current_user.id)

    total = sum(e.amount for e in expenses)
    limit = budget.monthly_limit if budget else 0

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "current_user": current_user,
        "total_expense": total,
        "monthly_budget": limit,
        "remaining_budget": limit - total,
        "total_transactions": len(expenses)
    })

# =========================
# EXPENSES
# =========================

@app.get("/create-expense", response_class=HTMLResponse)
def create_page(request: Request, current_user=Depends(get_current_user)):
    if (r := require_user(current_user)):
        return r
    return templates.TemplateResponse("create_expense.html", {"request": request})

@app.post("/create-expense")
def create_expense(title: str = Form(...), amount: float = Form(...), category: str = Form(...),
                    description: str = Form(...), date: str = Form(...),
                    db: Session = Depends(get_db), current_user=Depends(get_current_user)):

    if (r := require_user(current_user)):
        return r

    db.add(Expense(
        title=title,
        amount=amount,
        category=category,
        description=description,
        date=date,
        user_id=current_user.id
    ))
    db.commit()
    return RedirectResponse("/dashboard", status_code=303)

@app.get("/update-expense/{expense_id}", response_class=HTMLResponse)
def update_page(expense_id: int, request: Request, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    if (r := require_user(current_user)):
        return r

    expense = db.get(Expense, expense_id)
    return templates.TemplateResponse("update_expense.html", {"request": request, "expense": expense})

@app.post("/update-expense/{expense_id}")
def update_expense(expense_id: int, title: str = Form(...), amount: float = Form(...),
                   category: str = Form(...), description: str = Form(...), date: str = Form(...),
                   db: Session = Depends(get_db), current_user=Depends(get_current_user)):

    if (r := require_user(current_user)):
        return r

    e = db.get(Expense, expense_id)
    if e:
        e.title, e.amount, e.category, e.description, e.date = title, amount, category, description, date
        db.commit()

    return RedirectResponse("/dashboard", status_code=303)

@app.get("/delete-expense/{expense_id}")
def delete_expense(expense_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    if (r := require_user(current_user)):
        return r

    e = db.get(Expense, expense_id)
    if e:
        db.delete(e)
        db.commit()

    return RedirectResponse("/dashboard", status_code=303)

# =========================
# BUDGET
# =========================

@app.get("/budget", response_class=HTMLResponse)
def budget_page(request: Request, current_user=Depends(get_current_user)):
    if (r := require_user(current_user)):
        return r
    return templates.TemplateResponse("budget.html", {"request": request})

@app.post("/budget")
def save_budget(monthly_limit: float = Form(...), db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    if (r := require_user(current_user)):
        return r

    b = q_budget(db, current_user.id)

    if b:
        b.monthly_limit = monthly_limit
    else:
        db.add(Budget(monthly_limit=monthly_limit, user_id=current_user.id))

    db.commit()
    return RedirectResponse("/dashboard", status_code=303)