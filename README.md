# NewsFeed
An LLM-powered backend service for users to stay up to date on the news for any topic

## Dependencies
**Docker**: Installation instructions are linked [here](https://docs.docker.com/engine/install/ "Docker Install Instructions").

**NewsAPI API Key**: You can obtain an API key [here](https://newsapi.org/register "Register for News API key"). Note that 
this has a free developer tier which has a fairly small rate limit for how many news articles you can request. The next tier at time of writing is priced at $550/month but allows you to query far more news articles, which would be critical to have in a production environment for this application.

**OpenAI API Key**: Setup instructions are linked [here](https://whatsthebigdata.com/how-to-get-openai-api-key/).

**Anthropic API Key**: Setup instructions linked [here](https://www.merge.dev/blog/anthropic-api-key).

It's recommended to put at least $10 in your OpenAI account and $5 in your Anthropic account if you intend to actively use this
application for a few weeks.

This application has been tested/run on an AWS EC2 t3.large instance. Running Apache Kafka in addition to all the other services requires more than 8GB RAM, so this should run on a system with ideally 12GB RAM just to be safe.

## Configure
Once you get your API Keys, you're going to need to go to the `environment` directory:
```
cd environment
```
Copy the `keys_example.env` file and rename it to `keys.env` and insert the corresponding API keys:
```
cp keys_example.env keys.env
```

## Usage
In the main project directory, first build the image that all the services will be using:
```
docker build -t python-datamodels ./datamodels/
```
Once that's built, then you can run the application:
```
docker compose up
```

## Architecture
![NewsfeedArchitecture](https://github.com/ShalinAvlani/NewsfeedApp/assets/7970251/26e6a2d0-6a6e-467c-8052-62e25fafd351)
Kafka is used as the ETL pipeline to support incoming news URLs from the API and news URLs from the NewsAPI producer in real time. I created a high priority processing pipeline to handle the edge case of certain article topics not existing in the database at retrieval time - this way users just have to wait for a short bit before receiving enough articles related to the topic they queried for.

### Limitations
Due to the limited amount of requests you can make at the free tier of the News API, it's difficult to create a full-fledged ETL pipeline to continually process news articles and store them in the database - ideally if there are other sources to index news articles, then these could be added as producers to the Kafka cluster at some point in the future.

The architecture is designed so that this could be a distributed system, with theoretically many more news consumer services all running on different machines and more Kafka nodes to ensure higher fault tolerance within the Kafka cluster, but allocating resources for extra EC2 instances and avoiding the rate limit issue with OpenAI's and Anthropic's LLM's don't make this feasible without workarounds.

OpenAI and Anthropic rate limit their API's significantly when it comes to processing data in this application. Currently, the way to handle this is to wait 5 seconds before restarting an LLM service container, but in production other measures would need to be taken. Having multiple OpenAI/Anthropic API keys to switch between might be a more long-lasting solution. Another option is to add more fallback LLM's (configured in the `datamodels/articleobjects.py` file in the `instantiateBaseLLM` function). If you intend to run this application for an extensive period of time, it makes the most sense to use OpenAI's batch API to collect news articles in batches and have the results returned after a day or so. It'll be far cheaper, avoid the rate limit issue, and reduce your resource requirements, but you lose out on processing news articles near instantaneously.
