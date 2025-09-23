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
Intelligent question answering with chat context.

**Request:**
```json
{
  "question": "What is a C-ESMP and what does it include?",
  "chat_type": "question",
  "chat_id": "optional-chat-id"
}
```

**Response:**
```json
{
  "question": "What additional documents must a bidder submit?",
  "answer": "In addition to the Technical Proposal, bidders must submit an Outline Quality Control & Assurance Plan, an Outline Social, Safety, Health, and Environment Plan, Management Strategies and Implementation Plans (MSIPs), a Programme for execution of Work, a Logistic Plan, an Organization Chart, a plan for deploying Plant & Machinery, a plan for procurement of key materials, and a plan for engaging specialized agencies for specific work components.",
  "follow_up_questions": [
    "What is a C-ESMP and what does it include?",
    "How is the bid evaluated?",
    "What are the rules regarding the use of bidding forms?"
  ],
  "chat_id": "e856228f-64cd-42e4-9463-1d2f8cf3d132",
  "chat_type": "question",
  "title": "Understanding C-ESMP and its inclusions"
}
```

#### `GET /chats/{chat_id}?chat_type=question/insight`
Retrieve conversation history for a session.

**Response:**
```json
{
  "chat_id": "e856228f-64cd-42e4-9463-1d2f8cf3d132",
  "chat_type": "question",
  "user_id": "admin",
  "history": [
    {
      "question": "What is a C-ESMP and what does it include?",
      "answer": "The C-ESMP stands for Contractor's Environmental and Social Management Plan. It comprises Management Strategies and Implementation Plans (MSIPs) to address environmental and social risks and impacts of a project. The plan must adhere to specific E&S requirements outlined in Appendices I and II of Part VI, reviewed every six months, and approved by the Project Management Consultant (PMC) and Employer before work can begin.",
      "ts": 1758619735
    },
    {
      "question": "What additional documents must a bidder submit?",
      "answer": "In addition to the Technical Proposal, bidders must submit an Outline Quality Control & Assurance Plan, an Outline Social, Safety, Health, and Environment Plan, Management Strategies and Implementation Plans (MSIPs), a Programme for execution of Work, a Logistic Plan, an Organization Chart, a plan for deploying Plant & Machinery, a plan for procurement of key materials, and a plan for engaging specialized agencies for specific work components.",
      "ts": 1758619791
    }
  ]
}
```

#### `GET /chats?include_insight=true&include_question=true'`
List all active session IDs.

**Response:**
```json
[
  {
    "chat_id": "123",
    "title": "hi"
  },
  {
    "chat_id": "insight_I10",
    "title": "The project team is leveraging both internal and external ex..."
  },
  {
    "chat_id": "insight_I10",
    "title": "The project team is leveraging both internal and external ex..."
  },
  {
    "chat_id": "02274b6e-5764-4503-bb59-3fbc5796d28b",
    "title": "Understanding C-ESMP and its components"
  },
  {
    "chat_id": "53d67ea5-23e9-4356-b49c-4ffb72a8c2c7",
    "title": "Understanding C-ESMP and its inclusions"
  },
  {
    "chat_id": "baac1a5a-d8c5-43f9-9bf2-8d14ca210538",
    "title": "Understanding C-ESMP Components"
  },
  {
    "chat_id": "6fb48c17-1ce8-4fe7-bee4-adf01151b583",
    "title": "Understanding C-ESMP Components"
  },
  {
    "chat_id": "9e9b7147-cab5-4f69-b5ce-8d4d4498289b",
    "title": "What is a C-ESMP and what does it include?"
  },
  {
    "chat_id": "421c672f-2955-4823-a37d-92cbbce3b588",
    "title": "What is a C-ESMP and what does it include?"
  },
  {
    "chat_id": "99885ea7-845f-4881-8dc4-a56e36b48c0a",
    "title": "What is a C-ESMP and what does it include?"
  },
  {
    "chat_id": "cc2cc519-5060-4684-ac86-6009c6159a27",
    "title": "What is a C-ESMP and what does it include?"
  },
  {
    "chat_id": "55a278d3-3329-4734-b74e-61b62376e535",
    "title": "What is a C-ESMP and what does it include?"
  },
  {
    "chat_id": "12c29b3e-eeb8-4e89-9e47-f03100ceff46",
    "title": "What is a C-ESMP and what does it include?"
  },
  {
    "chat_id": "58c97679-b88e-423a-9489-2551fa0ab8b0",
    "title": "What is a C-ESMP and what does it include?"
  },
  {
    "chat_id": "22e9fd71-84fe-49e0-b3db-c36ebb606a81",
    "title": "What is a C-ESMP and what does it include?"
  }
]
```

