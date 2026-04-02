import os
from typing import Optional, List
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_community.utilities import SerpAPIWrapper
from langchain_core.documents import Document

load_dotenv()

class KnowledgeBaseService:
    """
    Singleton-style service managing LLM, Vector DB, and Web Search.
    """
    _instance = None
    
    def __new__(cls):
        # Proper Singleton pattern
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self.embeddings = None
        self.vector_db = None
        self.llm = None
        self.serpapi = None
        self._initialize_services()
        self._initialized = True

    def _initialize_services(self):
        """Initializes AI models, vector DB, and search tools."""
        print("--- Initializing AI Services ---")
        
        # Validate critical env vars
        groq_key = os.getenv("GROQ_API_KEY")
        if not groq_key:
            raise ValueError("GROQ_API_KEY not found in environment variables")
        
        # 1. Embeddings
        print("Loading embeddings...")
        self.embeddings = HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L6-v2"
        )
        
        # 2. FAISS Vector DB
        index_path = "app/faiss_index_urban_planning"
        if os.path.exists(index_path):
            print(f"Loading Vector DB from {index_path}...")
            # SECURITY: Only use allow_dangerous_deserialization if you trust the index source
            self.vector_db = FAISS.load_local(
                index_path,
                self.embeddings,
                allow_dangerous_deserialization=True
            )
            print("✓ Vector DB loaded")
        else:
            raise FileNotFoundError(f"Vector DB not found at {index_path}")

        # 3. LLM
        print("Initializing Groq LLM...")
        self.llm = ChatGroq(
            model_name="openai/gpt-oss-120b",  # or "llama-3.3-70b-versatile" for cheaper option
            groq_api_key=groq_key,
            temperature=0.2,
            streaming=True
        )
        print("✓ LLM ready")

        # 4. Web Search (Optional but recommended)
        serp_key = os.getenv("SERPAPI_API_KEY")
        if serp_key:
            self.serpapi = SerpAPIWrapper(serpapi_api_key=serp_key)
            print("✓ SerpAPI ready")
        else:
            print("⚠ SerpAPI key not found - web search disabled")

    def query_vector_db(self, query: str, k: int = 5) -> List[Document]:
        """Retrieve relevant documents from vector DB."""
        if not self.vector_db:
            return []
        retriever = self.vector_db.as_retriever(search_kwargs={"k": k})
        return retriever.invoke(query)

    def web_search(self, query: str) -> str:
        """Perform web search via SerpAPI."""
        if not self.serpapi:
            return "Error: Web search not configured"
        try:
            return self.serpapi.run(query)
        except Exception as e:
            return f"Web search error: {str(e)}"

    def get_llm(self):
        """Get the initialized LLM."""
        return self.llm

# Global instance
kb_service = KnowledgeBaseService()