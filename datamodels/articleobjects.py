from pydantic import BaseModel, Field
from datetime import datetime
from typing import List
import logging
import sys
from os import getenv

class Article(BaseModel):
    uuid: str = Field(default="")
    author: str = Field(default="")
    title: str
    url: str
    publishedAt: datetime
    fullStory: str = Field(default="")
    summary: str = Field(default="")
    topics: List[str] = Field(default=[])

def getLogger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    if not logger.hasHandlers():
        formatter = logging.Formatter("[%(asctime)s] %(levelname)s %(filename)s %(funcName)s | %(message)s")
        sh = logging.StreamHandler(sys.stdout)
        sh.setFormatter(formatter)
        sh.setLevel(logging.INFO)
        logger.addHandler(sh)
    logger.propagate = False
    return logger

def instantiateBaseLLM():
    from langchain_openai import ChatOpenAI
    from langchain_anthropic import ChatAnthropic
    from openai import RateLimitError
    llm_openai = ChatOpenAI(verbose=True, model_name=getenv("OPENAI_DEFAULT"), max_retries=0)
    llm_anthropic = ChatAnthropic(verbose=True, model_name=getenv("ANTHROPIC_DEFAULT"))
    llm = llm_openai.with_fallbacks([llm_anthropic], exceptions_to_handle=[RateLimitError])
    return llm

def connectToDB():
    import weaviate
    client = weaviate.connect_to_local(host=getenv("DB_HOST"), headers={"X-OpenAI-Api-Key": getenv("OPENAI_API_KEY")})
    collection = client.collections.get(getenv("COLLECTION_NAME"))
    return collection