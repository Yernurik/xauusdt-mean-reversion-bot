# Automated Mean-Reversion Trading Bot (XAUUSDT) 👋

An automated, quantitative trading bot designed for linear perpetual futures trading on **Bybit**. The system implements a statistical mean-reversion strategy driven by rolling Z-Score analysis, coupled with dynamic volatility-based risk management.

## ⚡ Current Status: `LIVE`
The bot is fully operational and executing live market orders via the Bybit API.

---

## 📈 Strategy & Mathematical Logic

The bot operates on the **15-minute (15m)** timeframe for **XAUUSDT (Gold)**[cite: 1]. It systematically exploits short-term price deviations from the statistical fair value.

### 1. Alpha Signal Generation (Z-Score)
The core engine computes a rolling **Z-Score** to measure price deviation in terms of standard deviations ($\sigma$):

*   **SHORT Entry:** $\text{Z-Score} \ge 3.0$ (Extreme overbought condition)[cite: 1].
*   **LONG Entry:** $\text{Z-Score} \le -3.0$ (Extreme oversold/panic condition)[cite: 1].

### 2. Risk Management (Dynamic ATR)
To survive shifting market regimes, the bot utilizes an **ATR (14-period)** indicator to scale risk dynamically[cite: 1]:
*   **Position Size:** Fixed minimum of `0.01 Lot`[cite: 1].
*   **Stop Loss (SL):** Placed at $1.5 \times \text{ATR}$ from the entry price to adapt to current volatility[cite: 1].
*   **Breakeven Logic:** Once the trade progresses $50\%$ towards the profit target ($0.5 \text{ to target}$), the Stop Loss automatically moves to the entry price to secure a risk-free trade[cite: 1].

### 3. Exit Mechanism (Take Profit)
*   **Z-Exit Strategy:** Positions are closed via market orders when the price reverts near its mean, specifically at $\text{Z-Score} = 0.2$[cite: 1].

---

## 🛠 Tech Stack & Architecture

*   **Language:** Python 3.x
*   **Exchange Integration:** Bybit API (via `pybit` or `requests`)
*   **Data & Math:** `pandas`, `numpy` (for rolling statistics and Z-score calculation)
*   **Execution Infrastructure:** High-performance event loop designed to handle live order execution, connection retries, and position monitoring.

---

## 🚀 Getting Started

### Prerequisites
Make sure you have Python installed, then install the required dependencies:
```bash
pip install pandas numpy pybit python-dotenv
