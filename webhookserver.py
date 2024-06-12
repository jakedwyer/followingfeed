from flask import Flask, request, jsonify
from flask_cors import CORS
from main import main  # Import the main function from your script
import logging

app = Flask(__name__)
CORS(app, resources={r"/webhook": {"origins": "*"}})  # Allow CORS for the /webhook endpoint

logging.basicConfig(level=logging.INFO)

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        logging.info("Received webhook request")
        main()  # Call the main function
        return jsonify({"status": "success"}), 200
    except Exception as e:
        logging.error(f"Error occurred: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)