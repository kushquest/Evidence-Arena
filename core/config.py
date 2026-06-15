import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    LLM_PROVIDER = "gemini"

    # Google Cloud ADC settings
    GOOGLE_CLOUD_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT", "your-project-id")
    GOOGLE_CLOUD_LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")

    # Active model configuration
    GEMINI_MODEL = "gemini-2.5-flash"

    # PubMed settings
    PUBMED_API_KEY = os.getenv("PUBMED_API_KEY", "")
    MAX_ABSTRACTS = 100 # Increased to 100 for higher fidelity
    MAX_FETCH_LIMIT = 150 # Fetch more initially to filter
    MAX_CONCURRENT_CALLS = 10

    # Debate settings
    MAX_ROUNDS = 3
    JOKER_QUERIES_PER_ROUND = 3

    @classmethod
    def get_pubmed_api_key(cls):
        """Resolves PubMed API key, checking Streamlit Secrets and Env variables."""
        key = os.getenv("PUBMED_API_KEY")
        if key:
            return key
        try:
            import streamlit as st
            if hasattr(st, "secrets") and st.secrets and "PUBMED_API_KEY" in st.secrets:
                return st.secrets["PUBMED_API_KEY"]
        except Exception:
            pass
        return cls.PUBMED_API_KEY

    @classmethod
    def get_gcp_credentials(cls):
        """Resolves GCP credentials and project ID, supporting Streamlit Secrets, local ADC, and Env vars."""
        credentials = None
        project = None
        
        # 1. Try to load from Streamlit Secrets
        try:
            import streamlit as st
            if hasattr(st, "secrets") and st.secrets:
                # Handle gcp_service_account dict
                if "gcp_service_account" in st.secrets:
                    creds_info = dict(st.secrets["gcp_service_account"])
                    if creds_info.get("type") == "authorized_user":
                        from google.oauth2.credentials import Credentials
                        credentials = Credentials.from_authorized_user_info(creds_info)
                        project = creds_info.get("quota_project_id")
                    else:
                        if "private_key" in creds_info:
                            creds_info["private_key"] = creds_info["private_key"].replace("\\n", "\n")
                        from google.oauth2 import service_account
                        credentials = service_account.Credentials.from_service_account_info(creds_info)
                        project = creds_info.get("project_id")
                # Handle gcp_credentials_json string
                elif "gcp_credentials_json" in st.secrets:
                    import json
                    creds_info = json.loads(st.secrets["gcp_credentials_json"])
                    if creds_info.get("type") == "authorized_user":
                        from google.oauth2.credentials import Credentials
                        credentials = Credentials.from_authorized_user_info(creds_info)
                        project = creds_info.get("quota_project_id")
                    else:
                        if "private_key" in creds_info:
                            creds_info["private_key"] = creds_info["private_key"].replace("\\n", "\n")
                        from google.oauth2 import service_account
                        credentials = service_account.Credentials.from_service_account_info(creds_info)
                        project = creds_info.get("project_id")
                
                # Check for location in secrets
                if "GOOGLE_CLOUD_LOCATION" in st.secrets:
                    cls.GOOGLE_CLOUD_LOCATION = st.secrets["GOOGLE_CLOUD_LOCATION"]
                if not project and "GOOGLE_CLOUD_PROJECT" in st.secrets:
                    project = st.secrets["GOOGLE_CLOUD_PROJECT"]
        except Exception as e:
            # Fallback if streamlit is not running or secrets are not defined
            pass

        # 2. Try standard Google ADC fallback
        if not credentials:
            try:
                from google.auth import default
                credentials, auth_project = default()
                if not project:
                    project = auth_project
            except Exception as e:
                # ADC credentials not found or failed
                pass

        # 3. Fallback to env variables or defaults
        if not project:
            project = os.getenv("GOOGLE_CLOUD_PROJECT", cls.GOOGLE_CLOUD_PROJECT)

        if project == "your-project-id" or not project:
            # Try to get from env or default
            project = os.getenv("GOOGLE_CLOUD_PROJECT", "your-project-id")

        return credentials, project


