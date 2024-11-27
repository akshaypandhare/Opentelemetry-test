from flask import Flask, jsonify
import requests
from opentelemetry import trace
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.jaeger.thrift import JaegerExporter

app = Flask(__name__)

# OpenTelemetry setup
trace.set_tracer_provider(TracerProvider())
tracer = trace.get_tracer(__name__)

# Configure Jaeger Exporter
jaeger_exporter = JaegerExporter(
    agent_host_name="simplest-collector",  # Replace with Jaeger service hostname in your cluster
    agent_port=14268,          # Default Jaeger UDP port
)
span_processor = BatchSpanProcessor(jaeger_exporter)
trace.get_tracer_provider().add_span_processor(span_processor)

FlaskInstrumentor().instrument_app(app)
RequestsInstrumentor().instrument()

# Backend service URL (make sure it matches your Kubernetes service name)
BACKEND_URL = "http://backend-service:5001/counter"

@app.route('/')
def increment_counter():
    with tracer.start_as_current_span("frontend-increment-counter"):
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
