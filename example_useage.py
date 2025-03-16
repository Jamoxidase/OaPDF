"""
Scholarly Content Retrieval System - Usage Examples with Field Documentation

This example file demonstrates how to use the Scholarly Content Retrieval System
with proper environment variable configuration and includes comprehensive documentation
for all fields in the result objects.
"""

import os
import json
import sys
from pathlib import Path
from scholarly_retrieval import process_scholarly_request

# Add python-dotenv support to load variables from .env file
try:
    from dotenv import load_dotenv
except ImportError:
    print("python-dotenv package not found. Install it with: pip install python-dotenv")
    print("Continuing without .env file support...\n")
    load_dotenv = lambda: None  # Create dummy function

# Load environment variables from .env file
load_dotenv()

# Define a function to create a template .env file if one doesn't exist
def create_env_template(file_path=".env"):
    """Create a template .env file if it doesn't exist"""
    if os.path.exists(file_path):
        return
    
    template = """# Scholarly Content Retrieval System - Environment Variables
# Uncomment and fill in the values below

# Required for Google Scholar searches via SerpAPI
# SERP_API_KEY=your_serp_api_key_here

# Required for PubMed/NCBI E-utilities and can be used for Unpaywall
# PUBMED_EMAIL=your_email@example.com

# Optional: Provides higher rate limits with PubMed/NCBI
# PUBMED_API_KEY=your_pubmed_api_key_here

# Optional: If not set, will use PUBMED_EMAIL for Unpaywall
# UNPAYWALL_EMAIL=your_email@example.com
"""
    
    with open(file_path, "w") as f:
        f.write(template)
    
    print(f"Created template .env file at {file_path}")
    print("Please edit this file with your API keys and email addresses\n")

def check_environment_variables():
    """
    Check required environment variables and provide guidance if missing
    
    Returns:
        bool: True if all critical variables are set, False otherwise
    """
    required_vars = {
        'SERP_API_KEY': 'Required for Google Scholar searches via SerpAPI',
        'PUBMED_EMAIL': 'Required for PubMed/NCBI E-utilities and can be used for Unpaywall'
    }
    
    optional_vars = {
        'PUBMED_API_KEY': 'Optional: Provides higher rate limits with PubMed/NCBI',
        'UNPAYWALL_EMAIL': 'Optional: If not set, will use PUBMED_EMAIL for Unpaywall'
    }
    
    missing_required = []
    missing_optional = []
    
    for var, description in required_vars.items():
        if not os.environ.get(var):
            missing_required.append(f"{var}: {description}")
    
    for var, description in optional_vars.items():
        if not os.environ.get(var):
            missing_optional.append(f"{var}: {description}")
    
    if missing_required:
        print("ERROR: Missing required environment variables:")
        for var in missing_required:
            print(f"  - {var}")
        print("\nPlease set these environment variables before running this script.")
        return False
    
    if missing_optional:
        print("NOTE: Missing optional environment variables:")
        for var in missing_optional:
            print(f"  - {var}")
        print()
    
    # If UNPAYWALL_EMAIL is not set, check if we can use PUBMED_EMAIL
    if not os.environ.get('UNPAYWALL_EMAIL') and os.environ.get('PUBMED_EMAIL'):
        print(f"Using PUBMED_EMAIL ({os.environ.get('PUBMED_EMAIL')}) for Unpaywall API")
    
    return True

def print_field_documentation():
    """Print comprehensive documentation for all fields in the result objects"""
    print("\n" + "="*80)
    print("RESULT FIELDS DOCUMENTATION")
    print("="*80)
    
    print("\nSearch Results Object Fields:")
    search_fields = [
        ("query", "string", "The original search query"),
        ("total_results", "integer", "Total number of results found"),
        ("results", "array", "Array of individual result objects (see below)"),
        ("pagination", "object", "Pagination information with current_page, total_pages, has_next, has_previous")
    ]
    
    for field, type_, desc in search_fields:
        print(f"  {field:<15} {type_:<10} {desc}")
    
    print("\nIndividual Result Object Fields:")
    result_fields = [
        # Common fields across all sources
        ("title", "string", "Title of the paper"),
        ("authors", "array", "List of author names"),
        ("publication_date", "string", "Publication date (format varies by source)"),
        ("journal", "string", "Journal or publication venue name"),
        ("snippet", "string", "Short preview/snippet of the abstract"),
        ("abstract", "string", "Full abstract of the paper when available"),
        ("doi", "string", "Digital Object Identifier (DOI) when available"),
        ("pdf_available", "boolean", "Whether a PDF link is available"),
        ("pdf_url", "string", "URL to the PDF file if available"),
        ("full_text_available", "boolean", "Whether full text content is available"),
        ("full_text", "string", "Full text content if available"),
        ("citation_count", "integer", "Number of citations (primarily from Google Scholar)"),
        ("source", "string", "Source database: google_scholar, pubmed, arxiv, or openaire"),
        ("source_url", "string", "URL to the source page for the paper"),
        ("result_id", "string", "Unique identifier for the result (format varies by source)"),
        
        # Unpaywall specific fields
        ("unpaywall", "object", "Unpaywall metadata with oa_status and source (only when resolved via Unpaywall)"),
        
        # Source-specific fields
        ("arxiv_id", "string", "arXiv identifier (only for arXiv results)"),
        ("categories", "array", "Subject categories (only for arXiv results)"),
        ("pmid", "string", "PubMed ID (only for PubMed results)")
    ]
    
    for field, type_, desc in result_fields:
        print(f"  {field:<20} {type_:<10} {desc}")
    
    print("\nOA Status Values (from Unpaywall):")
    oa_statuses = [
        ("gold", "Published in a fully OA journal"),
        ("green", "Free copy in a repository"),
        ("bronze", "Free on publisher page but without a clear license"),
        ("hybrid", "Free under an open license in a paid-access journal"),
        ("closed", "No free, legal copy available")
    ]
    
    for status, desc in oa_statuses:
        print(f"  {status:<10} {desc}")
    
    print("\n" + "="*80 + "\n")