#### `DELETE /chats/{chat_id}?chat_type=question/insight`
Delete a chat and its history.

**Response:**
```json
{"detail": "Chat chat-123 deleted."}
```

### Insights Endpoints

#### `GET /insights/`
List all insights (newest first).

**Response:**
```json
[
  {
    "id": "insight_I10",
    "title": "Internal and External Teams Drive Quality Solutions",
    "updatedAt": "2025-09-23T04:43:37.621828",
    "summary": "The project team is leveraging both internal and external expertise to address challenges, with a collaborative approach to problem-solving and quality control.",
    "type": "MEETING",
    "tags": [
      "Roads & Infrastructure for Zone 1A",
      "All Meetings",
      "Event: Multi-Meeting Insights",
      "Collaboration"
    ]
  },
  {
    "id": "insight_I9",
    "title": "Contractor Over-Dependence Poses Project Risk",
    "updatedAt": "2025-09-23T04:43:37.621828",
    "summary": "A significant risk of 'contractor over-dependence' has been identified, as the current contractor holds three other CRDA contracts, necessitating a new monitoring protocol.",
    "type": "MEETING",
    "tags": [
      "Roads & Infrastructure for Zone 1A",
      "10 December 2025",
      "Event: Finance & Risk Review",
      "Risk Management"
    ]
  },
  {
    "id": "insight_I8",
    "title": "Performance-Based Payments Linked to Verification",
    "updatedAt": "2025-09-23T04:43:37.621828",
    "summary": "The projectâ€™s payment process is tied directly to performance and external verification, indicating a strong focus on quality assurance before financial disbursements.",
    "type": "MEETING",
    "tags": [
      "Roads & Infrastructure for Zone 1A",
      "10 December 2025",
      "Event: Finance & Risk Review",
      "Payments"
    ]
  },
  {
    "id": "insight_I7",
    "title": "Dust Suppression Identified as Urgent Concern",
    "updatedAt": "2025-09-23T04:43:37.621828",
    "summary": "Environmental compliance, particularly regarding dust suppression, has been identified as a key area of concern that requires immediate action and a formal audit.",
    "type": "MEETING",
    "tags": [
      "Roads & Infrastructure for Zone 1A",
      "20 July 2025",
      "Event: Technical Review",
      "Environmental Compliance"
    ]
  },
  {
    "id": "insight_I6",
    "title": "Monsoon Delay Requires Formal Recovery Planning",
    "updatedAt": "2025-09-23T04:43:37.621828",
    "summary": "The project is currently facing a 30-day delay due to external factors like monsoon rains, requiring the development of a formal recovery plan to get back on schedule.",
    "type": "MEETING",
    "tags": [
      "Roads & Infrastructure for Zone 1A",
      "20 July 2025",
      "Event: Technical Review",
      "Progress"
    ]
  },
  {
    "id": "insight_I5",
    "title": "Project Kickoff Defines Legal and Financial Framework",
    "updatedAt": "2025-09-23T04:43:37.621828",
    "summary": "Initial project kickoff established a clear framework for the 'Roads & Infrastructure for Zone 1A' project, including timelines, financial structures, and legal clauses.",
    "type": "DOCUMENT",
    "tags": [
      "Roads & Infrastructure for Zone 1A",
      "15 January 2025",
      "Event: Kickoff Meeting",
      "Finance"
    ]
  },
  {
    "id": "insight_I4",
    "title": "Multi-Tiered System for Dispute Resolution",
    "updatedAt": "2025-09-23T04:43:37.621828",
    "summary": "The bidding process has a clear and multi-tiered system for resolving disputes and complaints.",
    "type": "DOCUMENT",
    "tags": [
      "Amaravati Capital City Development Program",
      "31 December 2024",
      "Document: Package - 3 (Neerukonda Reservior)",
      "Dispute Resolution"
    ]
  },
  {
    "id": "insight_I3",
    "title": "Strong Emphasis on Environmental and Social Compliance",
    "updatedAt": "2025-09-23T04:43:37.621828",
    "summary": "There is a strong emphasis on environmental and social compliance, backed by specific requirements and penalties.",
    "type": "DOCUMENT",
    "tags": [
      "Amaravati Capital City Development Program",
      "31 December 2024",
      "Document: Package - 3 (Neerukonda Reservior)",
      "Environmental"
    ]
  },
  {
    "id": "insight_I2",
    "title": "Comprehensive Criteria Focus on Bidder Capability",
    "updatedAt": "2025-09-23T04:43:37.621828",
    "summary": "The qualification criteria for bidders are comprehensive, focusing on financial stability, past performance, and technical capacity.",
    "type": "DOCUMENT",
    "tags": [
      "Amaravati Capital City Development Program",
      "31 December 2024",
      "Document: Package - 3 (Neerukonda Reservior)",
      "Qualification Criteria"
    ]
  },
  {
    "id": "insight_I1",
    "title": "Strict Bidding Process Ensures Bidder Credibility",
    "updatedAt": "2025-09-23T04:43:37.621828",
    "summary": "The bidding process has strict financial and security requirements to ensure the bidder's capability and commitment.",
    "type": "DOCUMENT",
    "tags": [
      "Amaravati Capital City Development Program",
      "31 December 2024",
      "Document: Package - 3 (Neerukonda Reservior)",
      "Financials"
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
"chat_type":"insight",
"chat_id": "insight_id"

}
```

