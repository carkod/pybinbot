# Re-export shared dependencies for unified imports
import numpy
import pandas
import passlib
import pydantic
import pydantic_settings
import pymongo
import python_dotenv
import python_jose
import requests
import requests_cache
import requests_html
import scipy
import websocket
import aiokafka
import apscheduler
import confluent_kafka
import kafka
import kucoin_universal_sdk

# Expose them for direct import
__all__ = [
    "numpy", "pandas", "passlib", "pydantic", "pydantic_settings", "pymongo", "python_dotenv", "python_jose", "requests", "requests_cache", "requests_html", "scipy", "websocket", "aiokafka", "apscheduler", "confluent_kafka", "kafka", "kucoin_universal_sdk"
]
