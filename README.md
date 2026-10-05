# Retail Sales ETL Pipeline & Power BI Reporting

An end-to-end data pipeline that processes 540,000+ raw retail transaction records,
validates and converts currency using ECB exchange rates, runs automated data quality
checks, and models the result into a star schema for Power BI reporting.

## Report preview

**Executive overview** — gross/net sales, refunds, orders, average order value, monthly
trend, sales by country, and concentration/seasonality/growth indicators.

![Executive overview](docs/01-visao-executiva.png)

**Trends & markets** — monthly net sales with month-over-month variation, country
performance breakdown, and UK vs. rest-of-world share over time.

![Trends and markets](docs/02-evolucao-mercados.png)

**Products** — top-selling products by net sales, quantity vs. gross sales relationship,
and full product-level breakdown with refund weight.

![Products](docs/03-produtos.png)

**Customers** — identified vs. unidentified customers, repeat-customer rate, top
customers by gross sales, and order-frequency distribution.

![Customers](docs/04-clientes.png)

**Data quality & methodology** — full source-to-model reconciliation, exchange rate
coverage by month, data sources with retrieval dates, and a documented log of every
data issue found and the decision taken for it.

![Data quality and methodology](docs/05-qualidade-metodologia.png)

## What it does

1. **Extract** — reads raw transaction data from Excel, preserving original codes and types.
2. **Clean & classify** — deduplicates records and classifies each row (sale, refund,
   non-commercial movement) using an explicit, documented rule set.
3. **Currency conversion** — validates monthly ECB exchange rates (coverage, uniqueness,
   positivity) and converts GBP to EUR row by row.
4. **Data quality** — runs 10+ automated checks (critical and non-critical), covering
   reconciliation, referential integrity and duplicate detection. The pipeline stops
   before writing output if a critical check fails.
5. **Modeling** — builds a star schema: one fact table (`fVendas`) and five dimension
   tables (product, customer, country, calendar, exchange rate).
6. **Reporting** — a Power BI report built on top, using Power Query and DAX.

## Tech stack

Python · pandas · openpyxl · pytest · Power BI · Power Query (M) · DAX

## Project structure

```
.
├── etl/
│   ├── executar_etl.py        # entry point
│   ├── configuracao.py        # paths, sources, business rules
│   ├── functions/             # the 6 pipeline steps
│   ├── powerquery/             # exported Power Query (M) scripts
│   └── requirements.txt
├── relatorio/
│   └── Analise_Vendas.pbix    # Power BI report
├── docs/                      # report screenshots (this README)
└── dados/
    └── origem/                # raw data goes here (see Data source below)
```

## Running it

```bash
pip install -r etl/requirements.txt
python etl/executar_etl.py
```

Runs fully offline against local files in `dados/origem/`. Takes ~2 minutes (reading the
Excel file is the slowest step). Output tables are written to `dados/tratados/` and
quality reports to `dados/qualidade/`.

## Data source

This project uses the public [UCI Online Retail dataset](https://archive.ics.uci.edu/dataset/352/online+retail)
and [ECB monthly GBP/EUR exchange rates](https://data.ecb.europa.eu/). Download links and
expected file names are in `etl/configuracao.py`.

## Highlights

- **Deterministic & idempotent** — running the pipeline twice on the same input produces
  identical output; nothing is appended, files are replaced atomically.
- **Fails safe** — if a critical data quality check fails, the pipeline stops before
  writing anything, and the previous successful output is left untouched.
- **Fully tested** — the classification and reconciliation logic is covered by an
  automated test suite using synthetic data, including edge cases.
