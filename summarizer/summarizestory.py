from kafka import KafkaConsumer, KafkaProducer
from os import getenv
from datamodels.articleobjects import Article, getLogger, instantiateBaseLLM, connectToDB
from langchain.prompts import SystemMessagePromptTemplate, HumanMessagePromptTemplate, ChatPromptTemplate
import asyncio

async def main():
    logger = getLogger(__name__)

    bootstrap_server = getenv("KAFKA_HOST") + ":" + getenv("KAFKA_PORT")

    consumer = KafkaConsumer(bootstrap_servers=bootstrap_server, client_id=getenv("KAFKA_FULL_STORY_CONSUMER"), auto_offset_reset=getenv("OFFSET_OPTION"))
    consumer.subscribe(topics=[getenv("KAFKA_FULL_STORY_TOPIC")])
    logger.info("Instantiated consumer and subscribed")

    producer = KafkaProducer(bootstrap_servers=bootstrap_server,client_id=getenv("KAFKA_SUMMARY_PRODUCER"))
    logger.info("Instaniated producer")

    collection = connectToDB()
    logger.info("Connected to collection")

    llm = instantiateBaseLLM()

    sysPrompt = SystemMessagePromptTemplate.from_template("Summarize the following article in 6 sentences or less.")
    humPrompt = HumanMessagePromptTemplate.from_template("{full_story}")
    chatPrompt = ChatPromptTemplate.from_messages([sysPrompt, humPrompt])

    counter = 0
    while True:
        messages = consumer.poll(timeout_ms=0, max_records=1)
        if messages:
            for topic in messages:
                for message in messages[topic]:
                    #decode into object
                    article = Article.model_validate_json(message.value.decode())
                    logger.info("Received full story")
                    #summarize full story and store in object
                    summarizeReq = chatPrompt.format_prompt(full_story=article.fullStory).to_messages()
                    if not collection.data.exists(article.uuid) or getenv("IS_HIGH_PRIORITY", "false")=="true":
                        summarizeRes = await llm.ainvoke(summarizeReq)
                        article.summary = summarizeRes.content
                        #send message to next topic
                        producer.send(topic=getenv("KAFKA_SUMMARY_TOPIC"), value=article.model_dump_json().encode())
                        counter += 1
                        logger.info("Created summary %d", counter)
                    else:
                        logger.info("Already in db")

if __name__ == "__main__":
    asyncio.run(main())