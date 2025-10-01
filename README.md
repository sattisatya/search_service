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
  "chat_type": "question",
  "document_ids": [
    "string"
  ]
}
```

**Response:**
```json
{
  "question": "What are the key infrastructure components being addressed in the N1 Trunk Infrastructure Agreement?",
  "answer": "- Construction of roads\n- Storm water drains\n- Water supply network\n- Sewerage network\n- Utility ducts for power & ICT\n- Reuse waterline\n- Pedestrian and cycle tracks\n- Avenue plantation\n- Street furniture",
  "follow_up_questions": [
    "What percentage of land has been acquired for the project, and which district has pending land acquisition?",
    "What specific action items were assigned to the Superintendent Engineer and the Executive Engineer (APTransco) during the meeting?",
    "When is the next review meeting scheduled, and where will it take place?"
  ],
  "chat_id": "bd74192e-70c2-436b-9ad6-13c5548726f8",
  "chat_type": "question",
  "title": "Document Overview",
  "tags": [
    "MoM_N1_Trunk_Infra_11Aug2025_MoM.pdf"
  ]
}
```

#### `GET /chats/{chat_id}?chat_type=question/insight`
Retrieve conversation history for a session.

**Response:**
```json
{
  "chat_id": "insight_36",
  "chat_type": "insight",
  "user_id": "admin",
  "chat_title": "Contractor Mobilization Speed and Timeline Trade-Off Stra...",
  "history": [
    {
      "question": "How quickly did the contractor achieve initial mobilization, and what was the trade-off strategy used to maintain the 24-month project timeline despite land acquisition delays?",
      "answer": "- 90% mobilization (plant, machinery, site office) achieved by April 18, 2025\n- Only 95% of Right-of-Way (ROW) cleared by that time, with a 100m commercial stretch pending eviction\n- Project Director directed contractor to immediately begin work in cleared segments to offset delays\n- Strategy helped maintain the March 2027 completion target\n- 20.5% physical progress achieved by September 2025\n- Approximately 25% of the total project timeline had elapsed by September 2025",
      "ts": "2025-10-01T12:14:55Z",
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
      "question": "What was the total physical progress achieved by the final review meeting on December 15, 2026?",
      "answer": "- The key action item for APADCL was to issue land demarcation instruction for Site A to the State Department",
      "ts": "2025-10-01T12:18:46Z",
      "tags": [
        "Action Item",
        "Site Selection",
        "Land",
        "Amaravati Airport Meetings.pdf"
      ]
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
    "chat_id": "ef2c3244-75c7-40f9-be8c-1853125abdb2",
    "title": "E6 Road Work Package VII Tender Number",
    "last_answer": "The full tender reference number for the E6 Road Work Package VII is not explicitly mentioned in the provided context.",
    "timestamp": "2025-09-30T14:17:42Z"
  },
  {
    "chat_id": "6a2bd6e5-5bc3-4750-953b-00ef53b85c0d",
    "title": "Questions for Document Review",
    "last_answer": "Some of the resolutions made during the review meeting included ensuring updated execution schedules are submitted, timely submission of the Utilization Certificate, obtaining approval for the Substation design, pursuing Environmental Clearance, and holding bi-weekly review meetings for progress monitoring.",
    "timestamp": "2025-09-30T13:23:29Z"
  },
  {
    "chat_id": "cfc54919-598e-4765-bbae-573fbd897cf9",
    "title": "Status of Guntur Irrigation Project",
    "last_answer": "The status of the Guntur Irrigation (IRR) project is that the finalized land requirement for phased development is approximately ~2,000 acres.",
    "timestamp": "2025-09-30T12:28:49Z"
  },
  {
    "chat_id": "810d2ae5-b139-4839-96f4-4100bb948684",
    "title": "Number of Projects",
    "last_answer": "Based on the information provided, it appears that there is one project with an estimated progress of around 15%.",
    "timestamp": "2025-09-30T12:28:04Z"
  },
  {
    "chat_id": "c07b48fb-eb6e-475b-b3b9-172850d28fb1",
    "title": "Material Supply Risk Mitigation",
    "last_answer": "The mitigation for the Material Supply risk was that the Contractor was required to submit the final As-Built Drawings and O&M Manuals (5 sets) by 15 January 2027.",
    "timestamp": "2025-09-30T12:27:43Z"
  },
  {
    "chat_id": "0173b394-391e-43c5-ae80-bcfc4eeda5af",
    "title": "Contractor Mobilization Speed and Project Timeline Strategy",
    "last_answer": "The mitigation for the Material Supply risk was to require the Contractor to submit the final As-Built Drawings and O&M Manuals (5 sets) by 15 January 2027.",
    "timestamp": "2025-09-30T12:22:39Z"
  },
  {
    "chat_id": "690929a8-10f1-4e2d-894a-4e993fdacdee",
    "title": "Contractor Mobilization Speed and Timeline Trade-offs",
    "last_answer": "The contractor achieved **90% mobilization (plant, machinery, site office) by April 18, 2025**. To maintain the 24-month project timeline despite land acquisition delays, they began work in cleared segments immediately, reaching **20.5% physical progress** by September 2025.",
    "timestamp": "2025-09-30T12:16:40Z"
  },
  {
    "chat_id": "d54e7d59-784b-4632-a3ce-219d1c2244eb",
    "title": "E6 Road Work Package VII Tender Number",
    "last_answer": "The full tender reference number for the E6 Road Work Package VII is not explicitly mentioned in the prior context provided. You may need to refer to the official tender documents or contact the relevant procurement or contracting department for this specific information.",
    "timestamp": "2025-09-30T11:52:12Z"
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
    "id": "insight_11",
    "title": "Monsoon Risk and Scheduling Urgency...",
    "updatedAt": "2025-09-30T07:20:25.021100",
    "insight": "Monsoon Risk and Scheduling Urgency",
    "user_question": "How did the aggressive 12-month schedule impact the foundation work and monsoon preparedness actions?",
    "detailed_answer": "The Superintending Engineer (SE) emphasized sticking to the **aggressive 12-month schedule** for foundation work during the pre-monsoon dry period. To mitigate monsoon impact, the SE stressed the urgency of completing all **canal bed work (CC lining)**. Action items mandated the contractor to install storm water drains and bunds around active pits **before the end of July**.",
    "tags": [
      "Risk Management",
      "Monsoon",
      "Foundation",
      "Schedule"
    ]
  },
  {
    "id": "insight_10",
    "title": "Project Timeline and Critical Progress Milestones...",
    "updatedAt": "2025-09-30T07:20:25.021100",
    "insight": "Project Timeline and Critical Progress Milestones",
    "user_question": "What is the total completion period for the project, and what is the latest reported physical progress and key milestones achieved?",
    "detailed_answer": "The project has a completion period of **12 months from the date of agreement**. As of the July 25, 2024 review meeting, the contractor reported **45% physical progress**. Critical milestones achieved include: **Full piling complete**, and **Pier P1 and P2 pile caps cast**. The **LMC CC lining** (canal bed work) was **confirmed met by the September 30 deadline**.",
    "tags": [
      "Progress",
      "Timeline",
      "Milestones",
      "Piling"
    ]
  },
  {
    "id": "insight_9",
    "title": "Contract Valuation and Bid Security Requirements...",
    "updatedAt": "2025-09-30T07:20:25.021100",
    "insight": "Contract Valuation and Bid Security Requirements",
    "user_question": "What are the key financial and commercial parameters for this tender, including the Estimated Contract Value and the Bid Security amount?",
    "detailed_answer": "The **Estimated Contract Value (ECV)** is **₹19,36,33,680 (INR 19.36 Crores)**. The required **Bid Security (EMD)** is **₹1,936,500.00**. The contract uses a **price-based (L1) selection** criterion, the evaluation type is **percentage based** (above/below ECV), and **Reverse Tendering** is applicable. **Joint Venture (JV) participation is permitted**.",
    "tags": [
      "Finance",
      "Tender",
      "ECV",
      "EMD"
    ]
  },
  {
    "id": "insight_8",
    "title": "Bridge Structure and Highway Connectivity...",
    "updatedAt": "2025-09-30T07:20:25.021100",
    "insight": "Bridge Structure and Highway Connectivity",
    "user_question": "What is the detailed scope of the civil work and its specific location within the Polavaram Project?",
    "detailed_answer": "The work is the Construction of an **NH Crossing Bridge** on the **Left Main Canal (LMC)** near **Kathipudi village** in Kakinada District. The structure consists of a **4-lane main bridge** with an **additional 2-lane service bridge on either side**. It intersects **National Highway NH-216** at **Km 1.850**. The scope also includes approach roads, canal excavation, and **Cement Concrete (CC) lining** of the canal.",
    "tags": [
      "Scope",
      "Location",
      "LMC",
      "NH-216"
    ]
  },
  {
    "id": "insight_7",
    "title": "High-Stakes Procurement Integrity and Governance...",
    "updatedAt": "2025-09-30T07:20:25.021100",
    "insight": "High-Stakes Procurement Integrity and Governance",
    "user_question": "What stringent integrity and governance mechanisms are in place for the procurement of the Polavaram and Guntur projects?",
    "detailed_answer": "The State's procurement process is protected by high-stakes governance clauses:\n\n1. **Polavaram Tender Integrity (G.O.Ms.No.174):** The L1 bidder is required to submit original hard copies of all uploaded documents. **Severe Penalties** are explicitly detailed for non-submission or variation of documents, including **suspension from tenders for 3 years** and potential criminal prosecution.\n\n2. **Guntur IRR Reverse Tendering (L1):** The project is subject to the strict adherence of QA standards due to the **reverse tendering process**. This governance model inherently carries a **risk of quality compromise due to tight margins**, which is mitigated by mandated **Independent Third-Party QA/QC audits** and strict material testing.",
    "tags": [
      "Governance",
      "Integrity Clause",
      "Reverse Tendering",
      "Penalties"
    ]
  },
  {
    "id": "insight_6",
    "title": "Schedule Performance and Delay Mitigation...",
    "updatedAt": "2025-09-30T07:20:25.021100",
    "insight": "Schedule Performance and Delay Mitigation",
    "user_question": "How do the active construction projects compare in terms of schedule performance, and what is the long-term accountability timeline?",
    "detailed_answer": "The two foundational construction projects have varying schedule statuses:\n\n1.  **Amaravati E6 Road:** The project is managing a slight gap between time elapsed and progress: **~25% Time Elapsed** versus **20.5% Physical Progress** (as of Sept 2025). The 3-week delay from utility conflicts puts pressure on the March 2027 completion goal.\n\n2.  **Guntur IRR Loop Phase III:** This project has just commenced (NTP Sept 2025) and is only at **5% physical progress**. The primary schedule risk is the delay in quality clearance (cross-slope rectification) and land handover, preventing the start of higher-productivity pavement work.\n\n**Long-Term Accountability:** The **Amaravati E6 Road** project sets a long-term compliance milestone with its **24-month Defect Liability Period (DLP)**, scheduled to commence with the issuance of the Provisional Completion Certificate on **January 1, 2027**.",
    "tags": [
      "Schedule Performance",
      "DLP",
      "Time Elapsed",
      "Physical Progress"
    ]
  },
  {
    "id": "insight_5",
    "title": "Financial Flow and Investment Scale...",
    "updatedAt": "2025-09-30T07:20:25.021100",
    "insight": "Financial Flow and Investment Scale",
    "user_question": "What is the financial scale of the two major road/utility projects, and what is the current status of financial disbursement (Running Account Bills)?",
    "detailed_answer": "The Amaravati E6 Road project is the largest civil works contract documented at **323.57 Crores**, significantly larger than the Guntur IRR Loop Phase III at **~46.56 Crores**.\n\n**Financial Flow Status:** Disbursement is active, with the **Second Running Bill** for the Amaravati E6 Road (representing 25% progress) confirmed processed and paid. The **First Running Account (R/A) Bill** for the newly started Guntur IRR Loop (estimated at ~15% progress) is currently being finalized for payment processing.",
    "tags": [
      "Financial Status",
      "Contract Value",
      "Funding",
      "Running Bill"
    ]
  },
  {
    "id": "insight_4",
    "title": "Foundation Milestones and Land Clearance Status...",
    "updatedAt": "2025-09-30T07:20:25.021100",
    "insight": "Foundation Milestones and Land Clearance Status",
    "user_question": "What foundational milestones have been achieved, and what is the current status of the residual land clearance risk across the construction projects?",
    "detailed_answer": "Key foundational milestones have been hit, but land remains a risk:\n\n1. **Polavaram LMC Bridge:** The critical **CC lining of the LMC was completed** by the Sept 30, 2024 deadline, allowing canal operations to resume without affecting superstructure work.\n\n2. **Guntur IRR Loop Phase III:** Confirmed **90% ROW clearance** but is challenged by a **pending 10% section near Palakaluru**.\n\n3. **Amaravati E6 Road:** **Road Formation (initial earthwork) is 100% complete** for the entire corridor, enabling the next phase, but minor land pockets remain at intersections.",
    "tags": [
      "Milestone Achievement",
      "Land Clearance",
      "ROW Clearance",
      "CC Lining"
    ]
  },
  {
    "id": "insight_3",
    "title": "Operational and Strategic Risk Mitigation in Amara...",
    "updatedAt": "2025-09-30T07:20:25.021100",
    "insight": "Operational and Strategic Risk Mitigation in Amaravati Projects",
    "user_question": "How are the Amaravati E6 Road and Airport projects addressing their distinct challenges related to utility conflicts and future concession structuring?",
    "detailed_answer": "The two Amaravati projects are mitigating risks specific to their phases:\n\n1.  **Amaravati E6 Road (Operational Risk):** This project experienced a **3-week delay** due to **unmapped utilities**, impacting the critical **Utility Ducting (55% complete)**. The mitigation includes GPR surveys and a mandate for immediate completion of ducting.\n\n2.  **Amaravati Greenfield Airport (Strategic Risk):** The 55%-complete consultancy phase requires finalizing documents for its future **PPP/Concession** model. The consultant must prepare the **Risk Allocation Matrix** and conduct a **sensitivity analysis** on terminal costs to solidify the financial model.",
    "tags": [
      "Operational Risk",
      "Strategic Planning",
      "Utility Conflicts",
      "PPP/Concession"
    ]
  },
  {
    "id": "insight_2",
    "title": "Critical Path Dependency on Regulatory & Quality C...",
    "updatedAt": "2025-09-30T07:20:25.021100",
    "insight": "Critical Path Dependency on Regulatory & Quality Compliance",
    "user_question": "Which two construction projects are facing imminent threats to their schedule based on external approvals or internal quality mandates, and what are the mandatory corrective actions?",
    "detailed_answer": "The Polavaram and Guntur projects are both facing critical compliance hurdles:\n\n1.  **Polavaram LMC Bridge:** The project is physically ready (girders certified) but is blocked by the need for regulatory approval for the **night block traffic diversion plan** to launch girders over the active NH-216.\n\n2.  **Guntur IRR Loop Phase III:** Progress is stalled by a **mandatory quality failure**. The IE issued only provisional acceptance of the initial subgrade (5% progress) and demanded **cross-slope rectification**, preventing the commencement of the next layer.",
    "tags": [
      "Critical Path",
      "Regulatory Compliance",
      "Quality Control",
      "Polavaram LMC Bridge"
    ]
  },
  {
    "id": "insight_1",
    "title": "Consolidated Infrastructure Portfolio Status and S...",
    "updatedAt": "2025-09-30T07:20:25.021100",
    "insight": "Consolidated Infrastructure Portfolio Status and Strategic Focus Areas",
    "user_question": "What is the overall status of the four major infrastructure projects, and which require immediate management attention based on current risks?",
    "detailed_answer": "The portfolio is actively managed across **four major projects** spanning three phases: **Advanced Construction** (Polavaram LMC Bridge, 45% complete on foundation), **Foundational Construction** (Guntur IRR Phase III and Amaravati E6 Road, 5%-20.5% complete), and **Strategic Planning** (Amaravati Airport, ~55% complete). The portfolio's immediate attention is split between resolving **critical regulatory bottlenecks** (Polavaram) and ensuring **foundational quality and land clearance** compliance (Guntur IRR). The Amaravati projects focus on mitigating utility delays (E6 Road) and finalizing strategic financial models (Airport).",
    "tags": [
      "Portfolio Summary",
      "Status Overview",
      "Critical Attention",
      "Polavaram"
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
  "document_id": "7e8e1ef877f9535dc6faa9b0015d9d42"
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
    document_ids: Optional[List[str]] = None   # transient only
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
    tags: List[str] = []

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
#### `HistoryResponse`
```python
class HistoryResponse(BaseModel):
    chat_id: str
    chat_type: Literal["question", "insight"]
    user_id: str
    chat_title: Optional[str] = None
    history: List[HistoryItem] = []

class HistoryItem(BaseModel):
    question: str
    answer: str
    ts: Optional[str] = None
    tags: List[str] = []          # NEW
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
    "$oid": "68dbbd27a3c2a2948ed61d82"
  },
  "ID": "Q1",
  "user_question": "What is the full tender reference number for the E6 Road Work Package VII?",
  "detailed_answer": "The **Final Contract Value (FCV) is 46.56 Crore**. This value was achieved through the Reverse Tendering process, resulting in a **3.0% discount** from the Original Estimated Cost Value (ECV) of 48.00 Crore.",
  "follow_up_question_1": "What is the total amount of the Performance Guarantee (PG) required from the contractor?",
  "follow_up_question_2": "What is the contractual implication of the Reverse Tendering (L1) clauses on project quality?",
  "follow_up_question_3": "What type of contract is being used for this project, and what does it entail?",
  "tags": "['Finance', 'Contract', 'Cost', 'Risk', 'Guntur Irr Phase3.pdf']",
  "updatedAt": "2025-09-30T11:21:11.576444",
  "question_embedding": Array(1536)

}
```

#### `insights` Collection
```json
{
  "_id": {
    "$oid": "68db84b9193046d45d8faea0"
  },
  "Insight ID": "insight_1",
  "insight": "Consolidated Infrastructure Portfolio Status and Strategic Focus Areas",
  "detailed_answer": "The portfolio is actively managed across **four major projects** spanning three phases: **Advanced Construction** (Polavaram LMC Bridge, 45% complete on foundation), **Foundational Construction** (Guntur IRR Phase III and Amaravati E6 Road, 5%-20.5% complete), and **Strategic Planning** (Amaravati Airport, ~55% complete). The portfolio's immediate attention is split between resolving **critical regulatory bottlenecks** (Polavaram) and ensuring **foundational quality and land clearance** compliance (Guntur IRR). The Amaravati projects focus on mitigating utility delays (E6 Road) and finalizing strategic financial models (Airport).",
  "tags": "['Portfolio Summary', 'Status Overview', 'Critical Attention', 'Polavaram', 'Guntur IRR', 'Amaravati E6', 'Amaravati Airport']",
  "follow_up_question_1": "What is the exact deadline for the contractor to resolve the cross-slope rectification issue on the Guntur IRR Loop Phase III subgrade?",
  "follow_up_question_2": "Has the necessary night block traffic diversion plan been submitted for the Polavaram LMC Bridge girder launching?",
  "follow_up_question_3": "What is the total combined estimated contract value (ECV) for the Guntur IRR Loop Phase III and Amaravati E6 Road projects?",
  "updatedAt": "2025-09-30T07:20:25.021100",
  "user_question": "What is the overall status of the four major infrastructure projects, and which require immediate management attention based on current risks?"
}
```

### Redis Data Structure

#### Chat History Storage
```
{
  "chat_id": "insight_36",
  "chat_type": "insight",
  "user_id": "admin",
  "chat_title": "Contractor Mobilization Speed and Timeline Trade-Off Stra...",
  "history": [
    {
      "question": "How quickly did the contractor achieve initial mobilization, and what was the trade-off strategy used to maintain the 24-month project timeline despite land acquisition delays?",
      "answer": "- 90% mobilization (plant, machinery, site office) achieved by April 18, 2025\n- Only 95% of Right-of-Way (ROW) cleared by that time, with a 100m commercial stretch pending eviction\n- Project Director directed contractor to immediately begin work in cleared segments to offset delays\n- Strategy helped maintain the March 2027 completion target\n- 20.5% physical progress achieved by September 2025\n- Approximately 25% of the total project timeline had elapsed by September 2025",
      "ts": "2025-10-01T12:14:55Z",
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
      "question": "What was the total physical progress achieved by the final review meeting on December 15, 2026?",
      "answer": "- The key action item for APADCL was to issue land demarcation instruction for Site A to the State Department",
      "ts": "2025-10-01T12:18:46Z",
      "tags": [
        "Action Item",
        "Site Selection",
        "Land",
        "Amaravati Airport Meetings.pdf"
      ]
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