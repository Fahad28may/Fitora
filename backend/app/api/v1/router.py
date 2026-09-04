from fastapi import APIRouter

from app.api.v1.ai import router as ai_router
from app.api.v1.auth import router as auth_router
from app.api.v1.dashboard import router as dashboard_router
from app.api.v1.exercises import router as exercises_router
from app.api.v1.food_diary import router as food_diary_router
from app.api.v1.foods import router as foods_router
from app.api.v1.goals import router as goals_router
from app.api.v1.measurements import router as measurements_router
from app.api.v1.profile import router as profile_router
from app.api.v1.recommendations import router as recommendations_router
from app.api.v1.water import router as water_router
from app.api.v1.weight import router as weight_router
from app.api.v1.workout_sessions import router as workout_sessions_router
from app.api.v1.workouts import router as workouts_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth_router)
api_router.include_router(profile_router)
api_router.include_router(goals_router)
api_router.include_router(weight_router)
api_router.include_router(measurements_router)
api_router.include_router(foods_router)
api_router.include_router(food_diary_router)
api_router.include_router(water_router)
api_router.include_router(exercises_router)
api_router.include_router(workouts_router)
api_router.include_router(workout_sessions_router)
api_router.include_router(dashboard_router)
api_router.include_router(recommendations_router)
api_router.include_router(ai_router)
