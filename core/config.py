import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    LLM_PROVIDER = "gemini"

    # Google Cloud ADC settings
    GOOGLE_CLOUD_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT", "your-project-id")
    GOOGLE_CLOUD_LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")

    # Model will be set by UI
    GEMINI_MODEL = None

    # PubMed settings
    PUBMED_API_KEY = os.getenv("PUBMED_API_KEY", "")
    MAX_ABSTRACTS = 100 # Increased to 100 for higher fidelity
    MAX_FETCH_LIMIT = 150 # Fetch more initially to filter
    MAX_CONCURRENT_CALLS = 10

    # Debate settings
    MAX_ROUNDS = 3
    JOKER_QUERIES_PER_ROUND = 3

    @classmethod
    def get_available_gemini_models(cls) -> list:
        """Dynamically fetch available, sorted Gemini models from Vertex AI."""
        try:
            from google import genai
            from google.auth import default
            
            credentials, project = default()
            client = genai.Client(
                vertexai=True, 
                project=cls.GOOGLE_CLOUD_PROJECT, 
                location=cls.GOOGLE_CLOUD_LOCATION,
                credentials=credentials
            )
            
            available = []
            for m in client.models.list():
                name = m.name
                if 'gemini' in name.lower() and 'embedding' not in name.lower():
                    display_name = name.split('/')[-1]
                    available.append(display_name)
            
            available = list(set(available))
            available.sort(key=lambda name: (
                'pro' not in name.lower(), 
                'flash' not in name.lower(), 
                'preview' in name.lower(),
                name
            ))
            return available if available else ['gemini-2.0-flash', 'gemini-1.5-pro']
        except Exception as e:
            print(f"⚠️ Could not fetch Gemini model list: {e}")
            return ['gemini-2.0-flash', 'gemini-1.5-pro']
