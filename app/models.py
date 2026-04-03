from pydantic import BaseModel, EmailStr, Field

'''
This file contains the request body models used by FastAPI.

Why this exists:
- it keeps request validation separate from route logic
- it makes the API contracts easy to understand
- FastAPI automatically uses these models for validation and docs
'''


class RegisterRequest(BaseModel):
    '''Expected body for creating a new user.'''
    name: str = Field(..., min_length=1)
    email: EmailStr
    password: str = Field(..., min_length=4)



class XamanTopupRequest(BaseModel):
    '''
    Expected body for creating a Xaman payment request.

    Fields:
    - apiKey: the API key to credit after payment
    - credits: number of credits to buy
    - endpointId: the endpoint ID (determines which developer receives the XRP)
    '''
    apiKey: str = Field(..., min_length=1)
    credits: int = Field(..., gt=0)
    endpointId: str = Field("", min_length=0)


class SummariseRequest(BaseModel):
    '''
    Expected body for the demo protected endpoint.

    Fields:
    - text: the input content that the endpoint will "summarise"
    '''
    text: str = Field(..., min_length=1)


class LoginRequest(BaseModel):
    '''Expected body for signing in.'''
    email: EmailStr
    password: str = Field(..., min_length=1)


class DeveloperRegisterRequest(BaseModel):
    '''Expected body for registering a new developer.'''
    name: str = Field(..., min_length=1)
    email: EmailStr
    password: str = Field(..., min_length=4)
    xrplAddress: str = ""


class CreateEndpointRequest(BaseModel):
    '''Expected body for a developer adding an API endpoint.'''
    developerKey: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    description: str = ""
    url: str = Field(..., min_length=1)
    costPerCall: int = Field(1, gt=0)
    authHeader: str = ""


class UpdateEndpointRequest(BaseModel):
    '''Expected body for updating an endpoint.'''
    developerKey: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    description: str = ""
    url: str = Field(..., min_length=1)
    costPerCall: int = Field(..., gt=0)
    isActive: bool = True
    authHeader: str = ""


class ProxyCallRequest(BaseModel):
    '''Expected body for calling an endpoint through the gateway.'''
    endpointId: str = Field(..., min_length=1)
    payload: dict = {}
