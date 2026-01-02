from flask import Blueprint

# Create the main API blueprint
api_bp = Blueprint('api', __name__)

# Import routes to register them with the blueprint
from . import bot_routes
from . import tourist_routes
from . import guide_routes
from . import smart_router

