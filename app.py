import streamlit as st
import pandas as pd
import plotly.express as px

st.title("AI-Powered Demand Planning")

st.header("Sales Data")

df = pd.read_csv("data/sales_data.csv")

st.dataframe(df)

fig = px.line(
    df,
    x="Month",
    y="UnitsSold",
    title="Historical Demand Trend"
)

st.plotly_chart(fig)

avg_sales = df["UnitsSold"].mean()
forecast = round(avg_sales * 1.1)

st.header("Forecast")

st.success(
    f"Forecasted Demand Next Month: {forecast} units"
)

st.write(
    "Recommendation: Review inventory levels and replenish stock accordingly."
)