**Response:**
```json
{
  "question": "What additional documents must a bidder submit?",
  "answer": "Based on the prior context provided, in addition to the documents mentioned, bidders must also submit a plan detailing their engagement of specialized agencies for specific work components.",
  "follow_up_questions": [
    "What is a C-ESMP and what does it include?",
    "How is the bid evaluated?",
    "What are the rules regarding the use of bidding forms?"
  ],
  "chat_id": "insight_I10",
  "chat_type": "insight",
  "title": "Leveraging Internal and External Expertise for Challenges"
}
```

## Data Models

### Request Models

#### `QuestionRequest`
```python
class QuestionRequest(BaseModel):
    question: str
    chat_id: Optional[str] = None # Optional: Session ID (auto-generated if not provided)
    chat_type: Literal["question", "insight"] = "question" 
```

#### `InsightResponse`
```python
# Response model for listing insights
class InsightResponse(BaseModel):
    id: str
    title: str
    updatedAt: str
    summary: str
    type: str
    tags: list[str]
   

```

### Response Models

#### `SearchResponse`
```python
class SearchResponse(BaseModel):
    question: str
    answer: str
    follow_up_questions: List[str]
    chat_id: str                  # NEW (returned only when created)
    chat_type: Literal["question", "insight"]
    title: Optional[str] = None   # NEW (returned only when created)
```

#### `HistoryResponse`
```python
class HistoryResponse(BaseModel):
    chat_id: str
    chat_type: Literal["question", "insight"]
    user_id: str
    chat_title: Optional[str] = None          # NEW: title outside the list
    history: List[HistoryItem]


class HistoryItem(BaseModel):
    question: str
    answer: str
    ts: Optional[int] = None  # unix timestamp (user_id removed from each item)
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
      "chat_id": "16054a4b-1e77-4828-b4f3-6f76db839d0e",
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
curl -X GET "http://localhost:8000/chat/chat-123"

# List all sessions
curl -X GET "http://localhost:8000/chats"

# Delete a session
curl -X DELETE "http://localhost:8000/chats/chat-123"

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