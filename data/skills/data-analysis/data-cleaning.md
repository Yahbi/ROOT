---
name: Data Cleaning
description: Missing values, outlier handling, normalization, deduplication, and data quality
version: "1.0.0"
author: ROOT
tags: [data-analysis, data-cleaning, missing-values, outliers, quality]
platforms: [all]
---

# Data Cleaning

Transform raw, messy data into reliable, analysis-ready datasets.

## Missing Value Handling

### Diagnosis
- Calculate missing rate per column: > 50% missing = consider dropping the column
- Check if missing is random (MCAR), depends on observed data (MAR), or depends on missing value itself (MNAR)
- Visualize missingness patterns: are certain columns always missing together?

### Imputation Strategies
| Method | When to Use | Limitation |
|--------|------------|------------|
| Drop rows | < 5% rows affected, MCAR | Loses data, can introduce bias |
| Mean/median | Numerical, random missingness | Reduces variance, distorts distribution |
| Mode | Categorical | Overrepresents most common category |
| Forward/backward fill | Time series | Assumes stability between observations |
| KNN imputation | Complex relationships | Computationally expensive for large data |
| Multiple imputation | Statistical analysis | Complex, requires understanding of method |
| Missingness indicator | ML models | Add binary column: `is_X_missing` + impute |

## Outlier Detection and Handling

### Detection Methods
1. **Statistical**: Z-score > 3 or IQR method (1.5 * IQR beyond quartiles)
2. **Visual**: Box plots, scatter plots — human judgment on what looks wrong
3. **Domain knowledge**: Values physically impossible (negative age, temperature > 200C)
4. **Isolation Forest**: ML-based, handles multi-dimensional outliers

### Handling Strategies
- **Investigate first**: Is the outlier a data error or a real extreme value?
- **Cap/winsorize**: Replace values beyond 1st/99th percentile with the boundary value
- **Log transform**: Reduces impact of extreme values (for right-skewed data)
- **Separate model**: If outliers follow different patterns, model them separately
- **Never delete blindly**: Document every outlier removal decision

## Deduplication

### Exact Duplicates
- `df.drop_duplicates()` — remove identical rows
- Check subset of columns: same person with different timestamps = not a true duplicate

### Fuzzy Duplicates
- Name matching: use fuzzy string matching (fuzzywuzzy, rapidfuzz) with threshold > 85%
- Address matching: normalize format first (lowercase, expand abbreviations)
- Record linkage: combine multiple fields (name + email + phone) with weighted scoring
- Always human-review borderline cases before merging

## Data Normalization

### String Standardization
- Trim whitespace, consistent case (lowercase or titlecase)
- Standardize formats: dates (ISO 8601), phones (E.164), currencies (consistent decimal places)
- Map variations to canonical values: "US", "USA", "United States" → "US"
- Remove invisible Unicode characters (zero-width spaces, BOM)

### Numerical Standardization
- Unit conversion: ensure all measurements use the same unit
- Currency conversion: use consistent point-in-time exchange rates
- Precision: round to appropriate decimal places for the domain

## Data Quality Checklist

- [ ] Schema validated: correct data types per column
- [ ] Missing values quantified and handled with documented strategy
- [ ] Outliers investigated: errors corrected, real extremes documented
- [ ] Duplicates removed (exact and fuzzy)
- [ ] Strings standardized (case, format, encoding)
- [ ] Numerical ranges validated against domain constraints
- [ ] Referential integrity checked (foreign keys valid)
- [ ] Data profiling report generated: distributions, cardinality, completeness per column
