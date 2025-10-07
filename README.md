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
  "question": "string",
  "chat_id": "string",
  "chat_type": "question"
}
```

**Response:**
```json
{
  "question": "What is the agenda of the meeting?",
  "answer": "Review of project execution status under Agreement No. /CE/ADC/Engg./2025-26.\nIdentification of pending issues relating to land acquisition, clearances, and departmental coordination.\nFinalization of timelines for completion of immediate tasks.\nAssignment of responsibilities and action items to concerned officers.",
  "follow_up_questions": [
    "What were the resolutions made in the meeting?",
    "Who were the members present at the meeting?",
    "What issues were discussed in detail during the meeting?"
  ],
  "chat_id": "da333fa3-f2e4-4768-9286-66ebf30ff01c",
  "chat_type": "question",
  "title": "Guntur Project Overview",
  "tags": [
    {
      "name": "MoM_N1_Trunk_Infra_11Aug2025_MoM.pdf",
      "file_url": ""
    }
  ]
}
```

#### `GET /chats/{chat_id}?chat_type=question/insight`
Retrieve conversation history for a session.

**Response:**
```json
{
  "chat_id": "f8f944c6-64cd-4cab-9a8f-2f72cb94337d",
  "chat_type": "question",
  "user_id": "admin",
  "chat_title": "Amaravathi Project Overview",
  "history": [
    {
      "question": "amaravathi project details",
      "answer": "1. The Amaravati E6 Road Project (Package VII) is currently in progress.\n2. The project has achieved approximately 20.5% physical completion.\n3. Completed tasks include earthwork and road formation.\n4. Ongoing tasks involve utility ducting, sewerage, and storm drains.\n5. The project has faced minor delays due to unmapped utilities and pending land clearance.\n6. Despite these delays, the project is on track for its planned completion in March 2027.",
      "ts": "2025-10-07T05:23:04Z",
      "tags": [
        {
          "name": "Project Status",
          "file_url": ""
        },
        {
          "name": "Identification",
          "file_url": ""
        },
        {
          "name": "Work Package",
          "file_url": ""
        },
        {
          "name": "Amaravati E6 Project.pdf",
          "file_url": "https:xxxxx"
        }
      ],
      "follow_up_questions": [
        "What is the current reported physical progress percentage as of mid-October 2025, and what construction activity is nearing completion?",
        "What are the core design specifications for the road, including the number of lanes, carriageway width, and design speed?",
        "What are the two most significant 'live' utility conflicts identified, and what is the target date for resolving the electrical pole shifting?"
      ]
    }
  ],
  "document_ids": []
}
```

#### `GET /chats?include_insight=true&include_question=true'`
List all active session IDs.

