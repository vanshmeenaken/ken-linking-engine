from fastapi import FastAPI

from config.settings import API_HOST, API_PORT

app = FastAPI(title="KEN Interlinking Engine")


@app.get("/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("api.main:app", host=API_HOST, port=API_PORT, reload=True)
