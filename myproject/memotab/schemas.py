from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import date as Date, datetime as DateTime
from decimal import Decimal


class SourceBase(BaseModel):
    """Base schema for Source model"""
    text: str = Field(..., min_length=1, max_length=200, description="Description of the cash collection source")
    is_active: bool = Field(default=True, description="Whether the source is active")


class SourceCreate(SourceBase):
    """Schema for creating a new Source"""
    pass


class SourceUpdate(BaseModel):
    """Schema for updating a Source"""
    text: Optional[str] = Field(None, min_length=1, max_length=200)
    is_active: Optional[bool] = None


class SourceResponse(SourceBase):
    """Schema for Source response"""
    id: int
    created_at: DateTime
    updated_at: DateTime
    created_by_id: Optional[int] = None
    
    class Config:
        from_attributes = True


class CashCollectBase(BaseModel):
    """Base schema for CashCollect model"""
    date: Date = Field(..., description="Date of cash collection")
    source_id: int = Field(..., description="ID of the cash collection source")
    amount: Decimal = Field(..., gt=0, description="Amount collected in currency")
    received_by_id: int = Field(..., description="ID of the user who received the cash")
    note: Optional[str] = Field(default="", description="Additional notes about the cash collection")

    @field_validator('amount')
    @classmethod
    def validate_amount(cls, v):
        if v <= 0:
            raise ValueError('Amount must be greater than 0')
        return round(v, 2)


class CashCollectCreate(CashCollectBase):
    """Schema for creating a new CashCollect"""
    pass


class CashCollectUpdate(BaseModel):
    """Schema for updating a CashCollect"""
    date: Optional[Date] = None
    source_id: Optional[int] = None
    amount: Optional[Decimal] = Field(None, gt=0)
    received_by_id: Optional[int] = None
    note: Optional[str] = None

    @field_validator('amount')
    @classmethod
    def validate_amount(cls, v):
        if v is not None and v <= 0:
            raise ValueError('Amount must be greater than 0')
        return round(v, 2) if v is not None else v


class CashCollectResponse(CashCollectBase):
    """Schema for CashCollect response"""
    id: int
    created_at: DateTime
    updated_at: DateTime
    created_by_id: Optional[int] = None
    
    # Additional fields with related data
    source_text: Optional[str] = None
    received_by_username: Optional[str] = None
    
    class Config:
        from_attributes = True


class CashCollectDetailResponse(CashCollectResponse):
    """Detailed schema for CashCollect with full related object data"""
    source: SourceResponse
    received_by_username: str
    created_by_username: Optional[str] = None
    
    class Config:
        from_attributes = True


class CashCollectListResponse(BaseModel):
    """Schema for paginated CashCollect list response"""
    count: int
    next: Optional[str] = None
    previous: Optional[str] = None
    results: List[CashCollectResponse]


class SourceListResponse(BaseModel):
    """Schema for paginated Source list response"""
    count: int
    next: Optional[str] = None
    previous: Optional[str] = None
    results: List[SourceResponse]


class ErrorResponse(BaseModel):
    """Schema for error responses"""
    error: str
    detail: Optional[str] = None
    field_errors: Optional[dict] = None


class SuccessResponse(BaseModel):
    """Schema for success responses"""
    message: str
    data: Optional[dict] = None