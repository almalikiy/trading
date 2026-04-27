from fastapi import FastAPI, WebSocket
from .routes import router
from fastapi.middleware.cors import CORSMiddleware
from .signal_ws import signal_stream
from .sim_engine import start_simulation_thread
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(router)

# Start simulation thread on startup
@app.on_event("startup")
def startup_event():
    start_simulation_thread()

@app.get("/")
def root():
    return {"message": "Trading Signal API"}


from fastapi import WebSocketDisconnect

@app.websocket("/ws/signal")
async def ws_signal(websocket: WebSocket):
    try:
        await signal_stream(websocket)
    except WebSocketDisconnect:
        pass
