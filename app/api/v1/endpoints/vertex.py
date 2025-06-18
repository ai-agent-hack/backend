from fastapi import APIRouter, status
from typing import Any

import vertexai
from vertexai.generative_models import GenerativeModel, GenerationConfig

import os
import dotenv

dotenv.load_dotenv()

router = APIRouter()

@router.post("/generate", response_model=str, status_code=status.HTTP_201_CREATED)
async def generate_text() -> Any:
    vertexai.init(project=os.getenv("GOOGLE_PROJECT_ID"), location="us-central1")
    model = GenerativeModel("gemini-2.0-flash")

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



