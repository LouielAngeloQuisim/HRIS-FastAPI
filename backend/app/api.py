from fastapi import APIRouter

from app.user.routes import auth, users, utils, private
from app.item.routes import items

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(items.router)
api_router.include_router(utils.router)
api_router.include_router(private.router)