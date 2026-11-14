"""Start the engine:  python -m nlie  [--host 0.0.0.0] [--port 8000]"""
import argparse

import uvicorn

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    a = ap.parse_args()
    uvicorn.run("nlie.app:app", host=a.host, port=a.port, log_level="info")
