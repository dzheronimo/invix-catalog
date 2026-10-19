from datetime import datetime

from pydantic import BaseModel


class ProductOut(BaseModel):
    id: int
    name: str
    image_url: str
    created_at: datetime
