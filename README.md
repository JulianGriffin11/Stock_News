# Stock News

An automated investment research pipeline that collects financial news and SEC filings, processes them with PostgreSQL and AI, and emails a personalized weekly digest.

## Why I Built This 💡

I wanted to automate part of my own investment research. Instead of checking news and SEC filings across several sources every week, I wanted one digest focused on the companies I actually follow.

## How It Works 

```text
 Financial news + SEC filings
                ↓
          Data ingestion
                ↓
           PostgreSQL
                ↓
      Agent summarization
                ↓
          Agent ranking
                ↓
           Agent email
```

Each week the pipeline pulls Yahoo Finance headlines and SEC filings (8-K, 10-Q, 10-K, and selected Form 4s) for a personal watchlist. New items are stored in Postgres, summarized, ranked against my investment criteria, and sent as one email. GitHub Actions runs this on Sunday.

## Tech Stack 🛠️


| Technology           | Purpose                                      |
| -------------------- | -------------------------------------------- |
| Python               | Application logic and pipeline orchestration |
| PostgreSQL / SQL     | Storage, queries, and run state              |
| SQLAlchemy / Alembic | Data access and migrations                   |
| OpenAI API           | Summarization, ranking, and email copy       |
| Jinja2               | HTML email generation                        |
| Resend               | Email delivery                               |
| GitHub Actions       | Weekly scheduled runs                        |




## AI Pipeline 🤖

Python and SQL handle structured data, storage, filtering, and control flow. The LLM is used where interpretation and language matter.

1. Summarize each new item
2. Rank this week's summaries by relevance
3. Write the email subject and overview

Model output is returned as structured JSON so the rest of the application can store it and render the email in code.

## Database 🗄️

PostgreSQL stores collected articles and filings, tracks what has already been summarized, and keeps state for each weekly run. SQL queries decide which items are new, which belong to the current week, and whether a digest has already been sent.

## What I Learned 📚

Building an AI application is not just calling an LLM. The surrounding pipeline — ingestion, storage, business logic, and delivery — is what makes it usable.

Predictable work belongs in code. Python and SQL own fetching, storage, and scheduling. The model is reserved for summarization, relevance, and writing.

## Future Improvements 🚀

- Improve relevance ranking
- Add monitoring when a weekly run fails
- Add automated tests for the pipeline



## Project Status ✅

The core pipeline is deployed and runs automatically each week. This is a completed portfolio project. Future work would extend it, not finish the core system.