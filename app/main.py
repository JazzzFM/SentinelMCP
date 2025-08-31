from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional
import logging
from datetime import datetime

from rag.ingest import IngestionService
from rag.retriever import RetrievalService
from agents.orchestrator import AgentOrchestrator
from app.mcp_server import create_mcp_server
from infra.logging import setup_logging, get_event_logger, get_logger

# Setup logging
setup_logging(log_level="INFO")
logger = get_logger("main")
event_logger = get_event_logger()

app = FastAPI(
    title="SentinelMCP",
    description="Multi-Agent RAG with MCP & Compliance (Saptiva-native)",
    version="0.1.0",
)

# Initialize services
logger.info("Initializing SentinelMCP services...")
ingestion_service = IngestionService()
retrieval_service = RetrievalService()
agent_orchestrator = AgentOrchestrator()
mcp_server = create_mcp_server()
logger.info("SentinelMCP services initialized successfully")

class IngestRequest(BaseModel):
    file_path: str
    metadata: Dict[str, Any]

class SearchRequest(BaseModel):
    query: str
    k: Optional[int] = 5

class AskRequest(BaseModel):
    question: str
    k: Optional[int] = 5

class McpCallRequest(BaseModel):
    tool: str
    params: Dict[str, Any]

@app.post("/ingest", summary="Ingest a document")
async def ingest_document(request: IngestRequest):
    try:
        result = ingestion_service.ingest_file(request.file_path, request.metadata)
        return result
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {e}")


@app.post("/search", summary="Search for passages")
async def search_passages(request: SearchRequest):
    passages = retrieval_service.retrieve(request.query, request.k)
    return {"query": request.query, "passages": passages}

@app.post("/ask", summary="Ask a question to the RAG system")
async def ask_question(request: AskRequest):
    response = agent_orchestrator.process_request(request.dict())
    return response

@app.post("/mcp/call", summary="Invoke an MCP tool")
async def call_mcp_tool(request: McpCallRequest):
    if request.tool not in mcp_server.tools:
        raise HTTPException(status_code=404, detail=f"Tool '{request.tool}' not found.")
    
    tool_function = mcp_server.tools[request.tool]
    try:
        result = tool_function(**request.params)
        return {"tool": request.tool, "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error calling tool '{request.tool}': {e}")

@app.get("/healthz", summary="Health check")
async def health_check():
    return {"status": "ok"}
