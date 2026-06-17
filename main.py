from fastapi import FastAPI, Request, Form, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

from sqlalchemy import create_engine, String, Float, ForeignKey, select
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    Session,
    sessionmaker,
)

import jwt
import bcrypt

from datetime import datetime, timedelta

# ==========================================
# JWT CONFIG
# ==========================================

SECRET_KEY = "mysecretkey"
ALGORITHM = "HS256"

# ==========================================
# DATABASE
# ==========================================

DATABASE_URL = "sqlite:///expense_tracker.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False
)

# ==========================================
# BASE
# ==========================================

class Base(DeclarativeBase):
    pass

# ==========================================
# MODELS
# ==========================================

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)

    name: Mapped[str] = mapped_column(
        String(50)
    )

    email: Mapped[str] = mapped_column(
        String(100),
        unique=True
    )

    password: Mapped[str] = mapped_column(
        String(255)
    )


class Expense(Base):
    __tablename__ = "expenses"

    id: Mapped[int] = mapped_column(
        primary_key=True
    )

    title: Mapped[str] = mapped_column(
        String(100)
    )

    amount: Mapped[float] = mapped_column(
        Float
    )

    category: Mapped[str] = mapped_column(
        String(50)
    )

    description: Mapped[str] = mapped_column(
        String(255)
    )

    date: Mapped[str] = mapped_column(
        String(50)
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id")
    )


class Budget(Base):
    __tablename__ = "budgets"

    id: Mapped[int] = mapped_column(
        primary_key=True
    )

    monthly_limit: Mapped[float] = mapped_column(
        Float
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id")
    )

# ==========================================
# CREATE TABLES
# ==========================================

Base.metadata.create_all(bind=engine)

# ==========================================
# APP
# ==========================================

app = FastAPI()

templates = Jinja2Templates(
    directory="Frontend/templates"
)

app.mount(
    "/static",
    StaticFiles(directory="Frontend/static"),
    name="static"
)

# ==========================================
# DATABASE DEPENDENCY
# ==========================================

def get_db():

    db = SessionLocal()

    try:
        yield db

    finally:
        db.close()

# ==========================================
# PASSWORD FUNCTIONS
# ==========================================

def hash_password(password: str):

    return bcrypt.hashpw(
        password.encode(),
        bcrypt.gensalt()
    ).decode()


def verify_password(
    plain_password,
    hashed_password
):

    return bcrypt.checkpw(
        plain_password.encode(),
        hashed_password.encode()
    )

# ==========================================
# JWT FUNCTIONS
# ==========================================

def create_token(email: str):

    payload = {
        "sub": email,
        "exp": datetime.utcnow() + timedelta(hours=2)
    }

    return jwt.encode(
        payload,
        SECRET_KEY,
        algorithm=ALGORITHM
    )


def get_current_user(
    request: Request,
    db: Session = Depends(get_db)
):

    token = request.cookies.get(
        "access_token"
    )

    if not token:
        return None

    try:

        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )

        email = payload.get("sub")

    except:
        return None

    user = db.scalars(
        select(User).where(
            User.email == email
        )
    ).first()

    return user

# ==========================================
# AUTH PAGES
# ==========================================

@app.get("/", response_class=HTMLResponse)
def home():

    return RedirectResponse(
        "/login",
        status_code=303
    )


@app.get("/signup", response_class=HTMLResponse)
def signup_page(
    request: Request
):

    return templates.TemplateResponse(
        request=request,
        name="signup.html"
    )


@app.post("/signup")
def signup_post(
    request: Request,
    name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):

    existing = db.scalars(
        select(User).where(
            User.email == email
        )
    ).first()

    if existing:

        return templates.TemplateResponse(
            request=request,
            name="signup.html",
            context={
                "error": "Email already exists"
            }
        )

    user = User(
        name=name,
        email=email,
        password=hash_password(password)
    )

    db.add(user)
    db.commit()

    return RedirectResponse(
        "/login",
        status_code=303
    )


@app.get("/login", response_class=HTMLResponse)
def login_page(
    request: Request
):

    return templates.TemplateResponse(
        request=request,
        name="login.html"
    )


@app.post("/login")
def login_post(
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):

    user = db.scalars(
        select(User).where(
            User.email == email
        )
    ).first()

    if not user:

        return RedirectResponse(
            "/login",
            status_code=303
        )

    if not verify_password(
        password,
        user.password
    ):

        return RedirectResponse(
            "/login",
            status_code=303
        )

    token = create_token(
        user.email
    )

    response = RedirectResponse(
        "/dashboard",
        status_code=303
    )

    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True
    )

    return response

