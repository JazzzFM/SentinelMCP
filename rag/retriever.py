from typing import List, Dict, Any, Optional
import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
import logging
import os

logger = logging.getLogger(__name__)

class RetrievalService:
    def __init__(self, 
                 vector_store_path: str = "./chroma_db",
                 collection_name: str = "documents",
                 embedding_model: str = "all-MiniLM-L6-v2"):
        """
        Initialize retrieval service with ChromaDB and SentenceTransformers
        """
        self.vector_store_path = vector_store_path
        self.collection_name = collection_name
        
        # Initialize ChromaDB client
        self.client = chromadb.PersistentClient(
            path=vector_store_path,
            settings=Settings(anonymized_telemetry=False)
        )
        
        # Initialize embedding model
        self.embedding_model = SentenceTransformer(embedding_model)
        
        # Get or create collection
        try:
            self.collection = self.client.get_collection(collection_name)
            logger.info(f"Loaded existing collection: {collection_name}")
        except ValueError:
            self.collection = self.client.create_collection(
                name=collection_name,
                metadata={"hnsw:space": "cosine"}
            )
            logger.info(f"Created new collection: {collection_name}")

    def add_documents(self, documents: List[Dict[str, Any]]) -> None:
        """
        Add documents to the vector store
        """
        if not documents:
            logger.warning("No documents to add")
            return
            
        texts = []
        metadatas = []
        ids = []
        
        for i, doc in enumerate(documents):
            content = doc.get('content', '')
            metadata = doc.get('metadata', {})
            doc_id = doc.get('id', f"doc_{i}_{hash(content[:100])}")
            
            texts.append(content)
            metadatas.append(metadata)
            ids.append(str(doc_id))
        
        # Generate embeddings
        embeddings = self.embedding_model.encode(texts).tolist()
        
        # Add to ChromaDB
        self.collection.add(
            documents=texts,
            metadatas=metadatas,
            ids=ids,
            embeddings=embeddings
        )
        
        logger.info(f"Added {len(documents)} documents to vector store")

    def retrieve(self, query: str, k: int = 5, metadata_filter: Optional[Dict] = None) -> List[Dict[str, Any]]:
        """
        Retrieves k most relevant documents for a given query using semantic search
        """
        try:
            # Generate query embedding
            query_embedding = self.embedding_model.encode([query]).tolist()[0]
            
            # Prepare query parameters
            query_params = {
                "query_embeddings": [query_embedding],
                "n_results": k
            }
            
            # Add metadata filter if provided
            if metadata_filter:
                query_params["where"] = metadata_filter
            
            # Query the collection
            results = self.collection.query(**query_params)
            
            # Format results
            formatted_results = []
            if results['documents'] and results['documents'][0]:
                for i in range(len(results['documents'][0])):
                    result = {
                        "id": results['ids'][0][i],
                        "content": results['documents'][0][i],
                        "metadata": results['metadatas'][0][i] if results['metadatas'][0] else {},
                        "distance": results['distances'][0][i] if results.get('distances') else None,
                        "source": results['metadatas'][0][i].get('source', 'unknown') if results['metadatas'][0] else 'unknown'
                    }
                    formatted_results.append(result)
            
            logger.info(f"Retrieved {len(formatted_results)} documents for query: {query[:50]}...")
            return formatted_results
            
        except Exception as e:
            logger.error(f"Error during retrieval: {e}")
            return []

    def get_collection_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the current collection
        """
        try:
            count = self.collection.count()
            return {
                "collection_name": self.collection_name,
                "document_count": count,
                "vector_store_path": self.vector_store_path
            }
        except Exception as e:
            logger.error(f"Error getting collection stats: {e}")
            return {"error": str(e)}

    def delete_collection(self) -> bool:
        """
        Delete the current collection (use with caution)
        """
        try:
            self.client.delete_collection(self.collection_name)
            logger.info(f"Deleted collection: {self.collection_name}")
            return True
        except Exception as e:
            logger.error(f"Error deleting collection: {e}")
            return False
