## Frameworks and Major Libraries

### Core application frameworks

- **FastAPI** – Backend web framework for the API (`api/`).
  - Docs: https://fastapi.tiangolo.com/

- **Next.js** – React framework for the web dashboard (`web/`).
  - Docs: https://nextjs.org/docs

- **React** – UI component framework (hooks, components, pages).
  - Docs: https://react.dev/

- **SQLAlchemy** – ORM and database access layer (`models/`, `storage/`).
  - Docs: https://docs.sqlalchemy.org/

- **TypeScript** – Typed JavaScript for the frontend.
  - Docs: https://www.typescriptlang.org/docs/

- **Tailwind CSS** – Utility-first CSS used via class names (e.g. `text-zinc-500`, `bg-emerald-600`).
  - Docs: https://tailwindcss.com/docs

- **AWS CDK (Python)** – Infrastructure-as-code for the full cloud stack: VPC, RDS PostgreSQL, Lambda (Docker image), HTTP API Gateway v2, and Amplify Hosting (`infrastructure/`). Supports `dev`, `staging`, and `production` environments via `infrastructure/config.py`.
  - Docs: https://docs.aws.amazon.com/cdk/latest/guide/home.html

- **AWS Amplify Hosting** – SSR hosting for the Next.js frontend. Connects to GitHub for CI/CD auto-build. Configured via `amplify.yml` and `infrastructure/stacks/amplify_stack.py`.
  - Docs: https://docs.aws.amazon.com/amplify/latest/userguide/welcome.html

- **Docker** – Used for packaging the FastAPI Lambda function (`Dockerfile.lambda`), required to include large scientific dependencies (NumPy, Pandas, scikit-learn, statsmodels) that exceed the Lambda zip limit.

### Supporting tools and libraries

- **Pydantic** – Data validation and settings for request/response models and configuration.
  - Docs: https://docs.pydantic.dev/

- **httpx** – HTTP client used for external API calls (FRED, BLS, BEA, etc.).
  - Docs: https://www.python-httpx.org/

- **Backtrader** – Backtesting engine for options and equity strategies.
  - Docs: https://www.backtrader.com/docu/

- **D3.js** – Charting and data visualization for economic series charts.
  - Docs: https://d3js.org/ (API: https://github.com/d3/d3/wiki)

- **ESLint** – Linting for the frontend TypeScript/React code.
  - Docs: https://eslint.org/docs/latest/

- **Pytest** – Python test runner for the backend (`tests/`). 244 tests as of 2026-03, covering all major modules.
  - Docs: https://docs.pytest.org/

- **chromadb** *(optional)* – Vector database for semantic search in the RAG knowledge base. If installed (`pip install chromadb`), it replaces the built-in TF-IDF retrieval with semantic search. Not included in `requirements.txt` (optional dependency).
  - Docs: https://docs.trychroma.com/

- **OpenAI Python SDK** – Listed in `requirements.txt` (`openai`). Used by the Research Assistant for LLM-generated explanations when `OPENAI_API_KEY` is set (env) or an API key is saved under Settings → AI & Research. Otherwise a structured placeholder is returned. If you omitted it from an env, run `pip install openai`.
  - Docs: https://platform.openai.com/docs/

