from sqlalchemy.orm import Session
from database import SessionLocal, engine
import models, auth

# Create tables if they don't exist
models.Base.metadata.create_all(bind=engine)

def create_admin_user(db: Session):
    username = "admin"
    email = "admin@example.com"
    password = "adminpassword"
    
    user = db.query(models.User).filter(models.User.username == username).first()
    if user:
        print(f"User {username} already exists.")
        return

    hashed_password = auth.get_password_hash(password)
    db_user = models.User(
        username=username,
        email=email,
        hashed_password=hashed_password,
        is_active=True,
        is_admin=True
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    print(f"User {username} created successfully.")

if __name__ == "__main__":
    db = SessionLocal()
    try:
        create_admin_user(db)
    finally:
        db.close()
