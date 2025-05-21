from pydantic import BaseModel, EmailStr, constr


class UserAuth(BaseModel):
    name: constr(min_length=3)

