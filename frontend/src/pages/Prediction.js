import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { PieChart, Pie, Cell, ResponsiveContainer, Legend, Tooltip } from 'recharts';
import config from '../config';

const COLORS = ['#0b3d91', '#facc15']; // ACE theme

const Prediction = () => {
  const [modelInfo, setModelInfo] = useState(null);
  const [prediction, setPrediction] = useState(null);
  const [inputData, setInputData] = useState({
    distance: '',
    temperature: ''
  });

  // Fetch model info
  useEffect(() => {
    axios.get(`${config.API_BASE_URL}/api/v1/model-info`)
      .then(response => setModelInfo(response.data))
      .catch(error => console.error('Error fetching model info:', error));
  }, []);

  // Handle input change
  const handleChange = (e) => {
    setInputData({
      ...inputData,
      [e.target.name]: e.target.value
    });
  };

  // Call prediction API
  const handlePredict = async () => {
    try {
      const res = await axios.post(`${config.API_BASE_URL}/api/v1/predict`, {
        distance: parseFloat(inputData.distance),
        temperature: parseFloat(inputData.temperature)
      });

      setPrediction(res.data);
    } catch (err) {
      console.error(err);
      alert("Prediction failed");
    }
  };

  // Prepare chart data
  const chartData = prediction ? [
    { name: "Confidence", value: prediction.confidence * 100 },
    { name: "Remaining", value: 100 - (prediction.confidence * 100) }
  ] : [];

  return (
    <div className="prediction-page" style={{ padding: "20px" }}>
      <h1>Water Activity Prediction</h1>

      {/* Model Info */}
      <div className="model-info-card">
        <h2>Model Information</h2>
        {modelInfo && (
          <>
            <p><b>Model:</b> {modelInfo.model_type}</p>
            <p><b>Accuracy:</b> {(modelInfo.accuracy * 100).toFixed(2)}%</p>
            <p><b>Version:</b> {modelInfo.version}</p>
          </>
        )}
      </div>

      {/* Input Form */}
      <div className="prediction-form" style={{ marginTop: "20px" }}>
        <h2>Enter Sensor Data</h2>

        <input
          type="number"
          name="distance"
          placeholder="Distance"
          value={inputData.distance}
          onChange={handleChange}
        />

        <br /><br />

        <input
          type="number"
          name="temperature"
          placeholder="Temperature"
          value={inputData.temperature}
          onChange={handleChange}
        />

        <br /><br />

        <button onClick={handlePredict}>Predict</button>
      </div>

      {/* Results */}
      {prediction && (
        <div className="prediction-results" style={{ marginTop: "30px" }}>
          <h2>Prediction Results</h2>

          <h3>Activity: {prediction.prediction}</h3>
          <h4>Confidence: {(prediction.confidence * 100).toFixed(2)}%</h4>

          {/* Chart */}
          <div style={{
            width: "100%",
            height: "300px",
            display: "flex",
            justifyContent: "center",
            alignItems: "center"
          }}>
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie            
                  data={chartData}
                  dataKey="value"
                  outerRadius={80}
                  innerRadius={40}
                  label
                >
                
                  {chartData.map((entry, index) => (
                    <Cell key={index} fill={COLORS[index]} />
                  ))}
                </Pie>
                <Tooltip />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}
    </div>
  );
};

export default Prediction;