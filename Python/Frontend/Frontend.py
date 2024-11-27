from flask import Flask, jsonify
import requests

app = Flask(__name__)

# Backend service URL (make sure it matches your Kubernetes service name)
BACKEND_URL = "http://backend-service:5001/counter"

@app.route('/')
def increment_counter():
    # Call the backend service to get the current counter value
    response = requests.get(BACKEND_URL)
    if response.status_code == 200:
        counter = response.json().get('counter')
        # Increment the counter
        new_counter = counter + 1
        
        # Send the incremented counter value back to the backend to be saved
        update_response = requests.post(BACKEND_URL, json={'counter': new_counter})
        
        if update_response.status_code == 200:
            return jsonify({'message': 'Counter incremented and saved', 'counter': new_counter}), 200
        else:
            return jsonify({'message': 'Error updating counter in backend'}), 500
    else:
        return jsonify({'message': 'Error fetching counter from backend'}), 500

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
