from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional

from rag.ingest import IngestionService

app = FastAPI(
    title="SentinelMCP",
    description="Multi-Agent RAG with MCP & Compliance (Saptiva-native)",
    version="0.1.0",
)

ingestion_service = IngestionService()

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
        ingestion_service.ingest_file(request.file_path, request.metadata)
        return {"status": "success", "file_path": request.file_path}
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {e}")


@app.post("/search", summary="Search for passages")
async def search_passages(request: SearchRequest):
    # Placeholder for search logic
    return {"query": request.query, "passages": []}

@app.post("/ask", summary="Ask a question to the RAG system")
async def ask_question(request: AskRequest):
    # Placeholder for RAG logic
    return {"question": request.question, "answer": "Placeholder answer."}

@app.post("/mcp/call", summary="Invoke an MCP tool")
async def call_mcp_tool(request: McpCallRequest):
    # Placeholder for MCP tool call logic
    return {"tool": request.tool, "result": "Placeholder result."}

@app.get("/healthz", summary="Health check")
async def health_check():
    return {"status": "ok"}
