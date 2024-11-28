from flask import Flask, jsonify, request
import mysql.connector
import os

app = Flask(__name__)

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
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT value FROM counter WHERE id = 1")
    result = cursor.fetchone()
    cursor.close()
    conn.close()
    
    if result:
        return jsonify({'counter': result['value']}), 200
    else:
        return jsonify({'message': 'Counter not found'}), 404

# Route to update the counter (this is where frontend sends incremented counter value)
@app.route('/counter', methods=['POST'])
def update_counter():
    new_counter = request.json.get('counter')
    
    if new_counter is None:
        return jsonify({'message': 'Counter value is required'}), 400
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE counter SET value = %s WHERE id = 1", (new_counter,))
    conn.commit()
    cursor.close()
    conn.close()
    
    return jsonify({'message': 'Counter updated successfully'}), 200

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5001)