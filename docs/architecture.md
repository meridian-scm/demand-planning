# Solution Architecture

## Overview

The AI-Powered Demand Planning solution helps supply chain teams forecast future demand and identify planning risks using historical sales and inventory data.

## Architecture

Sales Data (CSV)
        |
        v
Python + Pandas
        |
        v
Demand Forecast Engine
        |
        v
AI Analysis (Ollama + Llama 3.1)
        |
        v
Recommendations
        |
        v
Streamlit Dashboard

## Components

### User Interface
- Streamlit Dashboard

### Data Source
- CSV files

### Data Processing
- Pandas

### AI Layer
- Ollama
- Llama 3.1

### Visualization
- Plotly
- Streamlit Charts

## Outputs

- Demand Forecast
- Demand Trend Analysis
- Inventory Risk Alerts
- AI Recommendations
