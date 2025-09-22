# Search Service Documentation

## Overview

The Search Service is a FastAPI-based application that provides intelligent search capabilities with conversation history management. It combines MongoDB Atlas vector search, OpenAI embeddings, Redis session management, and insights management to deliver contextual responses to user queries.

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   FastAPI App   │    │   MongoDB       │    │     Redis       │
│   (main.py)     │    │   (Vector DB)   │    │   (Sessions)    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         ├─ Search API           ├─ knowledge_bank       ├─ chat_history
         └─ Insights API         └─ insights             └─ session management
```

## Key Features

- **Vector-based Search**: Uses OpenAI embeddings and MongoDB Atlas vector search
- **Session Management**: Redis-based conversation history like ChatGPT
- **Contextual Responses**: LLM considers previous conversation context
- **Insights Management**: CRUD operations for knowledge insights
- **RESTful API**: Full OpenAPI/Swagger documentation at `/docs`

## Core Components

### 1. Search API (`search_api.py`)

Handles intelligent question answering with session-based context.

#### Key Functions:
- Vector similarity search using MongoDB Atlas
- Context-aware LLM responses
- Session management with Redis
- Chat history storage and retrieval

### 2. Insights API (`insights_api.py`)

Manages knowledge base insights and metadata.

#### Key Functions:
- List all insights (newest first)
- Retrieve detailed insight by ID
- Create new insights
- CRUD operations on knowledge base

### 3. Main Application (`main.py`)

FastAPI application that combines both APIs into a unified service.

## API Endpoints

### Search Endpoints

#### `POST /search`
Intelligent question answering with session context.

**Request:**
```json
{
  "question": "What is a C-ESMP and what does it include?",
  "session_id": "optional-session-id"
}
```

**Response:**
```json
{
    "question": "What is a C-ESMP and what does it include?",
    "answer": "The C-ESMP stands for Contractor's Environmental and Social Management Plan. It includes Management Strategies and Implementation Plans to manage environmental and social risks and impacts of the project, based on specific requirements. It must be reviewed every six months and approved before work can commence.",
    "follow_up_questions": [
        "What additional documents must a bidder submit?",
        "What is the purpose of the 'Performance Security'?",
        "What is the 'Letter of Acceptance'?"
    ],
    "session_id": "4523cde3-712e-43c5-93c7-f424f7922e15"
}
```

#### `GET /session_id/{session_id}`
Retrieve conversation history for a session.

**Response:**
```json
{
  "history": [
    {
      "session_id": "16054a4b-1e77-4828-b4f3-6f76db839d0e",
      "question": "What is a C-ESMP and what does it include?",
      "answer": "The C-ESMP stands for Contractor's Environmental and Social Management Plan. It includes Management Strategies and Implementation Plans to address environmental and social risks of the project. It must be based on specific E&S requirements and reviewed every six months for approval before project commencement."
    }
  ]
}
```

#### `GET /sessions`
List all active session IDs.

**Response:**
```json
["session-123", "session-456", "session-789"]
```

#### `DELETE /sessions/{session_id}`
Delete a session and its history.

**Response:**
```json
{"detail": "Session session-123 deleted."}
```

### Insights Endpoints

#### `GET /insights/`
List all insights (newest first).

**Response:**
```json
[
  {
    "id": "insight_I10",
    "insight": "The project team is leveraging both internal and external expertise to address challenges, with a collaborative approach to problem-solving and quality control.",
    "tags": [
      "Project: Roads & Infrastructure for Zone 1A",
      "Date: All Meetings",
      "Event: Multi-Meeting Insights",
      "Collaboration",
      "Quality Control",
      "Stakeholder Management"
    ]
  },
  {
    "id": "insight_I9",
    "insight": "A significant risk of 'contractor over-dependence' has been identified, as the current contractor holds three other CRDA contracts, necessitating a new monitoring protocol.",
    "tags": [
      "Project: Roads & Infrastructure for Zone 1A",
      "Date: 10 December 2025",
      "Event: Finance & Risk Review",
      "Risk Management",
      "Contractor Over-commitment"
    ]
  },
  {
    "id": "insight_I8",
    "insight": "The projectâ€™s payment process is tied directly to performance and external verification, indicating a strong focus on quality assurance before financial disbursements.",
    "tags": [
      "Project: Roads & Infrastructure for Zone 1A",
      "Date: 10 December 2025",
      "Event: Finance & Risk Review",
      "Payments",
      "Quality Control"
    ]
  },
  {
    "id": "insight_I7",
    "insight": "Environmental compliance, particularly regarding dust suppression, has been identified as a key area of concern that requires immediate action and a formal audit.",
    "tags": [
      "Project: Roads & Infrastructure for Zone 1A",
      "Date: 20 July 2025",
      "Event: Technical Review",
      "Environmental Compliance",
      "Dust Suppression"
    ]
  },
  {
    "id": "insight_I6",
    "insight": "The project is currently facing a 30-day delay due to external factors like monsoon rains, requiring the development of a formal recovery plan to get back on schedule.",
    "tags": [
      "Project: Roads & Infrastructure for Zone 1A",
      "Date: 20 July 2025",
      "Event: Technical Review",
      "Progress",
      "Delay"
    ]
  },
  {
    "id": "insight_I5",
    "insight": "Initial project kickoff established a clear framework for the 'Roads & Infrastructure for Zone 1A' project, including timelines, financial structures, and legal clauses.",
    "tags": [
      "Project: Roads & Infrastructure for Zone 1A",
      "Date: 15 January 2025",
      "Event: Kickoff Meeting",
      "Finance",
      "Legal"
    ]
  },
  {
    "id": "insight_I4",
    "insight": "The bidding process has a clear and multi-tiered system for resolving disputes and complaints.",
    "tags": [
      "Project: Amaravati Capital City Development Program",
      "Date: 31.12.2024",
      "Document: Package - 3 (Neerukonda Reservior)",
      "Dispute Resolution",
      "Legal"
    ]
  },
  {
    "id": "insight_I3",
    "insight": "There is a strong emphasis on environmental and social compliance, backed by specific requirements and penalties.",
    "tags": [
      "Project: Amaravati Capital City Development Program",
      "Date: 31.12.2024",
      "Document: Package - 3 (Neerukonda Reservior)",
      "Environmental",
      "Social",
      "Compliance"
    ]
  },
  {
    "id": "insight_I2",
    "insight": "The qualification criteria for bidders are comprehensive, focusing on financial stability, past performance, and technical capacity.",
    "tags": [
      "Project: Amaravati Capital City Development Program",
      "Date: 31.12.2024",
      "Document: Package - 3 (Neerukonda Reservior)",
      "Qualification Criteria",
      "Experience"
    ]
  },
  {
    "id": "insight_I1",
    "insight": "The bidding process has strict financial and security requirements to ensure the bidder's capability and commitment.",
    "tags": [
      "Project: Amaravati Capital City Development Program",
      "Date: 31.12.2024",
      "Document: Package - 3 (Neerukonda Reservior)",
      "Financials",
      "Security"
    ]
  }
]
```

#### ``POST /search``
Get detailed insight by ID.

**Request**
```json
{
"question": "The project team is leveraging both internal and external expertise to address challenges, with a collaborative approach to problem-solving and quality control.",
"session_id": "optional-session-id"

}
```

**Response:**
```json
{
    "question": "The project team is leveraging both internal and external expertise to address challenges, with a collaborative approach to problem-solving and quality control.",
    "answer": "The project team's collaborative approach includes utilizing internal teams like the Chief Engineer's office and external parties like the Project Supervision Consultant to address challenges and ensure quality control. Multiple stakeholders, including the Commissioner, Chief Engineer, Finance Officer, and Legal Advisor, are involved in discussions to consider all aspects of the project.",
    "follow_up_questions": [
        "Who are the key external parties involved in the project?",
        "How does the project ensure compliance with quality standards?",
        "What is the final authority on decisions regarding project timelines and penalties?"
    ],
    "session_id": "908d2587-72f7-4499-8f5d-fdb343e79047"
}
```

## Data Models

### Request Models

#### `QuestionRequest`
```python
class QuestionRequest(BaseModel):
    question: str                    # Required: User's question
    session_id: Optional[str] = None # Optional: Session ID (auto-generated if not provided)
