---
name: Time Series Forecasting
description: ARIMA, Prophet, transformer-based models for temporal prediction
version: "1.0.0"
author: ROOT
tags: [machine-learning, time-series, forecasting, ARIMA, Prophet, transformers]
platforms: [all]
---

# Time Series Forecasting

Select and apply appropriate forecasting methods based on data characteristics and requirements.

## Method Selection Guide

| Method | Best For | Data Requirement | Strengths |
|--------|---------|-----------------|-----------|
| ARIMA | Single series, stationary or trend | 100+ observations | Interpretable, well-understood |
| Prophet | Business time series with seasonality | 365+ daily points | Handles holidays, missing data |
| XGBoost | Tabular features + temporal patterns | 1000+ rows | Feature-rich, non-linear |
| LSTM/GRU | Complex sequential dependencies | 10,000+ points | Captures long-range patterns |
| Transformers | Multi-variate, long horizons | 50,000+ points | State-of-the-art accuracy |

## Classical Methods

### ARIMA (AutoRegressive Integrated Moving Average)
1. **Test stationarity**: ADF test (p < 0.05 = stationary)
2. **Difference** if non-stationary: d = number of differences needed
3. **Select p, q**: Use ACF/PACF plots or auto_arima (AIC minimization)
4. **Fit and validate**: Walk-forward validation, never train on future data
5. **Residual check**: Residuals should be white noise (Ljung-Box test)

### Exponential Smoothing (ETS)
- Simple: level only (no trend, no seasonality)
- Holt: level + trend
- Holt-Winters: level + trend + seasonality
- Automatically selected via AIC in statsmodels or R's forecast package

## Modern Methods

### Prophet (Meta)
- Additive model: `y(t) = trend + seasonality + holidays + error`
- Handles missing data and outliers gracefully
- Configurable changepoints for trend shifts
- Add custom regressors (promotions, weather, events)

### ML-Based (XGBoost / LightGBM)
- Create lag features: `y(t-1), y(t-7), y(t-30)`
- Rolling statistics: mean, std, min, max over 7/30/90 day windows
- Calendar features: day of week, month, quarter, holiday flags
- Use walk-forward cross-validation (TimeSeriesSplit) — never random split

### Deep Learning (Transformers)
- Models: Temporal Fusion Transformer, PatchTST, TimesFM, Chronos
- Handle multi-variate inputs natively
- Attention mechanism captures long-range dependencies
- Require significant data and compute — overkill for simple problems

## Evaluation

### Metrics
- **MAE**: Average absolute error (interpretable in original units)
- **MAPE**: Percentage error (good for comparing across scales)
- **RMSE**: Penalizes large errors more than MAE
- **MASE**: Scale-free, compares to naive forecast (< 1 = better than naive)

### Validation Strategy
- Never use random train/test split — always temporal split
- Walk-forward: train on [0,t], predict [t+1,t+h], slide window forward
- Test on at least 3 different time periods to check robustness
- Compare all models to naive forecast (last value, seasonal naive)

## Common Pitfalls

- Lookahead bias: using future information in features (e.g., same-day volume to predict price)
- Overfitting to training window: model captures noise, not signal
- Ignoring regime changes: models trained on bull markets fail in bear markets
- Not accounting for prediction interval width — point forecasts without uncertainty are dangerous
