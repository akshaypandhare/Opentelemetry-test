from flask import Flask, jsonify
import requests
from opentelemetry import trace
from opentelemetry.propagate import inject
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.trace.status import Status, StatusCode

app = Flask(__name__)

# Set up the tracer provider with a specific service name
resource = Resource.create({
    "service.name": "frontend",  # Replace with your desired service name
    "service.version": "1.0.0"  # Optional: add version information
})

provider = TracerProvider(resource=resource)

jaeger_exporter = JaegerExporter(
    agent_host_name="simplest-agent.default.svc.cluster.local",  # Adjust to your Jaeger agent service
    agent_port=6831,
)
processor = BatchSpanProcessor(jaeger_exporter)
provider.add_span_processor(processor)

# Sets the global default tracer provider
trace.set_tracer_provider(provider)

# Creates a tracer from the global tracer provider
tracer = trace.get_tracer("frontend")

# Backend service URL (make sure it matches your Kubernetes service name)
BACKEND_URL = "http://backend:80/counter"

FlaskInstrumentor().instrument_app(app)
RequestsInstrumentor().instrument()

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