**Response:**
```json
[
  {
    "chat_id": "c278a833-38f7-4bce-820a-54f0c88519ab",
    "title": "Uploaded Documents Inquiry",
    "last_answer": "The main topic of KAG1.pdf is the introduction of a professional domain knowledge service framework called Knowledge Augmented Generation (KAG), which aims to enhance the performance of large language models (LLMs) in professional domains by integrating knowledge graphs and retrieval-augmented generation methods.",
    "timestamp": "2025-10-07T05:30:16Z"
  },
  {
    "chat_id": "insight_35",
    "title": "E6 Road Underground Utility Quality Measures",
    "last_answer": "1. **Street Furniture Delivery Schedule:** The primary focus of Review Meeting 5 on November 08, 2026, was on planning and coordinating the timely delivery and installation of street furniture. This includes elements such as benches, lighting, and signage, which are essential for enhancing the functionality and aesthetic appeal of the road infrastructure.\n\n2. **Final Drainage Review:** Another critical topic discussed during the meeting was the final drainage review. This involved a comprehensive evaluation of the drainage systems to ensure they effectively manage water runoff and prevent potential flooding or waterlogging issues, thereby maintaining the road's integrity and usability.",
    "timestamp": "2025-10-07T05:28:31Z"
  },
  {
    "chat_id": "da333fa3-f2e4-4768-9286-66ebf30ff01c",
    "title": "Guntur Project Overview",
    "last_answer": "Review of project execution status under Agreement No. /CE/ADC/Engg./2025-26.\nIdentification of pending issues relating to land acquisition, clearances, and departmental coordination.\nFinalization of timelines for completion of immediate tasks.\nAssignment of responsibilities and action items to concerned officers.",
    "timestamp": "2025-10-07T05:27:43Z"
  },
  {
    "chat_id": "f8f944c6-64cd-4cab-9a8f-2f72cb94337d",
    "title": "Amaravathi Project Overview",
    "last_answer": "1. The Amaravati E6 Road Project (Package VII) is currently in progress.\n2. The project has achieved approximately 20.5% physical completion.\n3. Completed tasks include earthwork and road formation.\n4. Ongoing tasks involve utility ducting, sewerage, and storm drains.\n5. The project has faced minor delays due to unmapped utilities and pending land clearance.\n6. Despite these delays, the project is on track for its planned completion in March 2027.",
    "timestamp": "2025-10-07T05:23:05Z"
  },
  {
    "chat_id": "5cdd50c3-ba29-4736-94ef-c2d1f3fed0be",
    "title": "Uploaded Documents Inquiry",
    "last_answer": "KAG achieved significant improvements in professionalism compared to RAG methods in two professional knowledge Q&A tasks of Ant Group, including E-Government Q&A and E-Health Q&A. [DOC KAG1.pdf]",
    "timestamp": "2025-10-06T17:34:49Z"
  },
  {
    "chat_id": "38612c02-7946-419d-ad95-06512fbe0c4e",
    "title": "Uploaded Documents Inquiry",
    "last_answer": "1. You have 1 uploaded document(s).\n2. Document names: KAG1.pdf\n3. The most recent document (by the shown list) is: KAG1.pdf",
    "timestamp": "2025-10-06T17:26:53Z"
  },
  {
    "chat_id": "test1",
    "title": "Uploaded Documents Inquiry",
    "last_answer": "1. The document introduces Knowledge Augmented Generation (KAG), a framework designed to enhance large language models (LLMs) with professional domain knowledge using knowledge graphs (KG) and retrieval-augmented generation (RAG) techniques. [DOC c15a3835b710673e57466ed17e6ad5ae]\n2. KAG addresses limitations of RAG, such as insensitivity to numerical values and temporal relations, by integrating semantic reasoning and logical forms into the retrieval and generation processes. [DOC c15a3835b710673e57466ed17e6ad5ae]\n3. The framework consists of three main components: KAG-Builder for building offline indexes, KAG-Solver for hybrid reasoning, and KAG-Model for optimizing language model capabilities. [DOC c15a3835b710673e57466ed17e6ad5ae]\n4. KAG has been applied in professional Q&A tasks at Ant Group, showing significant improvements in accuracy and professionalism over traditional RAG methods. [DOC c15a3835b710673e57466ed17e6ad5ae]",
    "timestamp": "2025-10-06T17:20:25Z"
  },
  {
    "chat_id": "test",
    "title": "Uploaded Documents Inquiry",
    "last_answer": "1. You have 1 uploaded document(s).\n2. Document names: sample.txt",
    "timestamp": "2025-10-06T17:04:55Z"
  },
  {
    "chat_id": "725d3ac7-4479-4301-902a-aa25129a4c84",
    "title": "Uploaded Documents Inquiry",
    "last_answer": "1. You uploaded the **Registration Certificate**, which is a mandatory document.",
    "timestamp": "2025-10-06T17:02:19Z"
  },
  {
    "chat_id": "2f8b755d-6030-4f27-a07c-42d84c91d9b8",
    "title": "Uploaded Documents Inquiry",
    "last_answer": "1. You uploaded the **Registration Certificate**, which is a mandatory document.",
    "timestamp": "2025-10-06T17:01:27Z"
  },
  {
    "chat_id": "b847fb71-d1e7-45f0-902e-82e3f9b7a821",
    "title": "Uploaded Documents Inquiry",
    "last_answer": "1. You have 1 uploaded document(s).\n2. Document names: sample.txt",
    "timestamp": "2025-10-06T17:00:21Z"
  },
  {
    "chat_id": "insight_34",
    "title": "E6 Road Infrastructure Progress Review September 2025",
    "last_answer": "1. **Road Formation:** The initial earthwork and road formation for the entire E6 Road corridor are fully completed, standing at 100% completion.\n\n2. **Utility Ducting (Power & ICT):** Progress on utility ducting, involving trench excavation and duct laying for power and ICT utilities, is at 55% completion.\n\n3. **Sewerage Network:** The installation of the trunk sewer line in the northern sector of the project is 40% complete.\n\n4. **Storm Water Drains:** The construction of storm water infrastructure, including collection chambers and drain lines, has reached 25% completion.\n\n5. **Water Networks:** The installation of water supply and reuse lines is currently paused in sections where subgrade construction work is actively ongoing.",
    "timestamp": "2025-10-04T18:43:50Z"
  },
  {
    "chat_id": "insight_31",
    "title": "Amaravati E6 Road Project Timeline Inquiry",
    "last_answer": "1. The Amaravati E6 Road Smart Trunk Infrastructure project is planned to have a total duration of 24 months.\n2. The anticipated completion date for the project is March 2027.\n3. As of September 27, 2025, the project had achieved a physical progress of 20.5%.\n4. By September 27, 2025, approximately 25% of the total project time had elapsed.\n5. A final review meeting was conducted on December 15, 2026.\n6. During this final review, Substantial Completion was confirmed at 98%.\n7. The final review validated the team's adherence to the project timeline.",
    "timestamp": "2025-10-04T18:41:36Z"
  },
  {
    "chat_id": "1f5016ba-7f67-43ae-b539-05666a842237",
    "title": "Uploaded Documents Inquiry",
    "last_answer": "I cannot answer based on the provided documents.",
    "timestamp": "2025-10-04T16:36:31Z"
  }
]
```

