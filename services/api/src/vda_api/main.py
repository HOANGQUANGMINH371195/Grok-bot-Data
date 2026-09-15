from fastapi import FastAPI

app = FastAPI(title="VDaAgent API", version="0.1.0")


@app.get("/healthz", include_in_schema=False)
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/readyz", include_in_schema=False)
def readyz() -> dict[str, str]:
    return {"status": "not_ready", "reason": "M1 dependencies are not configured"}