def truncate_text(text, max_length=200):
    """Helper function to safely truncate text to specified length"""
    if text is None:
        return "N/A"
    
    text_str = str(text)  # Convert to string in case it's a different type
    if len(text_str) > max_length:
        return text_str[:max_length] + "..."
    return text_str

def example_search_multi_source():
    """Example: Search across multiple sources with PDF resolution"""
    import time
    
    request_data = {
        "method": "search",
        "params": {
            "query": "quantum computing",
            "sources": ["google_scholar", "arxiv", "pubmed", "openaire"],
            "year_from": 2022,  # Only papers from 2022 onwards
            "limit": 5,
            "pdf_only": True,
            "resolve_pdfs": True  # Use Unpaywall to find PDF links
        },
        "id": 1
    }
    
    print("Running search across multiple sources for recent quantum computing papers...")
    start_time = time.time()
    result = process_scholarly_request(request_data)
    end_time = time.time()
    elapsed_time = end_time - start_time
    
    print(f"Query completed in {elapsed_time:.2f} seconds")
    
    # Print all results with reasonable truncation for long fields
    if "result" in result:
        sources_found = {}
        pdf_count = 0
        
        for item in result["result"]["results"]:
            source = item.get("source", "unknown")
            sources_found[source] = sources_found.get(source, 0) + 1
            if item.get("pdf_available"):
                pdf_count += 1
        
        print(f"\nFound {result['result']['total_results']} results:")
        for source, count in sources_found.items():
            print(f"  - {source}: {count} results")
        print(f"  - {pdf_count} results with PDF links available")
        
        # Print all results
        print("\nAll results:")
        for i, item in enumerate(result["result"]["results"]):
            print(f"\n--- Result {i+1} ---")
            print(f"Title: {truncate_text(item.get('title'))}")
            
            # Authors list may be long
            authors = ', '.join(item.get('authors', ['N/A']))
            print(f"Authors: {truncate_text(authors)}")
            
            print(f"Source: {item.get('source', 'N/A')}")
            print(f"Journal: {truncate_text(item.get('journal'))}")
            print(f"Publication Date: {item.get('publication_date', 'N/A')}")
            print(f"DOI: {item.get('doi', 'N/A')}")
            print(f"PDF Available: {item.get('pdf_available', False)}")
            if item.get('pdf_url'):
                print(f"PDF URL: {item.get('pdf_url')}")
            if item.get('unpaywall'):
                print(f"OA Status: {item.get('unpaywall', {}).get('oa_status', 'N/A')}")
                print(f"OA Source: {item.get('unpaywall', {}).get('source', 'N/A')}")
            
            # Print abstract
            abstract = item.get('abstract', '')
            print(f"Abstract: {truncate_text(abstract)}")
            
            # Print source-specific fields
            if item.get('source') == 'arxiv':
                print(f"arXiv ID: {item.get('arxiv_id', 'N/A')}")
                if item.get('categories'):
                    cats = ', '.join(item.get('categories', []))
                    print(f"Categories: {truncate_text(cats)}")
            elif item.get('source') == 'pubmed':
                print(f"PMID: {item.get('pmid', 'N/A')}")
    else:
        print("Error in search:", result.get("error", {}).get("message", "Unknown error"))
    
    print("\n" + "-"*80 + "\n")
    return result

