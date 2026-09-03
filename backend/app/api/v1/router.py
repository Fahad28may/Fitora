from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.food_diary import router as food_diary_router
from app.api.v1.foods import router as foods_router
from app.api.v1.goals import router as goals_router
from app.api.v1.profile import router as profile_router
from app.api.v1.weight import router as weight_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth_router)
api_router.include_router(profile_router)
api_router.include_router(goals_router)
api_router.include_router(weight_router)
api_router.include_router(foods_router)
api_router.include_router(food_diary_router)
