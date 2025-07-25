# Chat Box Assistant Backend

A FastAPI + PostgreSQL backend for the Chat Box Assistant application.

## Project Structure

```
chatbox-backend/
├── app/
│   ├── main.py           # FastAPI application
│   ├── database.py       # Database configuration
│   ├── models.py         # SQLAlchemy models
│   ├── schemas.py        # Pydantic schemas
│   └── routers/
│       └── chat.py       # Chat-related API endpoints
├── requirements.txt      # Python dependencies
└── README.md            # This file
```

## Prerequisites

- Python 3.8+
- PostgreSQL 13+
- pip (Python package manager)

## Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd chatbox-backend
   ```

2. **Create and activate a virtual environment**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip3 install -r requirements.txt
   ```

4. **Set up PostgreSQL**
   - Create a new PostgreSQL database named `chatbox_db`
   - Update the database URL in `app/database.py` with your PostgreSQL credentials

5. **Run database migrations**
   (We'll add Alembic migrations in a future update)

6. **Run the development server**
   ```bash
   uvicorn app.main:app --reload
   ```

7. **Access the API documentation**
   - Open your browser to: http://localhost:8000/docs

## Environment Variables

Create a `.env` file in the root directory with the following variables:

```
DATABASE_URL=postgresql://user:password@localhost/chatbox_db
SECRET_KEY=your-secret-key-here
```

## API Endpoints

- `GET /` - Welcome message
- `GET /api/chat/` - Chat endpoints (to be implemented)

## Next Steps

- [ ] Add user authentication
- [ ] Implement chat endpoints
- [ ] Add WebSocket support for real-time chat
- [ ] Add unit tests
- [ ] Set up CI/CD pipeline
