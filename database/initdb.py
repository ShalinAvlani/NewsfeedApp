# initialize database and set schema for table
import weaviate
import weaviate.classes.config as wc
from os import getenv
from datamodels.articleobjects import getLogger

logger = getLogger("DB Initialization")

with weaviate.connect_to_local(host=getenv("DB_HOST"), headers={"X-OpenAI-Api-Key":getenv("OPENAI_API_KEY")}) as client:
    if not client.collections.exists(getenv("COLLECTION_NAME")):
        client.collections.create(
            vectorizer_config=wc.Configure.Vectorizer.text2vec_openai(),
            generative_config=wc.Configure.Generative.openai(),
            name=getenv("COLLECTION_NAME"),
            properties=[
                wc.Property(name="publishedAt", data_type=wc.DataType.DATE),
                wc.Property(name="topics", data_type=wc.DataType.TEXT_ARRAY),
                wc.Property(name="summary", data_type=wc.DataType.TEXT),
                wc.Property(name="fullStory", data_type=wc.DataType.TEXT),
                wc.Property(name="url", data_type=wc.DataType.TEXT, skip_vectorization=True),
                wc.Property(name="title", data_type=wc.DataType.TEXT),
                wc.Property(name="author", data_type=wc.DataType.TEXT, skip_vectorization=True)
            ]
        )
        logger.info("Initialized")
    else:
        logger.info("Already initialized")