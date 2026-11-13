"""
===============================================================================
MODULE: ingest.py
PROJECT: OmniRAG Enterprise Agentic Support Chatbot
LAYER: Backend Data Ingestion Layer (PDF Chunking & Vector Upsert)
===============================================================================

DESCRIPTION:
    This module provides the ingestion pipeline for parsing corporate policy 
    PDF documents, implementing Parent-Child hierarchical text splitting, generating 
    3072-dimensional vector embeddings via Gemini, and upserting metadata-rich vector 
    payloads into Pinecone Serverless indices.

KEY RESPONSIBILITIES:
    1. Parsing PDF pages into raw LangChain Document objects via PyPDF.
    2. Splitting raw text into Parent Sections (~2000 chars / 400-500 tokens) with 200 char overlap.
    3. Splitting Parent Sections into Child Chunks (~500 chars / 100-150 tokens) with 50 char overlap.
    4. Linking Child Chunks to Parent Sections via `parent_id` and embedding full `parent_text` into metadata.
    5. Ensuring Pinecone index exists with dimension=3072 and metric="cosine".
    6. Batch upserting embedded vectors and metadata into Pinecone.
===============================================================================
"""

import os
import uuid
from pathlib import Path

from langchain_core.documents import Document
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from pinecone import Pinecone, ServerlessSpec
from pypdf import PdfReader


class SimpleTextSplitter:
    """
    Custom character-based text splitter implementing parent-child chunking parameters.

    ARGUMENTS:
        chunk_size (int): Target maximum character length per chunk (default 2000).
        chunk_overlap (int): Number of overlapping characters between consecutive chunks (default 200).
        separators (list[str] | None): Optional list of separator strings (unused, for interface consistency).
    """

    def __init__(
        self,
        chunk_size: int = 2000,
        chunk_overlap: int = 200,
        separators: list[str] | None = None,
    ) -> None:
        # Store configured maximum chunk character length
        self.chunk_size = chunk_size
        # Store configured chunk overlap character length
        self.chunk_overlap = chunk_overlap

    def split_text(self, text: str) -> list[str]:
        """
        Splits a raw text string into chunks based on chunk_size and chunk_overlap.

        ARGUMENTS:
            text (str): The input text string to divide into chunks.

        RETURNS:
            list[str]: A list of chunk text substrings.
        """
        chunks: list[str] = []
        i = 0
        # Loop through text using step size equal to chunk_size minus chunk_overlap
        while i < len(text):
            # Extract substring slice from current index up to i + chunk_size
            chunks.append(text[i:i + self.chunk_size])
            # Advance sliding window index forward by net stride
            i += self.chunk_size - self.chunk_overlap
            # Exit loop if index reaches or exceeds total text length
            if i >= len(text):
                break
        # Fallback check: if no chunks were created but input text was non-empty, append whole text
        if not chunks and text:
            chunks.append(text)
        return chunks

    def split_documents(self, documents: list[Document]) -> list[Document]:
        """
        Splits a list of Document objects while preserving and copying document metadata.

        ARGUMENTS:
            documents (list[Document]): Input LangChain Document objects to split.

        RETURNS:
            list[Document]: New list of Document objects with split page content and copied metadata.
        """
        docs: list[Document] = []
        # Iterate over each document object in the input list
        for doc in documents:
            # Split the document page content text into string chunks
            texts = self.split_text(doc.page_content)
            # Create a new Document instance for each text chunk, copying parent metadata
            for t in texts:
                docs.append(Document(page_content=t, metadata=doc.metadata.copy()))
        return docs


