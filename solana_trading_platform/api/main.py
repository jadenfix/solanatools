# api/main.py
from fastapi import FastAPI
from api.routes import portfolio

app = FastAPI(title="Solana Trading Platform API")

# Include portfolio endpoints
app.include_router(portfolio.router, prefix="/portfolio")

@app.get("/")
def root():
    return {"message": "Solana Trading Platform API is running!"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host="127.0.0.1", port=8000, reload=True)