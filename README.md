# meridian-supply-chain-operations

# AI-Powered Demand Planning for Supply Chain Operations

## Overview

AI-Powered Demand Planning for Supply Chain Operations is an intelligent solution designed to help supply chain teams improve demand forecasting and planning through data-driven insights and Artificial Intelligence.

The application analyzes historical sales and inventory data to predict future demand, identify demand trends, detect planning exceptions, and provide recommendations that help planners make better inventory and replenishment decisions.



## Business Challenge

Demand planning is a critical supply chain activity that directly impacts inventory levels, customer satisfaction, and operational efficiency.

Many organizations rely on manual analysis and spreadsheets to:

- Review historical sales data
- Forecast future demand
- Identify changing demand patterns
- Monitor inventory availability
- Detect planning risks
- Make replenishment decisions

These activities are often time-consuming, reactive, and prone to human error.



## Solution

The AI-Powered Demand Planning solution helps planners make smarter and faster decisions by using AI to analyze demand patterns and generate actionable insights.

### Demand Forecasting

The solution analyzes historical sales data to:

- Predict future demand
- Identify trends and seasonality
- Forecast product-level demand
- Support inventory planning decisions

### Demand Trend Analysis

The solution helps planners understand:

- Products with increasing demand
- Products with declining demand
- Seasonal demand fluctuations
- Emerging demand patterns

### Planning Exception Detection

The solution automatically identifies potential planning risks such as:

- Unexpected demand spikes
- Sudden demand drops
- Products at risk of stock shortages
- Potential excess inventory situations

### AI Recommendations

The solution generates recommendations to help planners:

- Improve forecasting accuracy
- Optimize inventory levels
- Reduce stockout risks
- Improve replenishment planning



## Key Features

### Demand Forecast Dashboard

Provides visibility into:

- Historical demand
- Forecasted demand
- Demand growth trends
- Forecast recommendations

### Sales Data Analysis

Analyze uploaded sales data to:

- Identify patterns
- Detect trends
- Compare product performance

### Exception Monitoring

Receive alerts for:

- Demand spikes
- Demand declines
- Inventory risks
- Forecast anomalies

### AI Insights

Generate business-friendly summaries and recommendations from demand planning data.



## Example Use Cases

### Forecast Next Month Demand

**Input**

| Month | Units Sold |
|||
| January | 100 |
| February | 120 |
| March | 140 |
| April | 160 |

**AI Forecast**

Forecasted Demand for May: **180 Units**

Recommendation:

Increase replenishment quantities to support rising demand.



### Demand Spike Detection

**AI Insight**

Product A demand increased by 25% compared to the previous month.

Recommendation:

Review inventory levels and ensure replenishment plans are aligned with forecasted demand.



### Inventory Risk Alert

**AI Insight**

Current inventory levels may not support projected demand over the next planning period.

Recommendation:

Review inventory strategy and replenishment schedule.



## Business Benefits

- Improve demand forecasting accuracy
- Reduce manual forecasting effort
- Detect planning risks earlier
- Support proactive inventory decisions
- Improve product availability
- Reduce stockout events
- Improve operational efficiency



## Target Users

- Demand Planners
- Supply Chain Analysts
- Inventory Managers
- Supply Chain Managers
- Operations Teams



## Technology Stack

### Frontend

- Streamlit

### Data Processing

- Python
- Pandas

### Data Storage

- CSV Files

### AI

- Ollama (Local LLM)
- Llama 3.1

### Visualization

- Streamlit Charts
- Plotly

### Source Control

- GitHub



## Project Architecture

text
Sales Data (CSV)
       |
       v
Python + Pandas
       |
       v
Demand Forecast Engine
       |
       v
AI Analysis
(Ollama + Llama 3.1)
       |
       v
Insights & Recommendations
       |
       v
Streamlit Dashboard




## Future Enhancements

- Advanced forecasting models
- Multi-product demand forecasting
- Seasonal demand prediction
- Automated replenishment recommendations
- Inventory optimization
- Conversational AI assistant for planners
- Real-time demand monitoring



## Getting Started

### Prerequisites

- Python 3.11+
- Git
- Ollama
- Llama 3.1

### Install Dependencies

bash
pip install streamlit pandas plotly


### Run Application

bash
streamlit run app.py


### Open Browser

text
http://localhost:8501




## Project Goal

The goal of this project is to demonstrate how Artificial Intelligence can improve demand planning by forecasting future demand, identifying planning risks, and providing AI-generated recommendations that help supply chain teams make better business decisions.



## Elevator Pitch

AI-Powered Demand Planning for Supply Chain Operations helps demand planners forecast future demand, identify planning exceptions, analyze demand trends, and generate actionable recommendations, enabling more accurate planning and smarter inventory decisions.
