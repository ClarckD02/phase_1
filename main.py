# extract_summarize/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import routers from local package
from routers import testing


def create_app() -> FastAPI:
    app = FastAPI(
        title="Extract & Summarize",
        version="1.0.0",
        description="PDF → Extraction → NER → Format (Gemini) → Summarize (Claude), with batch & realtime endpoints.",
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],   #  loosened for dev, tighten in prod
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Routers
    app.include_router(testing.router)

    @app.get("/", tags=["meta"])
    def root():
        return {
            "name": "Extract & Summarize",
            "docs": "/docs",
            "health": "/healthz",
            "endpoints": ["/testing/realtest"],
        }

    @app.get("/healthz", tags=["meta"])
    def healthz():
        return {"ok": True}
    

    return app

app = create_app()

if __name__ == "__main__":
    import uvicorn
    import os
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)