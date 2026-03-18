import os
from dotenv import load_dotenv
import requests
import psycopg2
import time
import random
import threading
from datetime import datetime
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

from tensorflow.keras.models import load_model
import numpy as np


# Load GRU model
ml_model = load_model("saved_models/Improved GRU_model.h5")

# Class labels
classes = ["no_activity", "shower", "faucet", "toilet", "dishwasher"]

# Load environment variables from .env file
load_dotenv()

app = FastAPI()

# Added CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# ==============================
# DATABASE CONNECTION
# ==============================


def get_connection():
    """
    Get database connection using environment variables.
    Falls back to local development settings if env vars not set.
    """
    return psycopg2.connect(
        host=os.environ.get("DB_HOST", "localhost"),
        port=os.environ.get("DB_PORT", "5432"),
        database=os.environ.get("DB_NAME", "iot-test"),
        user=os.environ.get("DB_USER", "postgres"),
        password=os.environ.get("DB_PASSWORD", "postgres"),
        sslmode=os.environ.get("DB_SSLMODE", "prefer")  # Use "require" for Aiven
    )


# ==============================
# CREATE TABLES
# ==============================
def create_tables():

    conn = get_connection()
    cur = conn.cursor()

    # Sensor data table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS sensor_data (
        id SERIAL PRIMARY KEY,
        node_id VARCHAR(50),
        field1 FLOAT,
        field2 FLOAT,
        created_at TIMESTAMP
    )
    """)

    # Tank parameters table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS tank_sensorparameters (
        id SERIAL PRIMARY KEY,
        node_id VARCHAR(50),
        tank_height_cm FLOAT,
        tank_length_cm FLOAT,
        tank_width_cm FLOAT,
        lat FLOAT,
        long FLOAT
    )
    """)

     # Prediction table
    cur.execute("""
CREATE TABLE IF NOT EXISTS predictions (
    id SERIAL PRIMARY KEY,
    distance FLOAT,
    temperature FLOAT,
    prediction VARCHAR(50),
    confidence FLOAT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

    conn.commit()
    cur.close()
    conn.close()


# ==============================
# THINGSPEAK CONFIG
# ==============================
REAL_DATA_WITH_CURRENT_TIME = False
TEST_MODE = True

# Node id of sensor
NODE_ID = "NODE_001"

# ThingSpeak API
url = "https://api.thingspeak.com/channels/3290444/feeds.json?api_key=AWP8F08WA7SLO5EQ&results=-1"

last_created_at = None


# ==============================
# GENERATE TEST DATA
# ==============================
def generate_test_data():

    base_values = {
        "distance": 94.0,
        "temperature": 20.8
    }

    return {
        "distance": round(base_values["distance"] + random.uniform(-10, 10), 1),
        "temperature": round(base_values["temperature"] + random.uniform(-2, 2), 1),
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }


# ==============================
# SENSOR DATA COLLECTOR
# ==============================
def sensor_collector():

    global last_created_at

    print("Distance & Temperature Data Collector Started")

    while True:

        try:

            if TEST_MODE:

                test_data = generate_test_data()

                distance = test_data["distance"]
                temperature = test_data["temperature"]
                created_at = test_data["created_at"]

            else:

                response = requests.get(url)
                data = response.json()

                feed = data["feeds"][0]

                distance = float(feed["field1"])
                temperature = float(feed["field2"])
                created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            print("NEW DATA:", distance, temperature, created_at)

            conn = get_connection()
            cur = conn.cursor()

            cur.execute("""
            INSERT INTO sensor_data
            (node_id, field1, field2, created_at)
            VALUES (%s,%s,%s,%s)
            """,
                        (NODE_ID, distance, temperature, created_at))

            conn.commit()

            cur.close()
            conn.close()

            print("Sensor data inserted")

        except Exception as e:

            print("Error:", e)

        time.sleep(20)


# ==============================
# REQUEST MODEL
# ==============================
class TankParameters(BaseModel):

    node_id: str
    tank_height_cm: float
    tank_length_cm: float
    tank_width_cm: float
    lat: float
    long: float


# ==============================
# POST API
# ==============================
@app.post("/tank-parameters")
def create_tank_parameters(data: TankParameters):

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
    INSERT INTO tank_sensorparameters
    (node_id, tank_height_cm, tank_length_cm, tank_width_cm, lat, long)
    VALUES (%s,%s,%s,%s,%s,%s)
    RETURNING id
    """,
                (
                    data.node_id,
                    data.tank_height_cm,
                    data.tank_length_cm,
                    data.tank_width_cm,
                    data.lat,
                    data.long
                ))

    new_id = cur.fetchone()[0]

    conn.commit()
    cur.close()
    conn.close()

    return {
        "message": "Tank parameters inserted successfully",
        "id": new_id
    }


