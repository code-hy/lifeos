import os
import logging
import google.generativeai as genai

logger = logging.getLogger("LifeOS.Memory")

class GeminiEmbeddingFunction:
    def __init__(self, api_key=None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if self.api_key:
            genai.configure(api_key=self.api_key)

    def name(self):
        return "GeminiEmbeddingFunction"

    def _embed(self, input: list[str]) -> list[list[float]]:
        if self.api_key:
            try:
                response = genai.embed_content(
                    model="models/text-embedding-004",
                    contents=input,
                    task_type="retrieval_document"
                )
                embeddings = response.get('embedding', [])
                if embeddings and isinstance(embeddings[0], list):
                    return embeddings
                elif embeddings and isinstance(embeddings[0], (int, float)):
                    return [embeddings]
                elif 'embedding' in response:
                    return response['embedding']
            except Exception as e:
                logger.warning(f"Gemini embedding failed: {e}. Falling back to deterministic hash embedding.")
        embeddings = []
        for text in input:
            text_str = str(text) if not isinstance(text, str) else text
            vec = [0.0] * 768
            for i, ch in enumerate(text_str):
                idx = (i * 31) % 768
                vec[idx] += ord(ch) * (1.0 / (i + 1))
            norm = sum(x * x for x in vec) ** 0.5
            if norm > 0:
                vec = [x / norm for x in vec]
            embeddings.append(vec)
        return embeddings

    def __call__(self, input: list[str]) -> list[list[float]]:
        return self._embed(input)

    def embed_query(self, input: str | list[str]) -> list[float]:
        if isinstance(input, list):
            return self._embed(input)[0]
        return self._embed([input])[0]

class LongTermMemory:
    def __init__(self):
        self.chroma_host = os.getenv("CHROMA_DB_HOST")
        self.chroma_port = os.getenv("CHROMA_DB_PORT", "8000")
        
        # Determine local directory path
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.persist_dir = os.path.join(base_dir, "data", "chroma")
        os.makedirs(os.path.dirname(self.persist_dir), exist_ok=True)

        self.api_key = os.getenv("GEMINI_API_KEY")
        self.embedding_function = GeminiEmbeddingFunction(self.api_key)
        
        self.active = False
        self.fallback_db = []

        try:
            import chromadb
            if self.chroma_host:
                logger.info(f"Connecting to remote ChromaDB at {self.chroma_host}:{self.chroma_port}")
                self.client = chromadb.HttpClient(host=self.chroma_host, port=int(self.chroma_port))
            else:
                logger.info(f"Connecting to local ChromaDB at {self.persist_dir}")
                self.client = chromadb.PersistentClient(path=self.persist_dir)
            
            # Get or create collection with custom embedding function
            self.collection = self.client.get_or_create_collection(
                name="user_preferences",
                metadata={"hnsw:space": "cosine"},
                embedding_function=self.embedding_function
            )
            self.active = True
            logger.info("ChromaDB memory agent initialized successfully.")
        except Exception as e:
            logger.error(f"Failed to initialize ChromaDB: {e}. Falling back to in-memory/JSON storage.")
            self.active = False

    def add_preference(self, key: str, value: str):
        text = f"User preference: {key} is {value}"
        doc_id = f"pref_{key}"
        if self.active:
            try:
                self.collection.upsert(
                    documents=[text],
                    metadatas=[{"key": key, "value": value, "type": "preference"}],
                    ids=[doc_id]
                )
                logger.info(f"Saved preference to ChromaDB: {key} = {value}")
            except Exception as e:
                logger.error(f"Error saving to ChromaDB: {e}. Saving to fallback.")
                self._add_fallback(key, value)
        else:
            self._add_fallback(key, value)

    def _add_fallback(self, key: str, value: str):
        for item in self.fallback_db:
            if item["key"] == key:
                item["value"] = value
                item["text"] = f"User preference: {key} is {value}"
                return
        self.fallback_db.append({
            "key": key,
            "value": value,
            "text": f"User preference: {key} is {value}"
        })
        logger.info(f"Saved preference to fallback memory: {key} = {value}")

    def fetch_context(self, query: str, n_results: int = 3) -> str:
        if self.active:
            try:
                # Query ChromaDB
                results = self.collection.query(
                    query_texts=[query],
                    n_results=n_results
                )
                documents = results.get("documents", [])
                if documents and len(documents[0]) > 0:
                    return "\n".join(documents[0])
            except Exception as e:
                logger.error(f"Error querying ChromaDB: {e}. Querying fallback.")
        
        # Fallback keyword/distance matching
        matched = []
        words = query.lower().split()
        for item in self.fallback_db:
            text = item["text"]
            score = sum(1 for w in words if w in text.lower())
            if score > 0 or not words:
                matched.append((score, text))
        
        matched.sort(key=lambda x: x[0], reverse=True)
        return "\n".join(text for _, text in matched[:n_results])

    def get_all_preferences(self) -> list[dict]:
        if self.active:
            try:
                results = self.collection.get()
                prefs = []
                for meta in results.get("metadatas", []):
                    if meta:
                        prefs.append(meta)
                return prefs
            except Exception as e:
                logger.error(f"Error listing preferences from ChromaDB: {e}")
        return [{"key": item["key"], "value": item["value"]} for item in self.fallback_db]

    def clear_memory(self):
        if self.active:
            try:
                # Delete all
                ids = self.collection.get().get("ids", [])
                if ids:
                    self.collection.delete(ids=ids)
                logger.info("ChromaDB memory cleared.")
            except Exception as e:
                logger.error(f"Error clearing ChromaDB memory: {e}")
        self.fallback_db = []
        logger.info("Fallback memory cleared.")
