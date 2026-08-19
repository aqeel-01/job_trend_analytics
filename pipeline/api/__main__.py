"""Run the API with uvicorn: python -m pipeline.api"""

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "pipeline.api.app:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
    )
