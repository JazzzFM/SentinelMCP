import os
import mimetypes
from typing import Any, Dict, List, Optional
from pathlib import Path
import logging
from datetime import datetime
import hashlib

# Document processing imports
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import (
    UnstructuredFileLoader, 
    PyPDFLoader,
    TextLoader,
    CSVLoader
)
from langchain.schema import Document

# Import our retrieval service for vector storage
from .retriever import RetrievalService

logger = logging.getLogger(__name__)

class IngestionService:
    def __init__(self, 
                 vector_store_path: str = "./chroma_db",
                 chunk_size: int = 1500,
                 chunk_overlap: int = 150):
        """
        Initialize ingestion service with document processing and vector storage
        """
        self.vector_store_path = vector_store_path
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size, 
            chunk_overlap=chunk_overlap
        )
        
        # Initialize retrieval service for vector storage
        self.retrieval_service = RetrievalService(vector_store_path)
        
        # Supported file types
        self.supported_extensions = {'.txt', '.pdf', '.csv', '.md', '.json', '.xml'}

    def _get_file_loader(self, file_path: str):
        """
        Get appropriate loader based on file extension
        """
        file_ext = Path(file_path).suffix.lower()
        
        if file_ext == '.pdf':
            return PyPDFLoader(file_path)
        elif file_ext == '.csv':
            return CSVLoader(file_path)
        elif file_ext in ['.txt', '.md', '.json', '.xml']:
            return TextLoader(file_path, encoding='utf-8')
        else:
            # Fallback to UnstructuredFileLoader
            return UnstructuredFileLoader(file_path)

    def _generate_document_id(self, content: str, file_path: str) -> str:
        """
        Generate unique document ID based on content and file path
        """
        content_hash = hashlib.md5(content.encode()).hexdigest()[:8]
        file_hash = hashlib.md5(file_path.encode()).hexdigest()[:8]
        return f"{file_hash}_{content_hash}"

    def _extract_text_from_file(self, file_path: str) -> List[Document]:
        """
        Extract text from file using appropriate loader
        """
        try:
            loader = self._get_file_loader(file_path)
            documents = loader.load()
            logger.info(f"Loaded {len(documents)} documents from {file_path}")
            return documents
        except Exception as e:
            logger.error(f"Error loading file {file_path}: {e}")
            raise

    def _prepare_chunks_for_storage(self, chunks: List[Document], base_metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Prepare document chunks for vector storage
        """
        prepared_docs = []
        
        for i, chunk in enumerate(chunks):
            # Combine base metadata with chunk metadata
            combined_metadata = {**base_metadata, **chunk.metadata}
            combined_metadata.update({
                'chunk_index': i,
                'chunk_length': len(chunk.page_content),
                'ingestion_timestamp': datetime.now().isoformat()
            })
            
            # Generate unique ID for chunk
            doc_id = self._generate_document_id(chunk.page_content, base_metadata.get('source', 'unknown'))
            
            prepared_doc = {
                'id': f"{doc_id}_chunk_{i}",
                'content': chunk.page_content,
                'metadata': combined_metadata
            }
            
            prepared_docs.append(prepared_doc)
        
        return prepared_docs

    def ingest_file(self, file_path: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Ingests a single file, chunks it, and stores it in the vector store.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        # Check if file type is supported
        file_ext = Path(file_path).suffix.lower()
        if file_ext not in self.supported_extensions and file_ext:
            logger.warning(f"File type {file_ext} may not be fully supported")

        # Prepare base metadata
        base_metadata = metadata or {}
        base_metadata.update({
            'source': file_path,
            'filename': Path(file_path).name,
            'file_extension': file_ext,
            'file_size': os.path.getsize(file_path),
            'mime_type': mimetypes.guess_type(file_path)[0]
        })

        try:
            # Extract text from file
            documents = self._extract_text_from_file(file_path)
            
            # Split into chunks
            chunks = self.text_splitter.split_documents(documents)
            
            # Prepare chunks for storage
            prepared_docs = self._prepare_chunks_for_storage(chunks, base_metadata)
            
            # Store in vector database
            self.retrieval_service.add_documents(prepared_docs)
            
            result = {
                "status": "success",
                "file_path": file_path,
                "chunks_created": len(chunks),
                "documents_processed": len(documents),
                "total_characters": sum(len(chunk.page_content) for chunk in chunks)
            }
            
            logger.info(f"Successfully ingested {file_path}: {len(chunks)} chunks created")
            return result
            
        except Exception as e:
            logger.error(f"Error ingesting file {file_path}: {e}")
            raise

    def ingest_directory(self, directory_path: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Ingest all supported files from a directory
        """
        if not os.path.isdir(directory_path):
            raise NotADirectoryError(f"Directory not found: {directory_path}")
        
        results = {
            "total_files": 0,
            "successful_files": 0,
            "failed_files": 0,
            "total_chunks": 0,
            "files_processed": [],
            "errors": []
        }
        
        # Find all supported files
        for file_path in Path(directory_path).rglob("*"):
            if file_path.is_file() and file_path.suffix.lower() in self.supported_extensions:
                results["total_files"] += 1
                
                try:
                    # Add directory info to metadata
                    file_metadata = metadata.copy() if metadata else {}
                    file_metadata['directory'] = str(file_path.parent)
                    
                    result = self.ingest_file(str(file_path), file_metadata)
                    
                    results["successful_files"] += 1
                    results["total_chunks"] += result["chunks_created"]
                    results["files_processed"].append({
                        "file": str(file_path),
                        "chunks": result["chunks_created"]
                    })
                    
                except Exception as e:
                    results["failed_files"] += 1
                    results["errors"].append({
                        "file": str(file_path),
                        "error": str(e)
                    })
                    logger.error(f"Failed to ingest {file_path}: {e}")
        
        logger.info(f"Directory ingestion complete: {results['successful_files']}/{results['total_files']} files processed")
        return results

    def get_ingestion_stats(self) -> Dict[str, Any]:
        """
        Get statistics about ingested documents
        """
        return self.retrieval_service.get_collection_stats()
