#!/usr/bin/env python3
"""
Simple CLI script to search for scholarly papers given a text query.
Returns the top 4 results across multiple sources with PDF links when available.
"""

import os
import sys
import time
from pathlib import Path
from scholarly_retrieval import process_scholarly_request

# Add python-dotenv support to load variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
    print("Loaded environment from .env file")
except ImportError:
    print("python-dotenv not installed. Using system environment variables.")

def check_environment():
    """Check if required environment variables are set"""
    required = {
        "PUBMED_EMAIL": "Your email for PubMed/NCBI API"
    }
    
    optional = {
        "SERP_API_KEY": "Your SerpAPI key for Google Scholar",
        "PUBMED_API_KEY": "Your PubMed API key for higher rate limits",
        "UNPAYWALL_EMAIL": "Your email for Unpaywall (defaults to PUBMED_EMAIL)"
    }
    
    missing = []
    for var, desc in required.items():
        if not os.environ.get(var):
            missing.append(f"{var}: {desc}")
    
    if missing:
        print("ERROR: Required environment variables not set:")
        for m in missing:
            print(f"  - {m}")
        print("\nPlease set these variables in your environment or .env file")
        return False
    
    warnings = []
    for var, desc in optional.items():
        if not os.environ.get(var):
            warnings.append(f"{var}: {desc}")
    
    if warnings:
        print("NOTE: Some optional variables are not set:")
        for w in warnings:
            print(f"  - {w}")
        print("The search will continue, but with limited sources.")
    
    return True

def truncate_text(text, max_length=75):
    """Truncate text to specified length with ellipsis"""
    if text is None:
        return "N/A"
    
    text_str = str(text)
    if len(text_str) > max_length:
        return text_str[:max_length] + "..."
    return text_str

def search_papers(query, limit=4):
    """Search for papers matching the query"""
    start_time = time.time()
    
    # Determine available sources based on environment variables
    sources = []
    if os.environ.get("PUBMED_EMAIL"):
        sources.append("pubmed")
    if True:  # arXiv doesn't require API keys
        sources.append("arxiv")
    if os.environ.get("SERP_API_KEY"):
        sources.append("google_scholar")
    
    if not sources:
        print("ERROR: No sources available. Please check environment variables.")
        return None
    
    print(f"Searching across: {', '.join(sources)}...")
    
    # Prepare the request
    request_data = {
        "method": "search",
        "params": {
            "query": query,
            "sources": sources,
            "limit": limit,
            "resolve_pdfs": True
        },
        "id": 1
    }
    
    # Process the request
    result = process_scholarly_request(request_data)
    
    end_time = time.time()
    elapsed_time = end_time - start_time
    
    return result, elapsed_time

def display_results(result, elapsed_time):
    """Display search results in a friendly format"""
    if "error" in result:
        print(f"ERROR: {result['error']['message']}")
        return
    
    if "result" not in result:
        print("No results found.")
        return
    
    results = result["result"]["results"]
    total = result["result"]["total_results"]
    
    print(f"\nFound {total} results in {elapsed_time:.2f} seconds:")
    
    if not results:
        print("No papers matched your query.")
        return
    
    # Count results by source
    sources = {}
    for item in results:
        source = item.get("source", "unknown")
        sources[source] = sources.get(source, 0) + 1
    
    for source, count in sources.items():
        print(f"  - {source}: {count} results")
    
    print("\n" + "="*80)
    
    # Display each result
    for i, paper in enumerate(results):
        print(f"\n[{i+1}] {paper.get('title')}")
        print(f"    Authors: {truncate_text(', '.join(paper.get('authors', ['N/A'])))}")
        print(f"    Source: {paper.get('source', 'N/A')} | Journal: {truncate_text(paper.get('journal', 'N/A'))}")
        print(f"    Date: {paper.get('publication_date', 'N/A')}")
        
        # Show abstract snippet
        abstract = paper.get('abstract', '')
        if abstract:
            print(f"    Abstract: {truncate_text(abstract, 120)}")
        
        # Show PDF link if available
        if paper.get('pdf_available') and paper.get('pdf_url'):
            print(f"    \033[92mPDF Available: {paper.get('pdf_url')}\033[0m")
        else:
            print(f"    \033[91mNo PDF Available\033[0m")
        
        # Source-specific info
        if paper.get('source') == 'arxiv':
            print(f"    arXiv ID: {paper.get('arxiv_id', 'N/A')}")
        elif paper.get('source') == 'pubmed':
            print(f"    PMID: {paper.get('pmid', 'N/A')}")
        
        print("    " + "-"*76)

def main():
    """Main entry point"""
    # Create template .env file if needed
    env_file = Path(".env")
    if not env_file.exists():
        print("No .env file found. Creating template...")
        with open(env_file, "w") as f:
            f.write("""# Scholarly Search Environment Variables

# Required for PubMed/NCBI E-utilities (also used for Unpaywall if not specified)
PUBMED_EMAIL=your_email@example.com

# Optional: Your SerpAPI key for Google Scholar access
# SERP_API_KEY=your_serp_api_key_here

# Optional: Your PubMed API key for higher rate limits
# PUBMED_API_KEY=your_pubmed_api_key_here

# Optional: Your email for Unpaywall (if different from PUBMED_EMAIL)
# UNPAYWALL_EMAIL=your_email@example.com
""")
        print(f"Created {env_file}. Please edit it with your credentials.")
        
    # Check environment
    if not check_environment():
        sys.exit(1)
    
    # Main search loop
    print("\nScholarly Paper Search")
    print("="*80)
    print("Enter your search query (or 'quit' to exit)")
    
    while True:
        try:
            query = input("\nSearch query: ").strip()
            if not query:
                continue
            
            if query.lower() in ('quit', 'exit', 'q'):
                break
            
            result, elapsed_time = search_papers(query)
            if result:
                display_results(result, elapsed_time)
        
        except KeyboardInterrupt:
            print("\nSearch interrupted.")
            break
        except Exception as e:
            print(f"Error: {str(e)}")
    
    print("\nThank you for using Scholarly Search!")

if __name__ == "__main__":
    main()