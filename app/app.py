import os
import socket
from flask import Flask, jsonify

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

try:
    import psycopg2
    POSTGRES_AVAILABLE = True
except ImportError:
    POSTGRES_AVAILABLE = False

app = Flask(__name__)

REDIS_HOST = os.getenv('REDIS_HOST', 'redis')
REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
POSTGRES_HOST = os.getenv('POSTGRES_HOST', 'db')
POSTGRES_PORT = int(os.getenv('POSTGRES_PORT', 5432))
POSTGRES_USER = os.getenv('POSTGRES_USER', 'counter')
POSTGRES_PASSWORD = os.getenv('POSTGRES_PASSWORD', 'counter_password')
POSTGRES_DB = os.getenv('POSTGRES_DB', 'counter_db')
DB_TYPE = os.getenv('DB_TYPE', 'redis')


def get_redis_connection():
    if not REDIS_AVAILABLE:
        return None
    try:
        return redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    except Exception as e:
        print(f"Redis connection error: {e}")
        return None


def get_postgres_connection():
    if not POSTGRES_AVAILABLE:
        return None
    try:
        conn = psycopg2.connect(
            host=POSTGRES_HOST,
            port=POSTGRES_PORT,
            user=POSTGRES_USER,
            password=POSTGRES_PASSWORD,
            database=POSTGRES_DB
        )
        return conn
    except Exception as e:
        print(f"PostgreSQL connection error: {e}")
        return None


def init_postgres():
    conn = get_postgres_connection()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS counter (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(50) UNIQUE NOT NULL,
                    value INTEGER DEFAULT 0
                )
            """)
            cur.execute("""
                INSERT INTO counter (name, value) VALUES ('visits', 0)
                ON CONFLICT (name) DO NOTHING
            """)
            conn.commit()
            cur.close()
            conn.close()
        except Exception as e:
            print(f"PostgreSQL init error: {e}")


def increment_counter():
    if DB_TYPE == 'postgres':
        conn = get_postgres_connection()
        if conn:
            try:
                cur = conn.cursor()
                cur.execute("""
                    UPDATE counter SET value = value + 1 WHERE name = 'visits'
                    RETURNING value
                """)
                result = cur.fetchone()
                conn.commit()
                cur.close()
                conn.close()
                return result[0] if result else 0
            except Exception as e:
                print(f"PostgreSQL increment error: {e}")
                return 0
    else:
        r = get_redis_connection()
        if r:
            try:
                return r.incr('counter')
            except Exception as e:
                print(f"Redis increment error: {e}")
                return 0
    return 0


def get_counter():
    if DB_TYPE == 'postgres':
        conn = get_postgres_connection()
        if conn:
            try:
                cur = conn.cursor()
                cur.execute("SELECT value FROM counter WHERE name = 'visits'")
                result = cur.fetchone()
                cur.close()
                conn.close()
                return result[0] if result else 0
            except Exception as e:
                print(f"PostgreSQL get error: {e}")
                return 0
    else:
        r = get_redis_connection()
        if r:
            try:
                val = r.get('counter')
                return int(val) if val else 0
            except Exception as e:
                print(f"Redis get error: {e}")
                return 0
    return 0


if DB_TYPE == 'postgres':
    init_postgres()


@app.route('/')
def index():
    count = increment_counter()
    hostname = socket.gethostname()
    return jsonify({
        'message': 'Hello from Flask Counter!',
        'counter': count,
        'hostname': hostname,
        'db_type': DB_TYPE
    })


@app.route('/count')
def count():
    current_count = get_counter()
    hostname = socket.gethostname()
    return jsonify({
        'counter': current_count,
        'hostname': hostname,
        'db_type': DB_TYPE
    })


@app.route('/health')
def health():
    db_status = 'unknown'
    if DB_TYPE == 'postgres':
        conn = get_postgres_connection()
        db_status = 'healthy' if conn else 'unhealthy'
        if conn:
            conn.close()
    else:
        r = get_redis_connection()
        if r:
            try:
                r.ping()
                db_status = 'healthy'
            except:
                db_status = 'unhealthy'

    hostname = socket.gethostname()
    status = 'healthy' if db_status == 'healthy' else 'degraded'

    return jsonify({
        'status': status,
        'hostname': hostname,
        'db_type': DB_TYPE,
        'db_status': db_status
    }), 200 if status == 'healthy' else 503


@app.route('/info')
def info():
    hostname = socket.gethostname()
    return jsonify({
        'hostname': hostname,
        'db_type': DB_TYPE,
        'redis_host': REDIS_HOST if DB_TYPE == 'redis' else None,
        'postgres_host': POSTGRES_HOST if DB_TYPE == 'postgres' else None
    })


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
