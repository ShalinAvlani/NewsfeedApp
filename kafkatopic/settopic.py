from kafka import KafkaAdminClient
from kafka.admin import NewTopic
from os import getenv
from datamodels.articleobjects import getLogger

logger = getLogger("Set Topic")

logger.info("Imported libraries")
client = KafkaAdminClient(bootstrap_servers=[getenv("KAFKA_HOST") + ":" + getenv("KAFKA_PORT")])
logger.info("Connected to client")
topic_list = client.list_topics()
logger.info(topic_list)

envTopics = [getenv("KAFKA_URL_TOPIC"), getenv("KAFKA_FULL_STORY_TOPIC"), getenv("KAFKA_SUMMARY_TOPIC")]

envTopics = envTopics + [getenv("KAFKA_HP_PREFIX")+kafkaTopic for kafkaTopic in envTopics]

if set(envTopics)==set(topic_list):
    logger.info("Topics are already set up")
else:
    #create topics in kafka
    client.create_topics([NewTopic(kafkaTopic, num_partitions=1, replication_factor=1) for kafkaTopic in envTopics])
    logger.info("Topics are now set up")

client.close()