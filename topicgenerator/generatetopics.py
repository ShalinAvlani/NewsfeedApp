from kafka import KafkaConsumer
from os import getenv
from datamodels.articleobjects import Article, getLogger, instantiateBaseLLM, connectToDB
from langchain.prompts import SystemMessagePromptTemplate, HumanMessagePromptTemplate, ChatPromptTemplate
from langchain.output_parsers import CommaSeparatedListOutputParser
import redis
import asyncio

async def main():
    logger = getLogger(__name__)

    r = redis.Redis(host=getenv("REDIS_HOST"), port=getenv("REDIS_PORT"), decode_responses=True)

    bootstrap_server = getenv("KAFKA_HOST") + ":" + getenv("KAFKA_PORT")

    consumer = KafkaConsumer(bootstrap_servers=bootstrap_server, client_id=getenv("KAFKA_SUMMARY_CONSUMER"), auto_offset_reset=getenv("OFFSET_OPTION"))
    consumer.subscribe(topics=[getenv("KAFKA_SUMMARY_TOPIC")])
    logger.info("Instantiated consumer and subscribed to topic")

    collection = connectToDB()
    logger.info("Connected to collection")

    llm = instantiateBaseLLM()

    cslParser = CommaSeparatedListOutputParser()
    sysPrompt = SystemMessagePromptTemplate.from_template("Using the following summary and full story of a news article, generate a list of topics relevant to the story. Don't generate more than ten phrases/topics.")
    humPrompt = HumanMessagePromptTemplate.from_template("Summary: {summary}\nFull story: {full_story}\n{format_instructions}")
    chatPrompt = ChatPromptTemplate.from_messages([sysPrompt, humPrompt])

    counter = 0
    while True:
        messages = consumer.poll(timeout_ms=0, max_records=1)
        if messages:
            for topic in messages:
                for message in messages[topic]:
                    #decode into object
                    article = Article.model_validate_json(message.value.decode())
                    logger.info("Received summary")
                    #take summary and full story, generate topic list
                    topicReq = chatPrompt.format_prompt(summary=article.summary, full_story=article.fullStory, format_instructions=cslParser.get_format_instructions()).to_messages()
                    topicRes = await llm.ainvoke(topicReq)
                    article.topics = cslParser.parse(topicRes.content)
                    logger.info("Created topics")
                    #insert article into weaviate
                    if not collection.data.exists(article.uuid):
                        #article doesn't exist in db, so insert
                        try:
                            collection.data.insert(
                                uuid=article.uuid,
                                properties={
                                    "publishedAt": article.publishedAt,
                                    "topics": article.topics,
                                    "summary": article.summary,
                                    "fullStory": article.fullStory,
                                    "url": article.url,
                                    "title": article.title,
                                    "author": article.author
                                }
                            )
                            counter += 1
                        except:
                            logger.warning("Object %s already exists in db", article.url)
                    else:
                        #article exists in db, so update
                        collection.data.update(
                            uuid=article.uuid,
                            properties={
                                "publishedAt": article.publishedAt,
                                "topics": article.topics,
                                "summary": article.summary,
                                "fullStory": article.fullStory,
                                "url": article.url,
                                "title": article.title,
                                "author": article.author
                            }
                        )
                    logger.info("Sent to database %d", counter)
                    #send update to redis if article is in high priority process
                    if getenv("IS_HIGH_PRIORITY", "false") == "true":
                        r.publish(article.uuid, article.uuid)

if __name__ == "__main__":
    asyncio.run(main())