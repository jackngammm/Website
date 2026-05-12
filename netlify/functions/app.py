import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from serverless_wsgi import handle_request
from main import app

def handler(event, context):
    return handle_request(app, event, context)
