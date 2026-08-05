# Finance AI Agent

An intelligent AI-powered financial assistant that transforms raw bank statements into structured financial insights, spending analytics, and natural language question answering.

Unlike traditional bank statement analyzers that rely on bank-specific templates or regular expressions, Finance AI Agent uses a document understanding pipeline to automatically identify transaction regions, normalize transactions, categorize spending, generate reports, and answer financial questions across multiple banks.

---

## Features

### 📄 Intelligent Document Understanding

- Automatic document layout detection
- Mixed-format statement support
- Header/Footer removal
- Metadata removal
- Transaction region detection
- Automatic transaction segmentation
- Multi-date format support
- Multi-page PDF support

Supported layouts include:

- Table-based statements
- Mixed layout statements
- Semi-structured statements

---

## Transaction Extraction

Automatically extracts:

- Date
- Description
- Debit/Credit
- Running Balance
- Transaction Type

Normalizes transactions into a consistent internal schema regardless of bank format.

---

## Merchant Normalization

Automatically converts noisy transaction descriptions into clean merchant names.

Examples

| Raw Description | Normalized Merchant |
|----------------|--------------------|
| UPI/LANDLORD/RENTPAY | Landlord (Rent) |
| SALARY CREDIT - INFOTECH SOLUTIONS PVT LTD | Infotech Solutions |
| UPI/AMAZONPAY/VENDOR4521 | Amazon |
| POS 5412 RELIANCE FRESH | Reliance Fresh |
| IMPS-HDFC-RAHUL | Rahul Sharma |

---

## Automatic Transaction Categorization

Transactions are categorized into:

- Food
- Shopping
- Travel
- Bills
- Fuel
- Entertainment
- Healthcare
- Insurance
- Groceries
- Rent
- Salary
- Interest
- Transfers
- Cash Withdrawal
- EMI
- Refunds

---

## Financial Analytics

Automatically computes:

- Total Income
- Total Expenses
- Opening Balance
- Closing Balance
- Highest Balance
- Lowest Balance
- Savings
- Savings Rate
- Budget Health
- Category-wise Spending
- Merchant-wise Spending
- Largest Expense
- Largest Credit
- Largest Debit
- Top Spending Categories
- Top Merchants
- Refund Summary
- Salary Summary
- Interest Summary
- Recurring Expenses
- Financial Recommendations

---

## Natural Language Question Answering

Ask questions naturally.

Examples:

### Balance

- What is my opening balance?
- What is my closing balance?
- What was my highest balance?
- Did my balance exceed ₹1 lakh?
- What was my balance after my salary credit?

---

### Transactions

- Show my largest debit
- Show my largest credit
- Show transactions above ₹5000
- Show transactions below ₹500
- Show transactions on 17 Aug
- Show transactions after 10 Aug
- Show transactions between two dates

---

### Spending

- How much did I spend?
- How much did I spend this month?
- Where is my money going?
- Expense summary
- Financial summary

---

### Categories

- How much did I spend on Food?
- How much did I spend on Shopping?
- How much did I spend on Fuel?
- How much did I spend on Travel?
- Show Insurance transactions

---

### Merchant Queries

- How much did I spend on Amazon?
- How much did I spend on Swiggy?
- How much did I spend on Google Play?
- Show Flipkart transactions
- Show Netflix transactions

Supports typo correction such as:

- swigy
- shpooing
- entertainmnet
- googel play

---

### Banking Operations

- Show UPI transactions
- Show NEFT transfers
- Show IMPS transfers
- Show RTGS transfers
- Show ATM withdrawals
- Show POS transactions

---

### Refunds

- Did I receive any refunds?
- Show refund transactions
- Refund summary

---

### Salary & Interest

- Show salary transactions
- How much salary did I receive?
- Show interest credits
- How much interest did I earn?

---

### Analytics

- Which category has the highest spending?
- Show all categories
- Top merchants
- What percentage of my spending was on Food?
- What percentage of my spending was on Shopping?
- Did I overspend?
- Summarize my financial habits
- What can I do to save more money?

---

### Conversational Follow-up

The assistant remembers the current context.

Example

```
User:
Show my largest debit

Assistant:
UPI/LANDLORD/RENTPAY

User:
Who was it paid to?

Assistant:
Landlord (Rent)

User:
When did it happen?

Assistant:
15 Aug 2024

User:
What category was it?

Assistant:
Rent

User:
Explain that transaction
```

---

## AI Components

### Report Generation

Model

- Qwen2.5:1.5B

Responsible for:

- Financial report generation
- Summary generation
- Recommendations

---

### Validation

Model

- Gemma3:1B

Responsible for:

- Output validation
- Response verification

---

## Project Architecture

```
PDF Statement
      │
      ▼
Document Understanding
      │
      ▼
Layout Detection
      │
      ▼
Transaction Region Detection
      │
      ▼
Transaction Segmentation
      │
      ▼
Field Extraction
      │
      ▼
Transaction Normalization
      │
      ▼
Validation
      │
      ▼
Knowledge Base
      │
      ▼
Analytics Engine
      │
      ▼
Question Answering Engine
      │
      ▼
Natural Language Response
```

---

## Supported Banks

Tested on

- Union Bank of India
- ICICI Bank
- State Bank of India (SBI)

The architecture is designed to generalize across different statement formats without relying on bank-specific parsing logic.

---

## Technology Stack

- Python
- Ollama
- Gemma 3
- Qwen 2.5
- PDF Processing
- Document Understanding Pipeline
- NLP
- Rule-based + AI Hybrid Analytics

---

## Key Design Principles

- No bank-specific regexes
- No hardcoded layouts
- Generalized transaction extraction
- Modular analytics engine
- Extensible QA architecture
- Bank-independent processing
- AI-assisted financial reporting

---

## Example Workflow

```
Bank Statement PDF
        │
        ▼
Understand Document Layout
        │
        ▼
Extract Transactions
        │
        ▼
Normalize Data
        │
        ▼
Categorize Spending
        │
        ▼
Generate Financial Analytics
        │
        ▼
Answer Natural Language Questions
```

---

## Future Improvements

- CSV and Excel statement support
- Investment portfolio analytics
- Budget planning
- Monthly financial trends
- Multi-statement comparison
- Expense forecasting
- Dashboard UI
- Voice-enabled financial assistant

---

## License

This project is intended for educational and research purposes.