# ==========================================
# LOGOUT
# ==========================================

@app.get("/logout")
def logout():

    response = RedirectResponse(
        "/login",
        status_code=303
    )

    response.delete_cookie(
        "access_token"
    )

    return response


# ==========================================
# DASHBOARD
# ==========================================

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):

    if not current_user:

        return RedirectResponse(
            "/login",
            status_code=303
        )

    expenses = db.scalars(
        select(Expense).where(
            Expense.user_id == current_user.id
        )
    ).all()

    budget = db.scalars(
        select(Budget).where(
            Budget.user_id == current_user.id
        )
    ).first()

    total_expense = sum(
        expense.amount
        for expense in expenses
    )

    monthly_budget = (
        budget.monthly_limit
        if budget
        else 0
    )

    remaining_budget = (
        monthly_budget - total_expense
    )

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "current_user": current_user,
            "total_expense": total_expense,
            "monthly_budget": monthly_budget,
            "remaining_budget": remaining_budget,
            "total_transactions": len(expenses)
        }
    )


# ==========================================
# CREATE EXPENSE PAGE
# ==========================================

@app.get("/create-expense",
         response_class=HTMLResponse)
def create_expense_page(
    request: Request,
    current_user: User = Depends(get_current_user)
):

    if not current_user:

        return RedirectResponse(
            "/login",
            status_code=303
        )

    return templates.TemplateResponse(
        request=request,
        name="create_expense.html"
    )


# ==========================================
# CREATE EXPENSE
# ==========================================

@app.post("/create-expense")
def create_expense(
    title: str = Form(...),
    amount: float = Form(...),
    category: str = Form(...),
    description: str = Form(...),
    date: str = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):

    if not current_user:

        return RedirectResponse(
            "/login",
            status_code=303
        )

    expense = Expense(
        title=title,
        amount=amount,
        category=category,
        description=description,
        date=date,
        user_id=current_user.id
    )

    db.add(expense)
    db.commit()

    return RedirectResponse(
        "/dashboard",
        status_code=303
    )


# ==========================================
# UPDATE PAGE
# ==========================================

@app.get(
    "/update-expense/{expense_id}",
    response_class=HTMLResponse
)
def update_expense_page(
    expense_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):

    if not current_user:

        return RedirectResponse(
            "/login",
            status_code=303
        )

    expense = db.get(
        Expense,
        expense_id
    )

    return templates.TemplateResponse(
        request=request,
        name="update_expense.html",
        context={
            "expense": expense
        }
    )


# ==========================================
# UPDATE EXPENSE
# ==========================================

@app.post(
    "/update-expense/{expense_id}"
)
def update_expense(
    expense_id: int,
    title: str = Form(...),
    amount: float = Form(...),
    category: str = Form(...),
    description: str = Form(...),
    date: str = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):

    if not current_user:

        return RedirectResponse(
            "/login",
            status_code=303
        )

    expense = db.get(
        Expense,
        expense_id
    )

    if expense:

        expense.title = title
        expense.amount = amount
        expense.category = category
        expense.description = description
        expense.date = date

        db.commit()

    return RedirectResponse(
        "/dashboard",
        status_code=303
    )


# ==========================================
# DELETE EXPENSE
# ==========================================

@app.get(
    "/delete-expense/{expense_id}"
)
def delete_expense(
    expense_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):

    if not current_user:

        return RedirectResponse(
            "/login",
            status_code=303
        )

    expense = db.get(
        Expense,
        expense_id
    )

    if expense:

        db.delete(expense)
        db.commit()

    return RedirectResponse(
        "/dashboard",
        status_code=303
    )


# ==========================================
# BUDGET PAGE
# ==========================================

@app.get(
    "/budget",
    response_class=HTMLResponse
)
def budget_page(
    request: Request,
    current_user: User = Depends(get_current_user)
):

    if not current_user:

        return RedirectResponse(
            "/login",
            status_code=303
        )

    return templates.TemplateResponse(
        request=request,
        name="budget.html"
    )


# ==========================================
# SAVE BUDGET
# ==========================================

@app.post("/budget")
def save_budget(
    monthly_limit: float = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):

    if not current_user:

        return RedirectResponse(
            "/login",
            status_code=303
        )

    budget = db.scalars(
        select(Budget).where(
            Budget.user_id == current_user.id
        )
    ).first()

    if budget:

        budget.monthly_limit = monthly_limit

    else:

        budget = Budget(
            monthly_limit=monthly_limit,
            user_id=current_user.id
        )

        db.add(budget)

    db.commit()

    return RedirectResponse(
        "/dashboard",
        status_code=303
    )