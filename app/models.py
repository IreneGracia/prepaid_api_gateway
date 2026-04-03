from pydantic import BaseModel, EmailStr, Field

'''
This file contains the request body models used by FastAPI.

Why this exists:
- it keeps request validation separate from route logic
- it makes the API contracts easy to understand
- FastAPI automatically uses these models for validation and docs
'''


class RegisterRequest(BaseModel):
    '''
    Expected body for creating a new user.

    Fields:
    - name: display name shown in the UI and responses
    - email: unique email address for the user
    '''
    name: str = Field(..., min_length=1)
    email: EmailStr


class MockTopupRequest(BaseModel):
    '''
    Expected body for adding mock credits.

    Fields:
    - apiKey: the issued API key we want to top up
    - credits: a positive integer amount of demo credits
    '''
    apiKey: str = Field(..., min_length=1)
    credits: int = Field(..., gt=0)


class XamanTopupRequest(BaseModel):
    '''
    Expected body for creating a Xaman payment request.

    Fields:
    - apiKey: the API key to credit after payment
    - credits: number of credits to buy (1 credit = 1 XRP on testnet)
    '''
    apiKey: str = Field(..., min_length=1)
    credits: int = Field(..., gt=0)


class SummariseRequest(BaseModel):
    '''
    Expected body for the demo protected endpoint.

    Fields:
    - text: the input content that the endpoint will "summarise"
    '''
    text: str = Field(..., min_length=1)


class LoginRequest(BaseModel):
    '''Expected body for signing in by email.'''
    email: EmailStr


class DeveloperRegisterRequest(BaseModel):
    '''Expected body for registering a new developer.'''
    name: str = Field(..., min_length=1)
    email: EmailStr


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
