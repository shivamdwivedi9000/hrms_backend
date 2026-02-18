from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from fastapi.middleware.cors import CORSMiddleware
from typing import List

import os
import models, schemas, auth
from database import engine, get_db
from dotenv import load_dotenv

load_dotenv()

# Create tables
models.Base.metadata.create_all(bind=engine)

# Ensure initial admin user exists
def ensure_admin_user():
    print("Checking for initial admin user...", flush=True)
    from database import SessionLocal
    db = SessionLocal()
    try:
        admin_username = "admin"
        admin = db.query(models.User).filter(models.User.username == admin_username).first()
        if not admin:
            print(f"Admin user '{admin_username}' not found. Creating...", flush=True)
            hashed_password = auth.get_password_hash("adminpassword")
            db_admin = models.User(
                username=admin_username,
                email="admin@example.com",
                hashed_password=hashed_password,
                is_active=True,
                is_admin=True
            )
            db.add(db_admin)
            db.commit()
            print(f"Admin user '{admin_username}' created successfully.", flush=True)
        else:
            print(f"Admin user '{admin_username}' already exists.", flush=True)
    except Exception as e:
        print(f"CRITICAL ERROR in ensure_admin_user: {e}", flush=True)
    finally:
        db.close()

# Run the startup check
ensure_admin_user()

app = FastAPI()

# CORS Middleware
origins = [
    "http://localhost",
    "http://localhost:5173",
    "http://localhost:3000",
    "https://hrmsfrontends.vercel.app", # User's specific production frontend
]

# Allow dynamic origins from environment
allowed_origins_env = os.getenv("ALLOWED_ORIGINS")
print(f"DEBUG: ALLOWED_ORIGINS env value: '{allowed_origins_env}'", flush=True)

if allowed_origins_env:
    if allowed_origins_env == "*":
        print("DEBUG: Enabling wildcard CORS (*)", flush=True)
        origins = ["*"]
    else:
        extra_origins = [o.strip() for o in allowed_origins_env.split(",")]
        print(f"DEBUG: Adding extra origins: {extra_origins}", flush=True)
        origins.extend(extra_origins)

# Ensure origins are unique
origins = list(set(origins))
print(f"DEBUG: Final CORS origins: {origins}", flush=True)

# Important for wildcard origins
use_credentials = True
if "*" in origins:
    use_credentials = False
    print("DEBUG: credentials disabled due to wildcard origin", flush=True)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=use_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = auth.jwt.decode(token, auth.SECRET_KEY, algorithms=[auth.ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = schemas.TokenData(username=username)
    except auth.JWTError:
        raise credentials_exception
    user = db.query(models.User).filter(models.User.username == token_data.username).first()
    if user is None:
        raise credentials_exception
    return user

@app.post("/token", response_model=schemas.Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    print(f"Login attempt: username='{form_data.username}'", flush=True)
    user = db.query(models.User).filter(models.User.username == form_data.username).first()
    
    if not user:
        print(f"Login FAILED: User '{form_data.username}' not found in DB", flush=True)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Check if user is active
    if not user.is_active:
        print(f"Login FAILED: User '{form_data.username}' is inactive", flush=True)
        raise HTTPException(status_code=400, detail="Inactive user")

    password_verified = auth.verify_password(form_data.password, user.hashed_password)
    if not password_verified:
        print(f"Login FAILED: Password mismatch for user '{form_data.username}'", flush=True)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    print(f"Login SUCCESS: User '{form_data.username}' logged in", flush=True)
    access_token_expires = auth.timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth.create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/login", response_model=schemas.Token)
async def login_json(credentials: schemas.LoginCredentials, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.username == credentials.username).first()
    if not user or not auth.verify_password(credentials.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = auth.timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth.create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/users/", response_model=schemas.UserSchema)
def create_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(models.User).filter(models.User.username == user.username).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    hashed_password = auth.get_password_hash(user.password)
    db_user = models.User(username=user.username, email=user.email, hashed_password=hashed_password)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

@app.get("/users/me", response_model=schemas.UserSchema)
async def read_users_me(current_user: models.User = Depends(get_current_user)):
    return current_user

@app.get("/")
def read_root():
    return {"message": "Welcome to HRMS Admin Backend"}

@app.get("/health")
def health_check():
    return {"status": "healthy"}

@app.get("/debug/info")
def debug_info(db: Session = Depends(get_db)):
    try:
        user_count = db.query(models.User).count()
        users = db.query(models.User.username).all()
        return {
            "status": "online",
            "database": "connected",
            "user_count": user_count,
            "usernames": [u.username for u in users]
        }
    except Exception as e:
        return {"status": "error", "database_error": str(e)}

# Employee Management
@app.get("/employees/", response_model=List[schemas.EmployeeSchema])
def read_employees(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    employees = db.query(models.Employee).offset(skip).limit(limit).all()
    return employees

@app.post("/employees/", response_model=schemas.EmployeeSchema)
def create_employee(employee: schemas.EmployeeCreate, db: Session = Depends(get_db)):
    db_employee = db.query(models.Employee).filter(models.Employee.employee_id == employee.employee_id).first()
    if db_employee:
        raise HTTPException(status_code=400, detail="Employee ID already exists")
    
    db_employee = models.Employee(**employee.model_dump())
    db.add(db_employee)
    db.commit()
    db.refresh(db_employee)
    return db_employee

@app.delete("/employees/{emp_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_employee(emp_id: int, db: Session = Depends(get_db)):
    db_employee = db.query(models.Employee).filter(models.Employee.id == emp_id).first()
    if not db_employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    db.delete(db_employee)
    db.commit()
    return None

# Attendance Management
@app.get("/attendance/{emp_id}", response_model=List[schemas.AttendanceSchema])
def read_attendance(emp_id: int, db: Session = Depends(get_db)):
    # Verify employee exists
    db_employee = db.query(models.Employee).filter(models.Employee.id == emp_id).first()
    if not db_employee:
        raise HTTPException(status_code=404, detail="Employee not found")
        
    return db.query(models.Attendance).filter(models.Attendance.employee_id == emp_id).all()

@app.get("/attendance/", response_model=List[schemas.AttendanceSchema])
def read_all_attendance(db: Session = Depends(get_db)):
    return db.query(models.Attendance).all()

@app.post("/attendance/", response_model=schemas.AttendanceSchema)
def mark_attendance(attendance: schemas.AttendanceCreate, db: Session = Depends(get_db)):
    # Verify employee exists
    db_employee = db.query(models.Employee).filter(models.Employee.id == attendance.employee_id).first()
    if not db_employee:
        raise HTTPException(status_code=404, detail="Employee not found")
        
    db_attendance = models.Attendance(**attendance.model_dump())
    db.add(db_attendance)
    db.commit()
    db.refresh(db_attendance)
    return db_attendance
