from newsapi import NewsApiClient
from os import getenv
from datetime import datetime, timedelta
from math import ceil
from kafka import KafkaProducer
from datamodels.articleobjects import Article, getLogger
from weaviate.util import generate_uuid5
from typing import List
import json

logger = getLogger("News Producer")

PAGE_SIZE = int(getenv("PAGE_SIZE", 20))

#instantiate Kafka producer
producer = KafkaProducer(bootstrap_servers=getenv("KAFKA_HOST")+":"+getenv("KAFKA_PORT"), client_id=getenv("KAFKA_URL_PRODUCER"))
logger.info("Instantiated producer")

def sendArticlesToKafka(newsResults):
    i = 0
    numErrors = 0
    for articleJson in newsResults['articles']:
        article = None
        try:
            article = Article.model_validate(articleJson)
        except Exception as e:
            numErrors += 1
            logger.warning("NUMBER OF ERRORS: %d", numErrors)
        if article is not None:
            article.uuid = generate_uuid5(article.url)
            #send message (article) to Kafka
            producer.send(topic=getenv("KAFKA_URL_TOPIC"), value=article.model_dump_json().encode())
            logger.info(article.url)
            i += 1

#instantiate news api client
newsapi = NewsApiClient(api_key=getenv("NEWS_API_KEY"))

def streamArticles(sourceList: List[str], isRecent: bool):
    #calculate earliest date to read articles from to initially populate database
    earliest_date = datetime.now().date() - timedelta(days=int(getenv("NUM_DAYS",0)),weeks=int(getenv("NUM_WEEKS", 4)))

    domainsToExclude = "theonion.com,removed.com,nasaspaceflight.com"

    firstPageResults = []
    if isRecent:
        firstPageResults = newsapi.get_everything(sources=",".join(sourceList), exclude_domains=domainsToExclude, language="en", page_size=PAGE_SIZE, from_param=earliest_date)
    else:
        firstPageResults = newsapi.get_everything(sources=",".join(sourceList), exclude_domains=domainsToExclude, language="en", page_size=PAGE_SIZE, to=earliest_date)
    #calculate number of pages to query through
    totalResults = int(firstPageResults['totalResults'])
    maxPages = ceil(min(totalResults, int(getenv("MAX_ALLOWED_RESULTS")))/PAGE_SIZE)

    #send articles from first page to Kafka
    sendArticlesToKafka(newsResults=firstPageResults)

    #send articles from subsequent pages to Kafka
    if maxPages > 1:
        for pageIndex in range(2, maxPages+1):
            results = []
            if isRecent:
                results = newsapi.get_everything(sources=",".join(sourceList), exclude_domains=domainsToExclude, language="en", page_size=PAGE_SIZE, page=pageIndex, from_param=earliest_date)
            else:
                results = newsapi.get_everything(sources=",".join(sourceList), exclude_domains=domainsToExclude, language="en", page_size=PAGE_SIZE, page=pageIndex, to=earliest_date)
            sendArticlesToKafka(newsResults=results)

sources = []
with open('sources.json') as f:
    sources = json.load(f)['sources']

sourceIds = [source['id'] for source in sources]

srcLen = len(sourceIds)

streamArticles(sourceList=sourceIds[:int(srcLen/2)], isRecent=True)
streamArticles(sourceList=sourceIds[int(srcLen/2):], isRecent=True)
#TODO: retrieve news articles no later than earliest_date to continue populating database