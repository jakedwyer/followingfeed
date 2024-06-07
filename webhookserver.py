from flask import Flask, request, jsonify
from main import main  # Import the main function from your script

app = Flask(__name__)

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        main()  # Call the main function
        return jsonify({"status": "success"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
