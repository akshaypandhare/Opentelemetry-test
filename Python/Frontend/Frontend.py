from flask import Flask, jsonify, request
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
    # Start the main span
    with tracer.start_as_current_span("frontend-increment-counter") as span:
        try:
            # Prepare headers for context propagation
            headers = {}
            inject(headers)  # Inject trace context into headers

            # Fetch current counter
            with tracer.start_as_current_span("get-counter") as get_span:
                get_span.set_attribute("http.method", "GET")
                get_span.set_attribute("http.url", BACKEND_URL)
                
                response = requests.get(BACKEND_URL, headers=headers)
                
                if response.status_code == 200:
                    counter = response.json().get('counter')
                    
                    # Increment the counter
                    new_counter = counter + 1
                    
                    # Update counter
                    with tracer.start_as_current_span("update-counter") as update_span:
                        update_span.set_attribute("http.method", "POST")
                        update_span.set_attribute("http.url", BACKEND_URL)
                        
                        update_response = requests.post(
                            BACKEND_URL, 
                            json={'counter': new_counter}, 
                            headers=headers
                        )
                        
                        if update_response.status_code == 200:
                            span.set_attribute("app.counter.value", new_counter)
                            return jsonify({
                                'message': 'Counter incremented and saved', 
                                'counter': new_counter
                            }), 200
                        else:
                            # Mark update span as error
                            update_span.set_status(Status(StatusCode.ERROR))
                            update_span.record_exception(Exception("Backend update failed"))
                            
                            # Mark main span as error
                            span.set_status(Status(StatusCode.ERROR))
                            return jsonify({'message': 'Error updating counter in backend'}), 500
                else:
                    # Mark get span as error
                    get_span.set_status(Status(StatusCode.ERROR))
                    
                    # Mark main span as error
                    span.set_status(Status(StatusCode.ERROR))
                    return jsonify({'message': 'Error fetching counter from backend'}), 500
        
        except Exception as e:
            # Capture any unexpected errors
            span.set_status(Status(StatusCode.ERROR))
            span.record_exception(e)
            return jsonify({'message': f'Unexpected error: {str(e)}'}), 500

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)