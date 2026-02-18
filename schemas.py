from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import date

class UserBase(BaseModel):
    username: str
    email: Optional[str] = None
    is_active: Optional[bool] = True

class UserCreate(UserBase):
    password: str

class UserSchema(UserBase):
    id: int
    is_admin: bool

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str

class LoginCredentials(BaseModel):
    username: str
    password: str

class TokenData(BaseModel):
    username: Optional[str] = None

# Employee Schemas
class EmployeeBase(BaseModel):
    employee_id: str
    full_name: str
    email: EmailStr
    department: str

class EmployeeCreate(EmployeeBase):
    pass

class EmployeeSchema(EmployeeBase):
    id: int

    class Config:
        from_attributes = True

# Attendance Schemas
class AttendanceBase(BaseModel):
    date: date
    status: str # Present / Absent

class AttendanceCreate(AttendanceBase):
    employee_id: int

class AttendanceSchema(AttendanceBase):
    id: int
    employee_id: int

    class Config:
        from_attributes = True
