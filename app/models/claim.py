from pydantic import BaseModel
from typing import Optional

class Department(BaseModel):
    code: Optional[str] = None
    name: Optional[str] = None

class NHSOClaimDetail(BaseModel):
    hcode: str
    department: Optional[Department] = None
    mainInsclCode: str
    serviceDateTime: int  # Unix Timestamp (ms)
    invoiceDateTime: int  # Unix Timestamp (ms)
    transactionId: str
    totalAmount: float
    paidAmount: float
    privilegeAmount: float
    claimServiceCode: str
    pid: str
    sourceId: str
    visitNumber: Optional[str] = None
    recorderPid: str
    # New fields from Swagger v8.0
    mobile: Optional[str] = ""
    tel: Optional[str] = ""
    reservedId: Optional[str] = ""
    latitude: Optional[float] = 0.0
    longitude: Optional[float] = 0.0
