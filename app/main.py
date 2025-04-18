from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from app.reddit_agent import RedditAgent
import logging
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Reddit Search Agent")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    prompt: str
    search_results: list | None = None

class ChatResponse(BaseModel):
    message: str
    results: list | None = None
    post_ids: list | None = None
    download_file: str | None = None
    logs: list

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    try:
        logger.info(f"Processing prompt: {request.prompt}")
        logger.info("Initializing RedditAgent")
        agent = RedditAgent()
        logger.info(f"Agent initialized with logs: {agent.logs}")
        logger.info("Handling prompt")
        response = agent.handle_prompt(
            prompt=request.prompt,
            search_results=request.search_results
        )
        logger.info(f"Response: {response}")
        return response
    except Exception as e:
        logger.error(f"Error processing prompt: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/files/{filename}")
async def get_file(filename: str):
    file_path = filename
    if not os.path.exists(file_path):
        logger.error(f"File not found: {file_path}")
        raise HTTPException(status_code=404, detail="File not found")
    logger.info(f"Serving file: {file_path}")
    return FileResponse(file_path, media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', filename=filename)

@app.get("/")
async def root():
    return {"message": "Reddit Search Agent API"}