#### `DELETE /chats/{chat_id}?chat_type=question/insight/documentqna`
Delete a chat and its history.

**Response:**
```json
{
  "detail": "Deleted",
  "chat_id": "99885ea7-845f-4881-8dc4-a56e36b48c0a",
  "segments_deleted": 1
}
```

#### `DELETE /chats`
Delete a chat and its history.

**Response:**
```json
{
  "detail": "All sessions deleted",
  "result": {
    "deleted_lists": 2,
    "deleted_meta": 2,
    "removed_order_zset": true
  }
}
```

### Insights Endpoints

#### `GET /insights/`
List all insights (newest first).

**Response:**
```json
[
  {
    "id": "insight_36",
    "title": "Timeline Adherence and Mobilization Status",
    "updatedAt": "2025-09-30T07:20:25.021100",
    "insight": "Timeline Adherence and Mobilization Status",
    "user_question": "How fast was contractor mobilization, and what trade-offs were made?",
    "summary": "The project achieved 90% mobilization by April 18, 2025, but 5% of the Right-of-Way remains uncleared. To maintain the March 2027 completion date, work commenced in cleared areas, resulting in 20.5% physical progress by September 2025 with ~25% of the time elapsed.",
    "tags": [
      "Mobilization",
      "Timeline",
      "Project Management",
      "Land Clearance",
      "Physical Progress",
      "Amaravati Meetings Log.pdf",
      "Amaravati E6 Project.pdf"
    ]
  },
  {
    "id": "insight_35",
    "title": "Quality Control and Technical Validation Strategy",
    "updatedAt": "2025-09-30T07:20:25.021100",
    "insight": "Quality Control and Technical Validation Strategy",
    "user_question": "What quality control measures were used for E6 Road utilities?",
    "summary": "The project emphasizes stringent quality control with mandatory third-party inspections and hydraulic pressure testing before backfilling. A pre-commissioning survey in December 2026 will assess road profiles and drainage slopes for design compliance.",
    "tags": [
      "Quality Control",
      "Testing",
      "Compliance",
      "Sewerage",
      "Inspection",
      "Amaravati E6 Project.pdf",
      "Amaravati Meetings Log.pdf"
    ]
  },
  {
    "id": "insight_34",
    "title": "Physical Progress Breakdown of Core Utility Networks (Sept 2025)",
    "updatedAt": "2025-09-30T07:20:25.021100",
    "insight": "Physical Progress Breakdown of Core Utility Networks (Sept 2025)",
    "user_question": "What's the September 2025 progress on E6 Road infrastructure?",
    "summary": "As of September 27, 2025, the project is focused on below-ground utility work: road formation is 100% complete, utility ducting is 55% done, sewerage network is 40% complete, storm water drains are at 25%, and water network installation is paused in active subgrade areas.",
    "tags": [
      "Physical Progress",
      "Utility Networks",
      "Sewerage",
      "Road Formation",
      "ICT Ducting",
      "Amaravati E6 Project.pdf"
    ]
  },
  {
    "id": "insight_33",
    "title": "Financial Overview and International Funding",
    "updatedAt": "2025-09-30T07:20:25.021100",
    "insight": "Financial Overview and International Funding",
    "user_question": "What is the E6 Road project's contract value and financiers?",
    "summary": "The Engineering Contract Value for the Balance Smart Trunk Infrastructure on E6 Road (Package VII) is **323.57 Crores**, funded by the **World Bank** and **Asian Development Bank** as part of the Amaravati infrastructure development programs.",
    "tags": [
      "Financials",
      "Contract Value (ECV)",
      "Funding Source",
      "World Bank",
      "ADB",
      "Amaravati E6 Project.pdf"
    ]
  },
  {
    "id": "insight_32",
    "title": "Mitigation Strategy for Critical E6 Road Project Risks",
    "updatedAt": "2025-09-30T07:20:25.021100",
    "insight": "Mitigation Strategy for Critical E6 Road Project Risks",
    "user_question": "What are the top three risks and their mitigations for E6?",
    "summary": "The project faces three key risks: a **3-week delay** from unmapped utilities, pending land clearance expected by **November 2025**, and material supply issues mitigated by maintaining buffer stock and engaging multiple vendors.",
    "tags": [
      "Risk Management",
      "Utility Conflicts",
      "Land Acquisition",
      "Material Supply",
      "GPR",
      "Amaravati E6 Project.pdf"
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
  "question": "How quickly did the contractor achieve initial mobilization, and what was the trade-off strategy used to maintain the 24-month project timeline despite land acquisition delays?",
  "answer": "- 90% mobilization (plant, machinery, site office) achieved by April 18, 2025\n- Only 95% of Right-of-Way (ROW) cleared by that time, with a 100m commercial stretch pending eviction\n- Project Director directed contractor to immediately begin work in cleared segments to offset delays\n- Strategy helped maintain the March 2027 completion target\n- 20.5% physical progress achieved by September 2025\n- Approximately 25% of the total project timeline had elapsed by September 2025",
  "follow_up_questions": [
    "Which specific government entity was tasked with securing the final land clearance?",
    "What was the total physical progress achieved by the final review meeting on December 15, 2026?",
    "What were the final items on the project's punch list?"
  ],
  "chat_id": "insight_36",
  "chat_type": "insight",
  "title": "Contractor Mobilization Speed and Timeline Trade-Off Stra...",
  "tags": [
    "Mobilization",
    "Timeline",
    "Project Management",
    "Land Clearance",
    "Physical Progress",
    "Amaravati Meetings Log.pdf",
    "Amaravati E6 Project.pdf"
  ]
}
```

