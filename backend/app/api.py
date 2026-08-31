from fastapi import APIRouter

from app.attendance import routes as attendance_routes
from app.config.settings import settings
from app.dashboard import routes as dashboard_routes
from app.employee import routes as employee_routes
from app.item.routes import items
from app.rbac import routes as rbac_routes
from app.user.routes import auth, private, users, utils

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(items.router)
api_router.include_router(utils.router)
api_router.include_router(rbac_routes.router)
for employee_router in employee_routes.routers:
    api_router.include_router(employee_router)
for attendance_router in attendance_routes.routers:
    api_router.include_router(attendance_router)
api_router.include_router(dashboard_routes.router)

# `/private` creates users with no authentication whatsoever. It exists purely
# as a test-support hook in the upstream scaffold, so it must never be mounted
# anywhere it could be reached from the internet.
if settings.ENVIRONMENT == "local":
    api_router.include_router(private.router)
