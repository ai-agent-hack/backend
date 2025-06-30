from fastapi import APIRouter, HTTPException, status
from typing import Any
import json
import os
import dotenv
from google.oauth2 import service_account
import vertexai
from vertexai.generative_models import GenerativeModel, GenerationConfig

dotenv.load_dotenv()

router = APIRouter()


def get_vertex_credentials():
    """Get Google Cloud credentials for Vertex AI"""
    try:

        # Try to get credentials from GOOGLE_APPLICATION_CREDENTIALS
        service_account_data = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        if service_account_data:
            # Check if it's a JSON string (starts with '{')
            if service_account_data.strip().startswith("{"):
                credentials_info = json.loads(service_account_data)
                credentials = service_account.Credentials.from_service_account_info(
                    credentials_info
                )
                return credentials
            # If it's a file path and the file exists
            elif os.path.exists(service_account_data):
                credentials = service_account.Credentials.from_service_account_file(
                    service_account_data
                )
                return credentials

        # If no explicit credentials, let Google Auth use default
        return None

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to load Google Cloud credentials: {str(e)}",
        )


@router.post("/generate", response_model=str, status_code=status.HTTP_200_OK)
async def generate_text() -> Any:
    """
    Generate text using Vertex AI Gemini model
    """
    try:
        project_id = os.getenv("GOOGLE_PROJECT_ID") or os.getenv("GOOGLE_CLOUD_PROJECT")
        if not project_id:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="GOOGLE_PROJECT_ID or GOOGLE_CLOUD_PROJECT environment variable is not set",
            )

        # Get credentials
        credentials = get_vertex_credentials()

        # Initialize Vertex AI with proper credentials
        if credentials:
            vertexai.init(
                project=project_id, location="us-central1", credentials=credentials
            )
        else:
            vertexai.init(project=project_id, location="us-central1")

        model = GenerativeModel("gemini-2.5-flash")

        generation_config = GenerationConfig(
            temperature=0.4,
            top_p=0.95,
            max_output_tokens=1024,
        )

        response = model.generate_content(
            "量子コンピュータを高校生に分かりやすく解説してください。",
            generation_config=generation_config,
        )

        return response.text

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate text: {str(e)}",
        )