### Upload Endpoints
#### ``POST /upload``
**Request**
```
multipart/form-data
```

**Response**
```json
{
  "document_id": "7e8e1ef877f9535dc6faa9b0015d9d42",
  "chat_id":"da333fa3-f2e4-4768-9286-66ebf30ff01c",
  "message":"Document added. 1/2 used."

}
```



## Data Models

### Request Models

#### `QuestionRequest`
```python
class QuestionRequest(BaseModel):
    question: str
    chat_id: Optional[str] = None
    chat_type: Literal["question", "insight"] = "question"
```

### Response Models

#### `SearchResponse`
```python
class SearchResponse(BaseModel):
    question: str
    answer: str
    follow_up_questions: List[str] = []
    chat_id: str
    chat_type: Literal["question", "insight"]
    title: Optional[str] = None
    tags: List[{"name":str, "fileurl":str}] = []

```

#### `InsightResponse`
```python
# Response model for listing insights
class InsightResponse(BaseModel):
    id: str
    title: str
    updatedAt: str
    insight: str
    user_question: str
    summary: str
    tags: list[str]

```
#### `HistoryResponse`
```python
class HistoryItem(BaseModel):
    question: str
    answer: str
    ts: Optional[str] = None
    tags: List[dict] = Field(default_factory=list)  # accept list of dicts
    follow_up_questions: List[str] = Field(default_factory=list)

class HistoryResponse(BaseModel):
    chat_id: str
    chat_type: str
    user_id: str
    chat_title: Optional[str]
    history: List[HistoryItem]
    document_ids: List[str] = Field(default_factory=list)
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
{
  "_id": {
    "$oid": "68df721510c330e5b1f1e432"
  },
  "ID": "Q133",
  "user_question": "As of the last status report (September 27, 2025), what were the key metrics for time elapsed and physical progress?",
  "detailed_answer": "As of September 27, 2025, the overall project status shows that approximately **25% of the time has elapsed**, against which the project has achieved a **Physical Progress of 20.5%**.",
  "follow_up_question_1": "What percentage of progress was reported at the meeting?",
  "follow_up_question_2": "What milestones are achieved and current land clearance status?",
  "follow_up_question_3": "What action is needed for Abutment A2 by July 31?",
  "tags": [
    {
      "names": [
        "Project Status",
        "Physical Progress",
        "Timeline",
        "Amaravati E6 Project.pdf"
      ]
    },
    {
      "file_url": "https://xxxxx"
    }
  ],
  "updatedAt": "2025-10-03T06:49:57.711264",
  "user_question_short": "What were the key metrics as of September 27, 2025?",
  "question_embedding": Array(1536)
}
```

