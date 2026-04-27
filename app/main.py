from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from .signal_ws import signal_stream
from .sim_engine import start_simulation_thread
app = FastAPI()

# To run the app, use the following command:
# uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
# This will start the FastAPI server on port 8001 and enable hot-reloading for development.
# You can access the API documentation at http://localhost:8001/docs
# The WebSocket endpoint for streaming signals will be available at ws://localhost:8001/ws/signal
# CORS middleware to allow cross-origin requests from the frontend
# In production, you should restrict the allowed origins to your frontend domain for security reasons.
# For development, we allow all origins with allow_origins=["*"].
# In production, consider setting allow_origins to a specific list of allowed domains, e.g.:
# allow_origins=["https://your-frontend-domain.com"]
# For more information on CORS and FastAPI, see the documentation:
# https://fastapi.tiangolo.com/tutorial/cors/   
# For production deployment, consider using a process manager like Supervisor or systemd to manage 
# the Gunicorn process and ensure it restarts automatically if it crashes. Additionally, 
# you may want to set up logging for Gunicorn to capture application logs for monitoring and debugging 
# purposes.
# gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8001 
# This command will start the FastAPI application using Gunicorn with 4 worker processes and bind it to 
# port 8001. Adjust the number of workers and port as needed for your deployment environment.
# For more information on deploying FastAPI with Gunicorn, see the documentation:
# https://fastapi.tiangolo.com/deployment/


# Inisialisasi DB account_state
from .db import init_db
from .routes import router
app.include_router(router)

# Start simulation thread on startup
@app.on_event("startup")
def startup_event():
    init_db()
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
