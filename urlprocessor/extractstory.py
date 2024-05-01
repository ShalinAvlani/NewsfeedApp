from kafka import KafkaConsumer, KafkaProducer
from os import getenv
from datamodels.articleobjects import Article, getLogger, instantiateBaseLLM, connectToDB
from langchain_community.document_loaders.web_base import WebBaseLoader
from langchain.prompts import SystemMessagePromptTemplate, HumanMessagePromptTemplate, ChatPromptTemplate
import redis
import asyncio

async def main():
    logger = getLogger(__name__)

    r = redis.Redis(host=getenv("REDIS_HOST"), port=getenv("REDIS_PORT"), decode_responses=True)

    bootstrap_server: str = getenv("KAFKA_HOST")+":"+getenv("KAFKA_PORT")

    consumer = KafkaConsumer(bootstrap_servers=bootstrap_server, client_id=getenv("KAFKA_URL_CONSUMER"), auto_offset_reset=getenv("OFFSET_OPTION"))
    consumer.subscribe(topics=[getenv("KAFKA_URL_TOPIC")])
    logger.info("Instantiated consumer and subscribed")

    producer = KafkaProducer(bootstrap_servers=bootstrap_server, client_id=getenv("KAFKA_FULL_STORY_PRODUCER"))
    logger.info("Instantiated producer")

    collection = connectToDB()
    logger.info("Connected to collection")

    llm = instantiateBaseLLM()

    sysPrompt = SystemMessagePromptTemplate.from_template("You need to extract the article text from the text of a web document. You will do this by removing text that doesn't make sense in the text document provided.")
    humPrompt = HumanMessagePromptTemplate.from_template("{article_text}")
    chatPrompt = ChatPromptTemplate.from_messages([sysPrompt, humPrompt])

    counter = 0
    while True:
        messages = consumer.poll(timeout_ms=0, max_records=1)
        if messages:
            for topic in messages:
                for message in messages[topic]:
                    # Process URL
                    article = Article.model_validate_json(message.value.decode())
                    logger.info("Received URL")
                    #load url
                    isValidURL = True
                    webDoc = None
                    #try to extract web document, if it doesn't work mark as invalid
                    try:
                        loader = WebBaseLoader(article.url, raise_for_status=True)
                        webDoc = loader.load()
                    except:
                        isValidURL = False
                    if isValidURL:
                        #if valid URL, load the document and process it
                        #extract article from web doc
                        articleBodyReq = chatPrompt.format_prompt(article_text=webDoc[0].page_content).to_messages()
                        if not collection.data.exists(article.uuid) or getenv("IS_HIGH_PRIORITY", "false")=="true":
                            articleRes = await llm.ainvoke(articleBodyReq)
                            article.fullStory = articleRes.content
                            #send processed data to next consumer
                            producer.send(topic=getenv("KAFKA_FULL_STORY_TOPIC"), value=article.model_dump_json().encode())
                            counter += 1
                            logger.info("Extracted full story %d", counter)
                        else:
                            logger.info("Already in db")
                    else:
                        logger.warning("Invalid url: %s", article.url)
                        #if a high priority container, send to redis that it was an invalid url
                        if getenv("IS_HIGH_PRIORITY", "false") == "true":
                            r.publish(article.uuid, "invalid")

if __name__ == "__main__":
    asyncio.run(main())