```

#### `InsightResponse`
```python
# Response model for listing insights
class InsightResponse(BaseModel):
    id: str                         # Id
    insight: str                    # Insight
    tags: list[str]                 # Insight tags

```

### Response Models

#### `SearchResponse`
```python
class SearchResponse(BaseModel):
    question: str                    # Original user question
    answer: str                      # LLM-generated answer
    follow_up_questions: List[str]   # Suggested follow-up questions
    session_id: str                  # Session identifier
```

#### `HistoryResponse`
```python
class HistoryResponse(BaseModel):
    history: List[HistoryItem]       # List of conversation items

class HistoryItem(BaseModel):
    session_id: str                  # Session identifier
    question: str                    # User's question
    answer: str                      # System's answer
```

## Environment Variables

Create a `.env` file with the following variables:

```env
# OpenAI Configuration
OPENAI_API_KEY=your_openai_api_key_here

# MongoDB Configuration
mongo_connection_string=mongodb+srv://username:password@cluster.mongodb.net/

# Redis Configuration
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=optional_password

# Vector Search Configuration
VECTOR_INDEX_NAME=questions_index
```

## Database Schema

### MongoDB Collections

#### `knowledge_bank` Collection
```json
"_id":"ObjectId("68d0e1a5f87abd89b31a45a2")"
"question_id":"Q5"
"user_question":"What are the grounds for the forfeiture of a Bid Security?"
"detailed_answer":"The Bid Security may be forfeited if a bidder withdraws, modifies, or …"
"follow_up_question_1":"Can I submit a conditional bid?"
"follow_up_question_2":"Who will pay for the cost of bidding?"
"follow_up_question_3":"What are the common sections of a bidding document?"
"question_embedding":Array (1536)
```

#### `insights` Collection
```json
{
  "_id": {
    "$oid": "68d16451d3d0872f08df4a75"
  },
  "Insight ID": "insight_I1",
  "insight": "The bidding process has strict financial and security requirements to ensure the bidder's capability and commitment.",
  "detailed_answer": "Bidders must have a strong financial position, with liquid assets of at least Rs. 58.84 Cr.\nA non-refundable bid processing fee of Rs. 20,000 and a transaction fee of 0.03% of the Estimated Contract Value (ECV) are required.\nA Bid Security, typically in the form of a bank guarantee, is mandatory. A separate **Performance Security** (2.5% of contract value) and an **E&S Performance Security** (0.1% of contract value) are required after the contract is awarded.",
  "follow_up_question_1": "What happens if a bidder fails to provide the required Performance Security or sign the contract?",
  "follow_up_question_2": "What are the accepted forms of Bid Security?",
  "follow_up_question_3": "What is the purpose of the 'Performance Security'?",
  "tags": "['Project: Amaravati Capital City Development Program', 'Date: 31.12.2024', 'Document: Package - 3 (Neerukonda Reservior)', 'Financials', 'Security']"
}
```

### Redis Data Structure

#### Chat History Storage
```
{
  "history": [
    {
      "session_id": "16054a4b-1e77-4828-b4f3-6f76db839d0e",
      "question": "What is a C-ESMP and what does it include?",
      "answer": "The C-ESMP stands for Contractor's Environmental and Social Management Plan. It includes Management Strategies and Implementation Plans to address environmental and social risks of the project. It must be based on specific E&S requirements and reviewed every six months for approval before project commencement."
    }
  ]
}
```

## Installation & Setup

### Prerequisites

- Python 3.11+
- MongoDB Atlas with vector search enabled
- Redis server
- OpenAI API key

### Local Development

1. **Clone Repository**
   ```bash
   git clone <repository-url>
   cd search_service
   ```

2. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Environment Setup**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

4. **Run Application**
   ```bash
   uvicorn main:app --host 0.0.0.0 --port 8000 --reload
   ```

5. **Access Documentation**
   - API Docs: http://localhost:8000/docs
   - ReDoc: http://localhost:8000/redoc

### Docker Deployment

1. **Build Image**
   ```bash
   docker build -t search-service .
   ```

2. **Run Container**
   ```bash
   docker run -d \
     --name search-service \
     -p 8000:8000 \
     --env-file .env \
     search-service
   ```

3. **Docker Compose** (Optional)
   ```yaml
   version: '3.8'
   services:
     app:
       build: .
       ports:
         - "8000:8000"
       environment:
         - OPENAI_API_KEY=${OPENAI_API_KEY}
         - mongo_connection_string=${MONGO_URI}
         - REDIS_HOST=redis
       depends_on:
         - redis
     
     redis:
       image: redis:7-alpine
       ports:
         - "6379:6379"
   ```


### cURL Examples

```bash
# Ask a question
curl -X POST "http://localhost:8000/search" \
  -H "Content-Type: application/json" \
  -d '{"question": "What is machine learning?"}'

