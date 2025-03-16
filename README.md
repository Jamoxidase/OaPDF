# Scholarly Content Retrieval System (SCRS)

A Python-based scholarly content retrieval system that takes JSON RPC-style requests to search for and retrieve academic papers, prioritizing PDF links, structured text, and metadata.

## Overview

The SCRS is designed to make it easy to programmatically access scientific information in Python projects. It provides a standardized interface that searches across multiple scholarly databases (Google Scholar via SerpAPI, PubMed/NCBI, arXiv, and OpenAIRE) and returns consistent response objects with PDF links as the primary goal, followed by structured content or available metadata.

### Key Features

- Search academic publications using natural language queries across multiple sources
  - Google Scholar (via SerpAPI)
  - PubMed/NCBI E-utilities
  - arXiv API
  - OpenAIRE API
- Automatically resolve PDF links using Unpaywall API
- Filter by source, date range, journal, and more
- Prioritize results with available PDF links
- Retrieve detailed document information by ID or DOI
- JSON RPC-style interface for easy integration
- Standardized response format across all sources
- PDF-first result prioritization
- Comprehensive error handling with retry logic
- Rate limiting protection

## Installation

```bash
# Clone the repository
git clone https://github.com/Jamoxidase/SCRS_OaPDF
cd SCRS_OaPDF

# Install dependencies
pip install requests tenacity
```

## Configuration

The system requires API keys for the services it uses. Set them as environment variables:

```bash
# Required for Google Scholar search (via SerpAPI)
export SERP_API_KEY="your_serp_api_key_here"

# Required for PubMed/NCBI E-utilities and Unpaywall
export PUBMED_EMAIL="your_email@example.com"

# Optional for higher rate limits with PubMed/NCBI
export PUBMED_API_KEY="your_pubmed_api_key_here"

# Optional if different from PUBMED_EMAIL
export UNPAYWALL_EMAIL="your_email@example.com"
```