#### `insights` Collection
```json
{
  "_id": {
    "$oid": "68db84b9193046d45d8faebc"
  },
  "Insight ID": "insight_29",
  "insight": "Drainage and Utility Ducting Acceleration",
  "detailed_answer": "The CRDA instructed **parallel deployment** (earthwork at Palakaluru end and drainage works in the middle stretch) following site clearance. The Contractor confirmed mobilization for culvert foundation, and is ahead of schedule on **Utility Duct laying**.",
  "tags": "['Design', 'Coordination', 'Progress', 'Drainage', 'Utility', 'Guntur Irr Meetings.pdf', 'Guntur Irr Phase3.pdf']",
  "follow_up_question_1": "How many total box culverts and major pipe culverts are planned for the project?",
  "follow_up_question_2": "What specific HDPE duct sizes are required for Power and ICT utility ducting?",
  "follow_up_question_3": "When were the design drawings for Cross-Drainage Structures 1 & 2 due from the Contractor?",
  "updatedAt": "2025-09-30T07:20:25.021100",
  "user_question": "Following full site clearance, how is the CRDA accelerating the construction of cross-drainage structures and utility works?",
  "user_question_short": "How is CRDA speeding up drainage and utility construction?",
  "summary": "CRDA has initiated parallel deployment with earthwork at Palakaluru and drainage works underway; the Contractor is ahead of schedule on utility duct laying and has mobilized for culvert foundation."
}
```

### Redis Data Structure

#### Chat History Storage
```
{
  "chat_id": "f8f944c6-64cd-4cab-9a8f-2f72cb94337d",
  "chat_type": "question",
  "user_id": "admin",
  "chat_title": "Amaravathi Project Overview",
  "history": [
    {
      "question": "amaravathi project details",
      "answer": "1. The Amaravati E6 Road Project (Package VII) is currently in progress.\n2. The project has achieved approximately 20.5% physical completion.\n3. Completed tasks include earthwork and road formation.\n4. Ongoing tasks involve utility ducting, sewerage, and storm drains.\n5. The project has faced minor delays due to unmapped utilities and pending land clearance.\n6. Despite these delays, the project is on track for its planned completion in March 2027.",
      "ts": "2025-10-07T05:23:04Z",
      "tags": [
        {
          "name": "Project Status",
          "file_url": ""
        },
        {
          "name": "Identification",
          "file_url": ""
        },
        {
          "name": "Work Package",
          "file_url": ""
        },
        {
          "name": "Amaravati E6 Project.pdf",
          "file_url": "https://s3-practice-ss.s3.ap-south-1.amazonaws.com/data/Amaravati+E6+Road+Project.pdf"
        }
      ],
      "follow_up_questions": [
        "What is the current reported physical progress percentage as of mid-October 2025, and what construction activity is nearing completion?",
        "What are the core design specifications for the road, including the number of lanes, carriageway width, and design speed?",
        "What are the two most significant 'live' utility conflicts identified, and what is the target date for resolving the electrical pole shifting?"
      ]
    }
  ],
  "document_ids": []
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
   uvicorn  src.app.main:app --host 0.0.0.0 --port 8000 --reload
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
uvicorn src.app.main:app --host 0.0.0.0 --port 8000 --log-level debug
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