def process_pdf(file_path: str) -> list[Document]:
    """
    Parses a single PDF file and generates Parent-Child chunked Document objects.

    ARGUMENTS:
        file_path (str): Absolute file path to the PDF document to process.

    RETURNS:
        list[Document]: A list of child Document objects enriched with parent_id, parent_text,
                        section_title, page_number, and source metadata.
    """
    # Step 1: Open and read PDF file using PyPDF reader
    reader = PdfReader(file_path)
    
    # Step 2: Initialize Parent Splitter (2000 chars / ~400-500 tokens, 200 char overlap)
    parent_splitter = SimpleTextSplitter(
        chunk_size=2000,
        chunk_overlap=200
    )
    
    # Step 3: Initialize Child Splitter (500 chars / ~100-150 tokens, 50 char overlap)
    child_splitter = SimpleTextSplitter(
        chunk_size=500,
        chunk_overlap=50
    )
    
    # Step 4: Extract page-level raw text into LangChain Document objects
    raw_docs: list[Document] = []
    for i, page in enumerate(reader.pages):
        # Extract text string from page
        text = page.extract_text()
        # Verify text string is non-empty before storing
        if text:
            raw_docs.append(
                Document(
                    page_content=text,
                    metadata={
                        "page_number": i + 1,                     # 1-indexed page number
                        "source": os.path.basename(file_path),    # Base PDF filename string
                    }
                )
            )
            
    # Step 5: Split raw page documents into Parent Section documents (~2000 chars)
    parent_docs = parent_splitter.split_documents(raw_docs)
    
    # Step 6: Divide each Parent Section into Child Chunks and attach Parent metadata
    child_docs: list[Document] = []
    for p_doc in parent_docs:
        # Generate a unique UUID identifier for this parent section
        parent_id = str(uuid.uuid4())
        
        # Extract first non-empty line (up to 50 chars) as the section title
        first_line = p_doc.page_content.split('\n')[0][:50].strip()
        
        # Sub-split the parent section into smaller child chunks (~500 chars)
        children = child_splitter.split_documents([p_doc])
        for c_doc in children:
            # Update child chunk metadata to attach parent section context and section title
            c_doc.metadata.update({
                "parent_id": parent_id,               # UUID string linking child to parent
                "parent_text": p_doc.page_content,    # Full parent section text passage
                "section_title": first_line           # Extracted section title
            })
            child_docs.append(c_doc)
            
    return child_docs


def ingest_pdfs(data_dir: str, index_name: str = "northwind-gadgets") -> None:
    """
    Ingests all PDF policy files from data_dir, embeds child chunks, and upserts to Pinecone.

    ARGUMENTS:
        data_dir (str): Directory path containing source policy PDF files.
        index_name (str): Pinecone index target name (default 'northwind-gadgets').

    RETURNS:
        None: Creates Pinecone index if missing and upserts vector embeddings.
    """
    # Fetch Pinecone API key from environment variables
    api_key = os.getenv("PINECONE_API_KEY")
    # Initialize Pinecone SDK client
    pc = Pinecone(api_key=api_key)
    
    # Step 1: Ensure Pinecone index exists with exact 3072 dimension spec (matching gemini-embedding-001)
    if not pc.has_index(index_name):
        pc.create_index(
            name=index_name,
            dimension=3072,                # 3072 dimensions matching Google gemini-embedding-001 output
            metric="cosine",                # Cosine distance metric for dense vector similarity
            spec=ServerlessSpec(
                cloud="aws",
                region="us-east-1"
            )
        )
        
    # Step 2: Connect to Pinecone index instance
    index = pc.Index(index_name)
    
    # Step 3: Initialize Google Generative AI Embeddings wrapper for gemini-embedding-001 model
    embeddings = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001")
    
    # Step 4: Scan data directory and process all PDF documents
    data_path = Path(data_dir)
    all_chunks: list[Document] = []
    for pdf_file in data_path.glob("*.pdf"):
        # Append chunk documents from each PDF to master chunks list
        all_chunks.extend(process_pdf(str(pdf_file)))
        
    # Check if any chunk documents were generated
    if not all_chunks:
        print("No chunks found.")
        return
        
    # Step 5: Upsert vector embeddings to Pinecone in batches of 100
    batch_size = 100
    for i in range(0, len(all_chunks), batch_size):
        # Extract current batch slice from chunks list
        batch = all_chunks[i:i + batch_size]
        texts = [doc.page_content for doc in batch]
        metadatas = [doc.metadata for doc in batch]
        ids = [str(uuid.uuid4()) for _ in batch]
        
        # Generate 3072-dimensional vector embeddings for text batch
        embeds = embeddings.embed_documents(texts)
        
        # Combine IDs, vector embeddings, and metadata into Pinecone upsert tuples
        vectors = list(zip(ids, embeds, metadatas))
        
        # Upsert vector batch into Pinecone vector database
        index.upsert(vectors=vectors)


# Standalone execution block for data ingestion
if __name__ == "__main__":
    from dotenv import load_dotenv
    # Load environment variables from backend/.env file
    load_dotenv()
    
    # Resolve absolute path to data directory
    data_dir = Path(__file__).resolve().parent.parent.parent / "data"
    
    # Read Pinecone index target name from environment variable (default 'northwind-gadgets')
    index_name = os.getenv("PINECONE_INDEX_NAME") or "northwind-gadgets"
    
    # Execute full PDF ingestion pipeline
    ingest_pdfs(str(data_dir), index_name.lower().strip())