You can obtain these API keys from:
- [SerpApi](https://serpapi.com/) for Google Scholar access
- [NCBI](https://www.ncbi.nlm.nih.gov/account/register/) for PubMed API key (email is required even without API key)
- No API key is required for arXiv and OpenAIRE
- Unpaywall only requires an email

## Usage

### Multi-Source Search with PDF Resolution

```python
import os
import json
from scholarly_retrieval import process_scholarly_request

# Set your API keys
os.environ["SERP_API_KEY"] = "your_serp_api_key_here"
os.environ["PUBMED_EMAIL"] = "your_email@example.com"
os.environ["PUBMED_API_KEY"] = "your_pubmed_api_key_here"  # Optional

# Search across multiple sources
search_request = {
    "method": "search",
    "params": {
        "query": "quantum computing",
        "sources": ["google_scholar", "arxiv", "pubmed", "openaire"],
        "year_from": 2020,
        "limit": 5,
        "pdf_only": True,
        "resolve_pdfs": True  # Use Unpaywall to find PDF links
    },
    "id": 1
}

# Process request
result = process_scholarly_request(search_request)
print(json.dumps(result, indent=2))
```

### Source-Specific Search

```python
# Search only in arXiv
arxiv_request = {
    "method": "search",
    "params": {
        "query": "machine learning",
        "sources": ["arxiv"],
        "limit": 5
    },
    "id": 2
}

arxiv_result = process_scholarly_request(arxiv_request)
print(json.dumps(arxiv_result, indent=2))
```

### Get Document by DOI

```python
# Get document details by DOI with PDF resolution
document_request = {
    "method": "get_document",
    "params": {
        "doi": "10.1038/s41746-019-0191-0",  # Example DOI
        "resolve_pdf": True
    },
    "id": 3
}

document_result = process_scholarly_request(document_request)
print(json.dumps(document_result, indent=2))
```

### Get Document by ID and Source

```python
# Get document details by result ID
document_request = {
    "method": "get_document",
    "params": {
        "result_id": "result_id_from_search",
        "source": "arxiv"  # Helps route to the correct API
    },
    "id": 4
}

document_result = process_scholarly_request(document_request)
print(json.dumps(document_result, indent=2))
```

## API Reference

### JSON RPC Request Format

All requests follow this format:

```json
{
  "method": "search|get_document",
  "params": {
    // Method-specific parameters
  },
  "id": 1 // Optional request ID
}
```

### Search Method

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| query | string | Yes | The search query text |
| sources | array | No | List of acceptable sources (default: ["google_scholar", "arxiv", "pubmed", "openaire"]) |
| year_from | integer | No | Start year for publication filter |
| year_to | integer | No | End year for publication filter |
| journal | string | No | Filter by journal name |
| limit | integer | No | Number of results (default: 10) |
| offset | integer | No | Results offset for pagination (default: 0) |
| pdf_only | boolean | No | Return only results with PDF links (default: false) |
| full_text_only | boolean | No | Return only results with full text (default: false) |
| resolve_pdfs | boolean | No | Attempt to resolve PDF links using Unpaywall (default: true) |

**Example:**

```json
{
  "method": "search",
  "params": {
    "query": "machine learning",
    "sources": ["google_scholar"],
    "year_from": 2020,
    "year_to": 2023,
    "journal": "Nature",
    "limit": 10,
    "offset": 0,
    "pdf_only": true,
    "full_text_only": false
  },
  "id": 1
}
```

### Get Document Method

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| result_id | string | * | The unique identifier for the result (required if no DOI) |
| doi | string | * | DOI of the document (can be used instead of result_id) |
| source | string | No | Source name to help route the request (e.g., "arxiv", "pubmed") |
| resolve_pdf | boolean | No | Attempt to resolve PDF link using Unpaywall (default: true) |

*Either result_id or doi must be provided

**Example with Result ID:**

```json
{
  "method": "get_document",
  "params": {
    "result_id": "abc123defg",
    "source": "google_scholar"
  },
  "id": 2
}
```

**Example with DOI:**

```json
{
  "method": "get_document",
  "params": {
    "doi": "10.1038/s41746-019-0191-0"
  },
  "id": 3
}
```

### Response Format

All responses follow this JSON RPC format:

```json
{
  "jsonrpc": "2.0",
  "result": {
    // Method-specific result
  },
  "id": 1 // Same as request ID
}
```

For errors:

```json
{
  "jsonrpc": "2.0",
  "error": {
    "code": -32000,
    "message": "Error message"
  },
  "id": 1 // Same as request ID
}
```

#### Search Result Format

```json
{
  "query": "string",
  "total_results": integer,
  "results": [
    {
      "title": "string",
      "authors": ["string"],
      "publication_date": "string",
      "journal": "string",
      "snippet": "string",
      "doi": "string",
      "pdf_available": boolean,
      "pdf_url": "string",
      "full_text_available": boolean,
      "full_text": "string",
      "abstract": "string",
      "citation_count": integer,
      "source": "string",
      "source_url": "string",
      "result_id": "string"
    }
  ],
  "pagination": {
    "current_page": integer,
    "total_pages": integer,
    "has_next": boolean,
    "has_previous": boolean
  }
}
```

#### Document Result Format

```json
{
  "title": "string",
  "authors": ["string"],
  "publication_date": "string",
  "journal": "string",
  "abstract": "string",
  "doi": "string",
  "pdf_available": boolean,
  "pdf_url": "string",
  "full_text_available": boolean,
  "full_text": "string",
  "citation_count": integer,
  "references": [
    {
      "title": "string",
      "authors": ["string"],
      "publication_date": "string",
      "journal": "string"
    }
  ],
  "source": "string",
  "source_url": "string"
}
```

## Error Codes

| Code | Description |
|------|-------------|
| -32600 | Invalid Request |
| -32601 | Method not found |
| -32602 | Invalid params |
| -32603 | Internal error (configuration) |
| -32000 | Generic server error |
| -32001 | API error (external services) |
| -32002 | Resource not found |
| -32003 | Rate limit exceeded |

## Current Features

- Multiple scholarly sources:
  - Google Scholar (via SerpAPI)
  - PubMed/NCBI E-utilities
  - arXiv API
  - OpenAIRE API
- PDF resolution via Unpaywall API
- Flexible filtering options
- Result normalization across all sources
- Rate limiting protection with exponential backoff
- LRU caching for API responses
- Comprehensive error handling

## Future Enhancements

- Add more scholarly sources (CORE, Semantic Scholar, etc.)
- Add persistent caching with Redis or similar
- Implement asynchronous processing for parallel API calls
- Implement citation networks 
## License

MIT

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