def example_search_arxiv_only():
    """Example: Search specifically in arXiv for machine learning papers"""
    import time
    
    request_data = {
        "method": "search",
        "params": {
            "query": "machine learning",
            "sources": ["arxiv"],
            "limit": 5
        },
        "id": 2
    }
    
    print("Running search for machine learning papers in arXiv only...")
    start_time = time.time()
    result = process_scholarly_request(request_data)
    end_time = time.time()
    elapsed_time = end_time - start_time
    
    print(f"Query completed in {elapsed_time:.2f} seconds")
    
    if "result" in result and result["result"]["results"]:
        print(f"\nFound {result['result']['total_results']} results")
        
        # Print category information for arXiv results
        categories = set()
        for item in result["result"]["results"]:
            if "categories" in item:
                categories.update(item["categories"])
        
        if categories:
            print("arXiv categories found:")
            for category in sorted(categories):
                print(f"  - {category}")
        
        # Print all results
        print("\nAll results:")
        for i, item in enumerate(result["result"]["results"]):
            print(f"\n--- Result {i+1} ---")
            print(f"Title: {truncate_text(item.get('title'))}")
            print(f"Authors: {truncate_text(', '.join(item.get('authors', ['N/A'])))}")
            print(f"arXiv ID: {item.get('arxiv_id', 'N/A')}")
            
            if item.get('categories'):
                cats = ', '.join(item.get('categories', []))
                print(f"Categories: {truncate_text(cats)}")
                
            print(f"Publication Date: {item.get('publication_date', 'N/A')}")
            print(f"DOI: {item.get('doi', 'N/A')}")
            print(f"PDF Available: {item.get('pdf_available', False)}")
            if item.get('pdf_url'):
                print(f"PDF URL: {item.get('pdf_url')}")
            
            # Print abstract
            abstract = item.get('abstract', '')
            print(f"Abstract: {truncate_text(abstract)}")
    else:
        print("Error or no results:", result.get("error", {}).get("message", "No results found"))
    
    print("\n" + "-"*80 + "\n")
    return result

def example_get_document_by_doi():
    """Example: Get document details by DOI with PDF resolution"""
    import time
    
    # Example DOI for a known open access paper - one that's definitely in arXiv
    # This is a more reliable DOI than the previous example
    doi = "10.1038/s41467-020-15393-8"  # Nature Communications paper available on arXiv
    
    request_data = {
        "method": "get_document",
        "params": {
            "doi": doi,
            "resolve_pdf": True
        },
        "id": 4
    }
    
    print(f"Retrieving document details for DOI {doi} with PDF resolution...")
    start_time = time.time()
    result = process_scholarly_request(request_data)
    end_time = time.time()
    elapsed_time = end_time - start_time
    
    print(f"Query completed in {elapsed_time:.2f} seconds")
    
    if "result" in result:
        doc = result["result"]
        print(f"\nDocument details:")
        print(f"Title: {truncate_text(doc.get('title'))}")
        print(f"Authors: {truncate_text(', '.join(doc.get('authors', ['N/A'])))}")
        print(f"Source: {doc.get('source', 'N/A')}")
        print(f"Journal: {truncate_text(doc.get('journal'))}")
        print(f"Publication Date: {doc.get('publication_date', 'N/A')}")
        print(f"DOI: {doc.get('doi', 'N/A')}")
        print(f"PDF Available: {doc.get('pdf_available', False)}")
        if doc.get('pdf_url'):
            print(f"PDF URL: {doc.get('pdf_url')}")
        if "unpaywall" in doc:
            print(f"OA Status: {doc.get('unpaywall', {}).get('oa_status', 'N/A')}")
            print(f"OA Source: {doc.get('unpaywall', {}).get('source', 'N/A')}")
        
        # Print source-specific fields
        if doc.get('source') == 'arxiv':
            print(f"arXiv ID: {doc.get('arxiv_id', 'N/A')}")
            if doc.get('categories'):
                cats = ', '.join(doc.get('categories', []))
                print(f"Categories: {truncate_text(cats)}")
        elif doc.get('source') == 'pubmed':
            print(f"PMID: {doc.get('pmid', 'N/A')}")
        
        # Print abstract
        if doc.get('abstract'):
            print(f"\nAbstract: {truncate_text(doc.get('abstract'))}")
    else:
        print("Error retrieving document:", result.get("error", {}).get("message", "Unknown error"))
    
    print("\n" + "-"*80 + "\n")
    return result

if __name__ == "__main__":
    # Create .env template file if it doesn't exist
    create_env_template()
    
    # Display field documentation
    print_field_documentation()
    
    # Check environment variables before running examples
    if not check_environment_variables():
        print("\nERROR: Missing required environment variables.")
        print("Please update the .env file with your API keys and email addresses.")
        print("If you've already updated the .env file, make sure you've installed dotenv:")
        print("  pip install python-dotenv\n")
        sys.exit(1)
    
    print("Running Enhanced Scholarly Content Retrieval System Examples\n")
    
    # Run examples
    try:
        example_search_multi_source()
        example_search_arxiv_only()
        example_get_document_by_doi()
    except Exception as e:
        print(f"Error in examples: {str(e)}")