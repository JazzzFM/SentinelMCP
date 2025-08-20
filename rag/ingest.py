import os
from typing import Any, Dict, List
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import UnstructuredFileLoader
# from langchain_community.vectorstores import Chroma
# from langchain_community.embeddings import SaptivaEmbeddings # Assuming saptiva provides this

class IngestionService:
    def __init__(self, vector_store_path: str = "./chroma_db"):
        self.text_splitter = RecursiveCharacterTextSplitter(chunk_size=1500, chunk_overlap=150)
        # self.embedding_function = SaptivaEmbeddings(model_name="Saptiva Embed") # Placeholder
        # self.vector_store = Chroma(persist_directory=vector_store_path, embedding_function=self.embedding_function)

    def ingest_file(self, file_path: str, metadata: Dict[str, Any]) -> None:
        """
        Ingests a single file, chunks it, and stores it in the vector store.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        loader = UnstructuredFileLoader(file_path)
        documents = loader.load()

        chunks = self.text_splitter.split_documents(documents)
        
        # Add metadata to each chunk
        for chunk in chunks:
            chunk.metadata.update(metadata)

        # self.vector_store.add_documents(chunks) # Placeholder for embedding and storing
        print(f"Ingested and chunked {len(chunks)} documents from {file_path}")
