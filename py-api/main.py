from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from datamodels.articleobjects import Article, getLogger, instantiateBaseLLM
from os import getenv
import weaviate, asyncio
from weaviate.classes.query import Filter, Sort
from weaviate.util import generate_uuid5
from langchain_weaviate.vectorstores import WeaviateVectorStore
from langchain.chains.query_constructor.schema import AttributeInfo
from langchain.retrievers import SelfQueryRetriever, ContextualCompressionRetriever
from langchain.retrievers.self_query.weaviate import WeaviateTranslator
from langchain.retrievers.document_compressors import LLMChainFilter
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain.prompts import SystemMessagePromptTemplate, HumanMessagePromptTemplate, ChatPromptTemplate
from langchain.output_parsers import BooleanOutputParser
from kafka import KafkaProducer
from datetime import datetime, timedelta
from newsapi import NewsApiClient
from redis import Redis
from typing import List

class ConnectionManager:
    def __init__(self):
        self.activeConnections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.activeConnections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.activeConnections.remove(websocket)

    async def sendMessage(self, websocket: WebSocket, message: str):
        await websocket.send_text(message)

logger = getLogger("API")

producer = KafkaProducer(bootstrap_servers=getenv("KAFKA_HOST")+":"+getenv("KAFKA_PORT"), client_id=getenv("KAFKA_URL_PRODUCER"))

client = weaviate.connect_to_local(host=getenv("DB_HOST"), headers={"X-OpenAI-Api-Key": getenv("OPENAI_API_KEY")})
collection = client.collections.get(getenv("COLLECTION_NAME"))

r = Redis(host=getenv("REDIS_HOST"), port=getenv("REDIS_PORT"), decode_responses=True)

app = FastAPI()

def isAboutCurrentEvents(topic: str) -> bool:
    logger.info("Performing binary decision")
    boolOutputParser = BooleanOutputParser()
    sysPrompt = SystemMessagePromptTemplate.from_template("You are an AI assistant that identifies if the word/phrase that the user provides is an alias of the terms 'current events' or 'today'.")
    humPrompt = HumanMessagePromptTemplate.from_template("{topicName}\n{format_instructions}")
    chat_prompt = ChatPromptTemplate.from_messages([sysPrompt, humPrompt])

    #perform binary decision to determine if topic is relevant to current events or not
    topic_request = chat_prompt.format_prompt(topicName=topic, format_instructions="You must answer either YES or NO").to_messages()
    llm = instantiateBaseLLM()
    return boolOutputParser.parse(llm.invoke(topic_request).content)

async def listenOnRedis(r: Redis, uuid: str, socket: WebSocket, manager: ConnectionManager):
    #instantiate pub/sub listener
    pubsub = r.pubsub()
    pubsub.subscribe(uuid)
    messageNotFound = True
    failPollCounter = 0
    while messageNotFound:
        message = pubsub.get_message(timeout=30, ignore_subscribe_messages=True)
        if message is not None:
            if message['type'] == 'message' and message['data'] != 'invalid':
                logger.info("Found article")
                messageNotFound = False
                #query collection for object
                articleObj = collection.query.fetch_object_by_id(uuid)
                #successfully queried article
                if articleObj:
                    article = Article.model_validate(articleObj.properties)
                    #return article through web socket
                    logger.info("Sending on web socket")
                    await manager.sendMessage(socket, article.model_dump_json())
                else:
                    logger.warning("Could not retrieve object: " + uuid)
            elif message['type'] == 'message' and message['data'] == 'invalid':
                messageNotFound = False
                logger.warning("Found invalid URL, stopping wait")
        else:
            failPollCounter += 1
            if failPollCounter > 6:
                #if message polling fails for 3 minutes, exit out of loop
                messageNotFound = False
                logger.warning("Never found URL, timed out")
    #unsubscribe from redis channel
    pubsub.unsubscribe(uuid)

manager = ConnectionManager()

@app.websocket("/topic")
async def handleTopic(websocket: WebSocket):    
    await manager.connect(websocket)
    try:
        #receive topic
        data = await websocket.receive_text()

        #search database for articles related to topic given
        if isAboutCurrentEvents(data):
            #query by recency
            results = collection.query.fetch_objects(limit=7, filters=Filter.by_property("publishedAt").greater_or_equal(datetime.now() - timedelta(days=7)), sort=Sort.by_property("publishedAt",ascending=False))
            for article in results.objects:
                articleObj = Article.model_validate(article.properties)
                articleObj.uuid = str(article.uuid)
                await manager.sendMessage(websocket, articleObj.model_dump_json())
        else:
            logger.info("Using LLM to retrieve results")
            llm = ChatOpenAI(model_name="gpt-4-turbo")

            metadata_info = [
                AttributeInfo(name="topics", description="Key topics about the article", type="list[string]"),
                AttributeInfo(name="summary", description="Short summary of the news article", type="string"),
                AttributeInfo(name="title", description="Headline of the article", type="string")
            ]

            db = WeaviateVectorStore(client=client, index_name=getenv("COLLECTION_NAME"), text_key="fullStory", embedding=OpenAIEmbeddings(), attributes=["topics", "summary", "title"])
            
            retriever = SelfQueryRetriever.from_llm(llm, db, "Full length news articles", metadata_info, WeaviateTranslator())
            compressionRetriever = ContextualCompressionRetriever(base_compressor=LLMChainFilter.from_llm(llm), base_retriever=retriever)
            docResults = await compressionRetriever.aget_relevant_documents("Find the most recent articles about this topic: " + data)
            
            logger.info("Length of retrieved results: %d", len(docResults))

            results = []
            for document in docResults:
                article = Article.model_validate(document.metadata)
                article.fullStory = document.page_content
                article.uuid = str(generate_uuid5(article.url))
                results.append(article)
                
            #if found, return data to client, close websocket
            if len(results) >= 7:
                for i in range(7):
                    await manager.sendMessage(websocket, results[i].model_dump_json() )
            else:
                #send found articles
                for article in results:
                    await manager.sendMessage(websocket, article.model_dump_json() )
                #else, find news articles related to topic, send to high priority kafka consumers, create listeners for each uuid, wait for response, send through web socket
                newsapi = NewsApiClient(api_key=getenv("NEWS_API_KEY"))
                newsResults = newsapi.get_everything(q=data, page_size=10-len(results),exclude_domains='yahoo.com')
                logger.info("Queried for news results")

                uuids= []

                for articleJson in newsResults['articles']:
                    article = None
                    try:
                        article = Article.model_validate(articleJson)
                    except:
                        logger.warning("Invalid article: %s", articleJson['url'])
                    #send article to Kafka since we successfully create Article object
                    if article is not None:
                        article.uuid = generate_uuid5(article.url)
                        logger.info("Sending to kafka")
                        producer.send(topic=getenv("KAFKA_URL_TOPIC"), value=article.model_dump_json().encode())
                        uuids.append(article.uuid)
                #create threads to listen on redis and return data through websocket
                async with asyncio.TaskGroup() as tg:
                    for uuid in uuids:
                        tg.create_task(listenOnRedis(r, uuid, websocket, manager))
        manager.disconnect(websocket)
        await websocket.close()
    except WebSocketDisconnect:
        manager.disconnect(websocket)