# ==============================
# GET API
# ==============================
@app.get("/tank-parameters")
def get_tank_parameters():

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT * FROM tank_sensorparameters")

    rows = cur.fetchall()

    cur.close()
    conn.close()

    result = []

    for row in rows:
        result.append({
            "id": row[0],
            "node_id": row[1],
            "tank_height_cm": row[2],
            "tank_length_cm": row[3],
            "tank_width_cm": row[4],
            "lat": row[5],
            "long": row[6]
        })

    return result


# ==============================
# GET SENSOR DATA API
# ==============================
@app.get("/sensor-data")
def get_sensor_data():

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
    SELECT id,node_id,field1,field2,created_at
    FROM sensor_data
    ORDER BY id DESC
    LIMIT 100
    """)

    rows = cur.fetchall()

    cur.close()
    conn.close()

    result = []

    for row in rows:
        result.append({
            "id": row[0],
            "node_id": row[1],
            "distance": row[2],
            "temperature": row[3],
            "created_at": row[4]
        })

    return result

@app.get("/sensor-data")
def get_sensor_data(node_id: str = None):

    conn = get_connection()
    cur = conn.cursor()

    if node_id:
        cur.execute("""
        SELECT id,node_id,field1,field2,created_at
        FROM sensor_data
        WHERE node_id = %s
        ORDER BY created_at DESC
        """, (node_id,))
    else:
        cur.execute("""
        SELECT id,node_id,field1,field2,created_at
        FROM sensor_data
        ORDER BY created_at DESC
        """)

    rows = cur.fetchall()

    cur.close()
    conn.close()

    result = []

    for row in rows:
        result.append({
            "id": row[0],
            "node_id": row[1],
            "distance": row[2],
            "temperature": row[3],
            "created_at": row[4]
        })

    return result


# ==============================
# POST PREDICT API
# ==============================

@app.post("/api/v1/predict")
def predict_water_activity(data: dict):

    try:
        distance = data["distance"]
        temperature = data["temperature"]

        # Prepare input
        input_data = np.array([[distance, temperature]])

        # Adjust if needed
        input_data = input_data.reshape(1, 1, 2)

        # Predict
        prediction = ml_model.predict(input_data)

        predicted_class = classes[np.argmax(prediction)]
        confidence = float(np.max(prediction))

        # Save to DB
        conn = get_connection()
        cur = conn.cursor()

        cur.execute("""
        INSERT INTO predictions (distance, temperature, prediction, confidence)
        VALUES (%s, %s, %s, %s)
        """, (distance, temperature, predicted_class, confidence))

        conn.commit()
        cur.close()
        conn.close()

        return {
            "prediction": predicted_class,
            "confidence": confidence
        }

    except Exception as e:
        return {"error": str(e)}
    

# ==============================
# GET MODEL-INFO API
# ==============================

@app.get("/api/v1/model-info")
def get_model_info():

    return {
     "model_type": "GRU",
     "version": "1.0",
     "accuracy": 0.9103,
     "last_trained": "2026-03-10",
     "classes": classes
    }
    

# ==============================
# POST PREDICTIONS-HISTORY API
# ==============================

@app.get("/api/v1/predictions-history")
def get_predictions_history(limit: int = 100):

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
    SELECT distance, temperature, prediction, confidence, created_at
    FROM predictions
    ORDER BY created_at DESC
    LIMIT %s
    """, (limit,))

    rows = cur.fetchall()

    cur.close()
    conn.close()

    return [
        {
            "distance": r[0],
            "temperature": r[1],
            "prediction": r[2],
            "confidence": r[3],
            "time": str(r[4])
        }
        for r in rows
    ]

# ==============================
# DELETE TANK NODE API
# ==============================

@app.delete("/api/v1/tank/{node_id}")
def delete_tank(node_id: str):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("DELETE FROM tank_sensorparameters WHERE node_id = %s", (node_id,))
    
    conn.commit()
    cur.close()
    conn.close()

    return {"message": f"{node_id} deleted successfully"}

# ==============================
# START BACKGROUND COLLECTOR
# ==============================
@app.on_event("startup")
def start_background_tasks():

    create_tables()

    thread = threading.Thread(target=sensor_collector)
    thread.daemon = True
    thread.start()


# ==============================
# MAIN
# ==============================
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