# Get conversation history
curl -X GET "http://localhost:8000/history/session-123"

# List all sessions
curl -X GET "http://localhost:8000/sessions"

# Delete a session
curl -X DELETE "http://localhost:8000/sessions/session-123"

# List insights
curl -X GET "http://localhost:8000/insights/"

# Get specific insight
curl -X GET "http://localhost:8000/insights/insight-1"
```

## Error Handling

The API uses standard HTTP status codes:

- `200`: Success
- `404`: Resource not found
- `500`: Internal server error

Error responses follow this format:
```json
{
  "detail": "Error message description"
}
```

## Monitoring & Logging

### Health Check

```bash
curl -X GET "http://localhost:8000/health"
```

### Logs

Application logs include:
- Request/response details
- Database connection status
- Redis operations
- OpenAI API calls
- Error traces

## Performance Considerations

### Vector Search Optimization

- **numCandidates**: Higher values improve accuracy but increase latency
- **limit**: Controls number of results retrieved
- **Index Configuration**: Ensure proper vector index on `question_embedding`

### Redis Optimization

- **Memory Usage**: Monitor chat history storage
- **TTL Settings**: Consider setting expiration on old sessions
- **Connection Pooling**: Use Redis connection pools for high load

### OpenAI API Optimization

- **Rate Limiting**: Implement request rate limiting
- **Caching**: Cache embeddings for repeated queries
- **Model Selection**: Balance cost vs. quality with model choice

## Security Considerations

### API Security

- **Rate Limiting**: Implement request rate limiting
- **Authentication**: Add API key authentication for production
- **Input Validation**: Validate all input parameters
- **CORS**: Configure CORS for web applications

### Data Privacy

- **Session Data**: Consider encrypting chat history
- **PII Handling**: Implement PII detection and masking
- **Data Retention**: Set retention policies for chat history

## Troubleshooting

### Common Issues

1. **MongoDB Connection Failed**
   - Check connection string format
   - Verify network access to MongoDB Atlas
   - Ensure database and collection exist

2. **Redis Connection Failed**
   - Verify Redis server is running
   - Check REDIS_HOST and REDIS_PORT
   - Test Redis connectivity

3. **OpenAI API Errors**
   - Verify API key is valid
   - Check API rate limits
   - Monitor API quota usage

4. **Vector Search Issues**
   - Ensure vector index exists
   - Check embedding dimensions match
   - Verify index name configuration

### Debug Mode

Run with debug logging:
```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --log-level debug
```

## Contributing

### Development Workflow

1. Fork repository
2. Create feature branch
3. Implement changes
4. Add tests
5. Submit pull request

### Code Standards

- Follow PEP 8 style guide
- Add type hints
- Include docstrings
- Write comprehensive tests

## License

[Insert your license information here]

## Support

For support and questions:
- Create GitHub issues for bugs
- Check documentation first
- Provide detailed error messages and logs

---

**Version**: 1.0.0  
**Last Updated**: September 2025