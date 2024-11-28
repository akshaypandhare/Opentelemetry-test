from flask import Flask, jsonify, request
import mysql.connector
from opentelemetry import trace
from opentelemetry.propagate import extract
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.instrumentation.mysql import MySQLInstrumentor
from opentelemetry.trace.status import Status, StatusCode

resource = Resource.create({
    "service.name": "backend",  # Replace with your desired service name
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
tracer = trace.get_tracer("backend")

app = Flask(__name__)

# Instrument Flask and MySQL
FlaskInstrumentor().instrument_app(app)
MySQLInstrumentor().instrument()

# MySQL database connection settings (make sure these are correct for your setup)
MYSQL_HOST = "mysql-service.default.svc.cluster.local"  # Kubernetes service name
MYSQL_USER = "root"
MYSQL_PASSWORD = "testpassword"  # Change as per your setup
MYSQL_DB = "testdb"  # Ensure this database exists in MySQL
MYSQL_PORT = 3306

# Connect to MySQL
def get_db_connection():
    conn = mysql.connector.connect(
        host=MYSQL_HOST,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=MYSQL_DB,
        port=MYSQL_PORT
    )
    return conn

# Route to get the current counter from MySQL
@app.route('/counter', methods=['GET'])
def get_counter():
    # Extract trace context from incoming request
    context = extract(request.headers)
    
    # Start a span that is a child of the incoming trace
    with tracer.start_as_current_span("get-counter", context=context) as span:
        try:
            # Create a span for database connection
            with tracer.start_as_current_span("db-connection"):
                conn = get_db_connection()
                cursor = conn.cursor(dictionary=True)
            
            # Create a span for database query
            with tracer.start_as_current_span("db-query"):
                span.set_attribute("db.statement", "SELECT value FROM counter WHERE id = 1")
                cursor.execute("SELECT value FROM counter WHERE id = 1")
                result = cursor.fetchone()
            
            # Close database resources
            cursor.close()
            conn.close()
            
            if result:
                # Add counter value as an attribute
                span.set_attribute("app.counter.value", result['value'])
                return jsonify({'counter': result['value']}), 200
            else:
                # Mark span as not found
                span.set_status(Status(StatusCode.ERROR, "Counter not found"))
                return jsonify({'message': 'Counter not found'}), 404
        
        except Exception as e:
            # Record any exceptions
            span.set_status(Status(StatusCode.ERROR))
            span.record_exception(e)
            return jsonify({'message': f'Error fetching counter: {str(e)}'}), 500

# Route to update the counter (this is where frontend sends incremented counter value)
@app.route('/counter', methods=['POST'])
def update_counter():
    # Extract trace context from incoming request
    context = extract(request.headers)
    
    # Start a span that is a child of the incoming trace
    with tracer.start_as_current_span("update-counter", context=context) as span:
        try:
            # Get the new counter value from request
            new_counter = request.json.get('counter')
            
            if new_counter is None:
                span.set_status(Status(StatusCode.ERROR, "Counter value missing"))
                return jsonify({'message': 'Counter value is required'}), 400
            
            # Create a span for database connection
            with tracer.start_as_current_span("db-connection"):
                conn = get_db_connection()
                cursor = conn.cursor()
            
            # Create a span for database update
            with tracer.start_as_current_span("db-update"):
                # Set attributes for the update operation
                span.set_attribute("db.statement", "UPDATE counter SET value = %s WHERE id = 1")
                span.set_attribute("app.counter.new_value", new_counter)
                
                cursor.execute("UPDATE counter SET value = %s WHERE id = 1", (new_counter,))
                conn.commit()
            
            # Close database resources
            cursor.close()
            conn.close()
            
            return jsonify({'message': 'Counter updated successfully'}), 200
        
        except Exception as e:
            # Record any exceptions
            span.set_status(Status(StatusCode.ERROR))
            span.record_exception(e)
            return jsonify({'message': f'Error updating counter: {str(e)}'}), 500

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5001)