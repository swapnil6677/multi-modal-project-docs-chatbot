"""
Main application entry point
"""

import logging
import os
from dotenv import load_dotenv
from app import create_app
from app.routes import initialize_processors

# Load environment variables from .env file
dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(dotenv_path)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def main():
    """Main application function"""
    try:
        # Create Flask app
        app = create_app()
        
        # Initialize processors within app context
        with app.app_context():
            initialize_processors()
        
        app.logger.info("Application started successfully")
        
        # Run the application
        app.run(debug=True, host='0.0.0.0', port=5001)
        
    except Exception as e:
        logging.error(f"Failed to start application: {e}")
        raise

if __name__ == '__main__':
    main()
