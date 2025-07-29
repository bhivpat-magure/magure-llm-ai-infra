from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routers import chat,user
from .auth.middleware import AuthMiddleware

app = FastAPI(
    title="Chat Box Assistant API",
    description="Backend API for the Chat Box Assistant",
    version="0.1.0"
)


# app.add_middleware(AuthMiddleware)

# CORS middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(user.router)
# Include routers
app.include_router(chat.router)

@app.get("/api2/hello")
async def root():
    return {"message": "Welcome to Chat Box Assistant API"}
