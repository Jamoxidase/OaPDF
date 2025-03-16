import requests
import json
import re
import os
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Dict, List, Optional, Union, Any
from functools import lru_cache
from tenacity import retry, wait_exponential, stop_after_attempt

class ScholarlyRetrievalError(Exception):
    """Base exception for all scholarly retrieval errors"""
    pass

class ConfigurationError(ScholarlyRetrievalError):
    """Raised when there's an issue with configuration"""
    pass

class APIError(ScholarlyRetrievalError):
    """Raised when there's an error with an external API"""
    pass

class ValidationError(ScholarlyRetrievalError):
    """Raised when input validation fails"""
    pass

class RateLimitError(ScholarlyRetrievalError):
    """Raised when rate limits are exceeded"""
    pass

class ResourceNotFoundError(ScholarlyRetrievalError):
    """Raised when a requested resource is not found"""
    pass

class SerpAPIClient:
    """Client for interacting with SerpAPI's Google Scholar endpoint"""
    
    def __init__(self, api_key: str, base_url: str = "https://serpapi.com/search"):
        """
        Initialize the SerpAPI client
        
        Args:
            api_key: SerpAPI authentication key
            base_url: Base URL for SerpAPI
        """
        if not api_key:
            raise ConfigurationError("SerpAPI API key is required")
            
        self.api_key = api_key
        self.base_url = base_url
        
    def search_scholar(self, 
                      query: str, 
                      limit: int = 10, 
                      offset: int = 0, 
                      year_from: Optional[int] = None, 
                      year_to: Optional[int] = None,
                      journal: Optional[str] = None) -> Dict:
        """
        Perform a Google Scholar search via SerpAPI
        
        Args:
            query: Search query string
            limit: Number of results to return
            offset: Offset for pagination
            year_from: Start year for publication filter
            year_to: End year for publication filter
            journal: Filter by journal name (applied post-query)
            
        Returns:
            Normalized search results in the SCRS format
        """
        params = {
            "engine": "google_scholar",
            "q": query,
            "api_key": self.api_key,
            "num": limit,
            "start": offset
        }
        
        if year_from:
            params["as_ylo"] = year_from
        
        if year_to:
            params["as_yhi"] = year_to
        
        try:
            response = requests.get(self.base_url, params=params, timeout=30)
            response.raise_for_status()
            results = self._normalize_search_results(response.json())
            
            # Apply journal filter if specified (post-query filtering)
            if journal:
                results['results'] = [
                    r for r in results['results'] 
                    if journal.lower() in r.get('journal', '').lower()
                ]
                results['total_results'] = len(results['results'])
                
            return results
            
        except requests.RequestException as e:
            raise APIError(f"SerpAPI request failed: {str(e)}")
        except (KeyError, ValueError, TypeError) as e:
            raise APIError(f"Failed to process SerpAPI response: {str(e)}")
    
    def get_citation(self, result_id: str) -> Dict:
        """
        Get citation details for a specific result using SerpAPI's citation endpoint
        
        Args:
            result_id: The unique identifier for the result
            
        Returns:
            Normalized citation data in the SCRS format
        """
        params = {
            "engine": "google_scholar_cite",
            "q": result_id,
            "api_key": self.api_key
        }
        
        try:
            response = requests.get(self.base_url, params=params, timeout=30)
            response.raise_for_status()
            return self._normalize_citation_results(response.json())
        except requests.RequestException as e:
            raise APIError(f"SerpAPI citation request failed: {str(e)}")
        except (KeyError, ValueError, TypeError) as e:
            raise APIError(f"Failed to process SerpAPI citation response: {str(e)}")
    
    def _normalize_search_results(self, raw_results: Dict) -> Dict:
        """
        Convert SerpAPI format to SCRS format
        
        Args:
            raw_results: Raw results from SerpAPI
            
        Returns:
            Normalized results in SCRS format
        """
        normalized = {
            "query": raw_results.get("search_parameters", {}).get("q", ""),
            "total_results": len(raw_results.get("organic_results", [])),
            "results": []
        }
        
        for result in raw_results.get("organic_results", []):
            # Extract PDF URL if available using our enhanced extraction logic
            pdf_url, pdf_available = self._extract_pdf_url(result)
            
            # Extract publication info
            pub_info = result.get("publication_info", {}).get("summary", "")
            
            # Extract journal directly 
            journal = ""
            parts = pub_info.split(" - ")
            if len(parts) > 2:
                journal = parts[2].split(",")[0].strip()
            
            # Extract DOI directly
            doi = None
            link = result.get("link", "")
            doi_match = re.search(r'10\.\d{4,9}/[-._;()/:a-zA-Z0-9]+', link)
            if doi_match:
                doi = doi_match.group(0)
            
            normalized["results"].append({
                "title": result.get("title", ""),
                "authors": self._parse_authors(pub_info),
                "publication_date": self._extract_date(pub_info),
                "journal": journal,
                "snippet": result.get("snippet", ""),
                "doi": doi,
                "pdf_available": pdf_available,
                "pdf_url": pdf_url,
                "full_text_available": False,  # We don't have full text from SerpAPI directly
                "full_text": None,
                "abstract": result.get("snippet", ""),
                "citation_count": result.get("inline_links", {}).get("cited_by", {}).get("total", 0),
                "source": "google_scholar",
                "source_url": result.get("link", ""),
                "result_id": result.get("result_id", "")
            })
        
        return normalized
    
    def _normalize_citation_results(self, raw_citation: Dict) -> Dict:
        """
        Convert SerpAPI citation format to SCRS format
        
        Args:
            raw_citation: Raw citation data from SerpAPI
            
        Returns:
            Normalized citation in SCRS format
        """
        citation = raw_citation.get("citation", {})
        
        # Extract PDF URL if available
        pdf_url, pdf_available = self._extract_pdf_url(citation)
        
        # Extract DOI directly
        doi = None
        link = citation.get("link", "")
        doi_match = re.search(r'10\.\d{4,9}/[-._;()/:a-zA-Z0-9]+', link)
        if doi_match:
            doi = doi_match.group(0)
        
        return {
            "title": citation.get("title", ""),
            "authors": citation.get("authors", "").split(", ") if citation.get("authors") else [],
            "publication_date": citation.get("publication_date", ""),
            "journal": citation.get("journal", ""),
            "abstract": citation.get("description", ""),
            "doi": doi,
            "pdf_available": pdf_available,
            "pdf_url": pdf_url,
            "full_text_available": False,
            "full_text": None,
            "citation_count": 0,
            "references": [],
            "source": "google_scholar",
            "source_url": citation.get("link", "")
        }
    
    def _extract_pdf_url(self, result: Dict) -> tuple:
        """
        Enhanced PDF URL extraction from result or citation
        
        Args:
            result: Result or citation object from SerpAPI
            
        Returns:
            Tuple of (pdf_url, pdf_available)
        """
        pdf_url = None
        pdf_available = False
        
        # Method 1: Check resources array for PDF links
        if "resources" in result:
            for resource in result.get("resources", []):
                if resource.get("file_format", "").upper() == "PDF":
                    pdf_url = resource.get("link")
                    pdf_available = True
                    break
        
        # Method 2: Check if main link is PDF
        if not pdf_url and result.get("link", "").lower().endswith(".pdf"):
            pdf_url = result.get("link")
            pdf_available = True
        
        # Method 3: Look for PDF link in snippet or description
        if not pdf_url:
            snippet = result.get("snippet", "") or result.get("description", "")
            pdf_matches = re.findall(r'https?://[^\s]+\.pdf', snippet, re.IGNORECASE)
            if pdf_matches:
                pdf_url = pdf_matches[0]
                pdf_available = True
        
        return pdf_url, pdf_available
    
    def _parse_authors(self, publication_info: str) -> List[str]:
        """
        Extract authors from publication info string
        
        Args:
            publication_info: Publication info string from SerpAPI
            
        Returns:
            List of author names
        """
        if not publication_info:
            return []
        
        # Common pattern: "Authors - Title, Year"
        parts = publication_info.split(" - ", 1)
        if len(parts) > 1:
            return [a.strip() for a in parts[0].split(", ")]
        
        return []
    
    def _extract_date(self, publication_info: str) -> str:
        """
        Extract date from publication info string
        
        Args:
            publication_info: Publication info string from SerpAPI
            
        Returns:
            Publication date as string
        """
        if not publication_info:
            return ""


@retry(wait=wait_exponential(multiplier=1, min=4, max=10),
       stop=stop_after_attempt(3))
def safe_api_call(url, params=None, headers=None):
    """
    Make a safe API call with retry logic for rate limiting and transient errors
    
    Args:
        url: The URL to call
        params: Optional query parameters
        headers: Optional request headers
        
    Returns:
        Response object from requests
        
    Raises:
        APIError: If the API call fails after retries
    """
    try:
        response = requests.get(url, params=params, headers=headers, timeout=30)
        response.raise_for_status()
        return response
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            # Don't retry 404 errors
            raise APIError(f"Resource not found: {url}")
        elif e.response.status_code == 429:
            # Rate limiting - will be retried
            raise APIError(f"Rate limit exceeded: {url}")
        else:
            # Other HTTP errors - will be retried
            raise APIError(f"HTTP error {e.response.status_code}: {url}")
    except requests.exceptions.Timeout:
        # Timeout - will be retried
        raise APIError(f"Request timed out: {url}")
    except requests.exceptions.RequestException as e:
        # General request exception - will be retried
        raise APIError(f"Request failed: {url}, {str(e)}")


class PubMedClient:
    """Client for interacting with PubMed/NCBI E-utilities"""
    
    def __init__(self, email: str, api_key: Optional[str] = None, tool: str = "scholarly-system"):
        """
        Initialize the PubMed client
        
        Args:
            email: Contact email for NCBI rate limiting
            api_key: Optional NCBI API key for higher rate limits
            tool: Tool name for NCBI
        """
        if not email:
            raise ConfigurationError("Email is required for PubMed/NCBI E-utilities")
            
        self.email = email
        self.api_key = api_key
        self.tool = tool
        self.base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
    
    def search(self, query: str, max_results: int = 10, offset: int = 0) -> Dict:
        """
        Search PubMed for articles matching the query
        
        Args:
            query: The search query
            max_results: Maximum number of results to return
            offset: Offset for pagination
            
        Returns:
            Normalized search results in SCRS format
        """
        # Set up search parameters
        search_params = {
            "db": "pubmed",
            "term": query,
            "retmode": "json",
            "retmax": max_results,
            "retstart": offset,
            "email": self.email,
            "tool": self.tool
        }
        
        if self.api_key:
            search_params["api_key"] = self.api_key
        
        # Search phase - get PMIDs
        search_url = f"{self.base_url}esearch.fcgi"
        search_response = safe_api_call(search_url, search_params)
        search_data = search_response.json()
        
        id_list = search_data.get("esearchresult", {}).get("idlist", [])
        total_results = int(search_data.get("esearchresult", {}).get("count", 0))
        
        if not id_list:
            return {
                "query": query,
                "total_results": 0,
                "results": []
            }
        
        # Fetch details for the IDs
        fetch_params = {
            "db": "pubmed",
            "id": ",".join(id_list),
            "retmode": "xml",
            "rettype": "abstract",
            "email": self.email,
            "tool": self.tool
        }
        
        if self.api_key:
            fetch_params["api_key"] = self.api_key
        
        fetch_url = f"{self.base_url}efetch.fcgi"
        fetch_response = safe_api_call(fetch_url, fetch_params)
        
        # Parse XML response
        try:
            root = ET.fromstring(fetch_response.content)
            articles = root.findall('.//PubmedArticle')
            
            results = []
            for article in articles:
                parsed_article = self._parse_pubmed_article(article)
                if parsed_article:
                    results.append(parsed_article)
            
            return {
                "query": query,
                "total_results": total_results,
                "results": results
            }
        except ET.ParseError as e:
            raise APIError(f"Failed to parse PubMed XML response: {str(e)}")
    
    def _parse_pubmed_article(self, article) -> Dict:
        """
        Parse a PubMed article XML element
        
        Args:
            article: ElementTree element for PubmedArticle
            
        Returns:
            Parsed article data in SCRS format
        """
        try:
            # Extract PMID
            pmid_elem = article.find('.//PMID')
            pmid = pmid_elem.text if pmid_elem is not None else None
            
            # Extract DOI
            doi_elem = article.find('.//ArticleId[@IdType="doi"]')
            doi = doi_elem.text if doi_elem is not None else None
            
            # Extract title
            title_elem = article.find('.//ArticleTitle')
            title = title_elem.text if title_elem is not None else ""
            
            # Extract abstract
            abstract_elem = article.find('.//AbstractText')
            abstract = abstract_elem.text if abstract_elem is not None else ""
            
            # Extract journal
            journal_elem = article.find('.//Journal/Title')
            journal = journal_elem.text if journal_elem is not None else ""
            
            # Extract authors
            authors = []
            author_elems = article.findall('.//Author')
            for author_elem in author_elems:
                last_name_elem = author_elem.find('LastName')
                fore_name_elem = author_elem.find('ForeName')
                
                if last_name_elem is not None and fore_name_elem is not None:
                    last_name = last_name_elem.text if last_name_elem.text else ""
                    fore_name = fore_name_elem.text if fore_name_elem.text else ""
                    authors.append(f"{last_name} {fore_name}".strip())
                elif last_name_elem is not None:
                    authors.append(last_name_elem.text)
            
            # Extract publication date
            year_elem = article.find('.//PubDate/Year')
            month_elem = article.find('.//PubDate/Month')
            day_elem = article.find('.//PubDate/Day')
            
            year = year_elem.text if year_elem is not None else ""
            month = month_elem.text if month_elem is not None else "01"
            day = day_elem.text if day_elem is not None else "01"
            
            # Try to construct a proper date
            pub_date = year
            if year and month and day:
                pub_date = f"{year}-{month}-{day}"
            elif year and month:
                pub_date = f"{year}-{month}"
            
            # Check for PMC ID (indicates potential free full text)
            pmc_elem = article.find('.//ArticleId[@IdType="pmc"]')
            pmc_id = pmc_elem.text if pmc_elem is not None else None
            
            pmc_url = None
            if pmc_id:
                pmc_url = f"https://www.ncbi.nlm.nih.gov/pmc/articles/{pmc_id}/pdf/"
            
            return {
                "title": title,
                "authors": authors,
                "publication_date": pub_date,
                "journal": journal,
                "snippet": abstract[:200] + "..." if len(abstract) > 200 else abstract,
                "abstract": abstract,
                "doi": doi,
                "pmid": pmid,
                "pdf_available": pmc_url is not None,
                "pdf_url": pmc_url,
                "full_text_available": False,
                "full_text": None,
                "citation_count": 0,  # Not available from basic PubMed
                "source": "pubmed",
                "source_url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else None,
                "result_id": pmid if pmid else None
            }
        except Exception as e:
            # Log error but continue with other results
            print(f"Error parsing PubMed article: {str(e)}")
            return None


class ArXivClient:
    """Client for interacting with arXiv API"""
    
    def __init__(self):
        """Initialize the arXiv client"""
        self.base_url = "http://export.arxiv.org/api/query"
        
    def search(self, query: str, max_results: int = 10, offset: int = 0) -> Dict:
        """
        Search arXiv for articles matching the query
        
        Args:
            query: The search query
            max_results: Maximum number of results to return
            offset: Offset for pagination
            
        Returns:
            Normalized search results in SCRS format
        """
        # Set up search parameters
        params = {
            "search_query": f"all:{query}",
            "start": offset,
            "max_results": max_results,
            "sortBy": "relevance",
            "sortOrder": "descending"
        }
        
        response = safe_api_call(self.base_url, params)
        
        try:
            # Parse XML response
            root = ET.fromstring(response.content)
            
            # Define namespaces
            ns = {
                'atom': 'http://www.w3.org/2005/Atom',
                'arxiv': 'http://arxiv.org/schemas/atom'
            }
            
            # Get total results (approximate)
            total_results_elem = root.find('.//opensearch:totalResults', 
                                           {'opensearch': 'http://a9.com/-/spec/opensearch/1.1/'})
            total_results = int(total_results_elem.text) if total_results_elem is not None else 0
            
            # Parse entries
            entries = root.findall('.//atom:entry', ns)
            results = []
            
            for entry in entries:
                parsed_entry = self._parse_arxiv_entry(entry, ns)
                if parsed_entry:
                    results.append(parsed_entry)
            
            return {
                "query": query,
                "total_results": total_results,
                "results": results
            }
            
        except ET.ParseError as e:
            raise APIError(f"Failed to parse arXiv XML response: {str(e)}")
    
    def _parse_arxiv_entry(self, entry, ns) -> Dict:
        """
        Parse an arXiv entry XML element
        
        Args:
            entry: ElementTree element for an arXiv entry
            ns: XML namespaces
            
        Returns:
            Parsed entry data in SCRS format
        """
        try:
            # Extract ID (arxiv ID)
            id_elem = entry.find('./atom:id', ns)
            full_id = id_elem.text if id_elem is not None else None
            arxiv_id = full_id.split('/')[-1] if full_id else None
            
            # Extract title
            title_elem = entry.find('./atom:title', ns)
            title = title_elem.text if title_elem is not None else ""
            
            # Extract summary (abstract)
            summary_elem = entry.find('./atom:summary', ns)
            summary = summary_elem.text if summary_elem is not None else ""
            
            # Extract authors
            authors = []
            author_elems = entry.findall('./atom:author/atom:name', ns)
            for author_elem in author_elems:
                if author_elem.text:
                    authors.append(author_elem.text)
            
            # Extract publication date
            published_elem = entry.find('./atom:published', ns)
            published = published_elem.text if published_elem is not None else None
            pub_date = ""
            if published:
                try:
                    dt = datetime.strptime(published, "%Y-%m-%dT%H:%M:%SZ")
                    pub_date = dt.strftime("%Y-%m-%d")
                except ValueError:
                    pub_date = published.split('T')[0] if 'T' in published else published
            
            # Extract DOI if available
            doi = None
            doi_elem = entry.find('./arxiv:doi', ns)
            if doi_elem is not None and doi_elem.text:
                doi = doi_elem.text
            
            # Extract journal reference if available
            journal_ref = None
            journal_ref_elem = entry.find('./arxiv:journal_ref', ns)
            if journal_ref_elem is not None and journal_ref_elem.text:
                journal_ref = journal_ref_elem.text
            
            # Extract categories
            categories = []
            category_elems = entry.findall('./arxiv:category', ns)
            for category_elem in category_elems:
                if 'term' in category_elem.attrib:
                    categories.append(category_elem.attrib['term'])
            
            # Direct PDF link
            pdf_url = f"https://arxiv.org/pdf/{arxiv_id}" if arxiv_id else None
            
            return {
                "title": title,
                "authors": authors,
                "publication_date": pub_date,
                "journal": journal_ref,
                "snippet": summary[:200] + "..." if len(summary) > 200 else summary,
                "abstract": summary,
                "doi": doi,
                "arxiv_id": arxiv_id,
                "pdf_available": arxiv_id is not None,
                "pdf_url": pdf_url,
                "full_text_available": False,  # We don't parse full text
                "full_text": None,
                "citation_count": 0,  # Not available from arXiv API
                "source": "arxiv",
                "source_url": f"https://arxiv.org/abs/{arxiv_id}" if arxiv_id else None,
                "result_id": arxiv_id if arxiv_id else None,
                "categories": categories
            }
        except Exception as e:
            # Log error but continue with other results
            print(f"Error parsing arXiv entry: {str(e)}")
            return None


class OpenAIREClient:
    """Client for interacting with OpenAIRE API"""
    
    def __init__(self):
        """Initialize the OpenAIRE client"""
        self.base_url = "https://api.openaire.eu/"
    
    def search(self, query: str, max_results: int = 10, offset: int = 0) -> Dict:
        """
        Search OpenAIRE for open access publications
        
        Args:
            query: The search query
            max_results: Maximum number of results to return
            offset: Offset for pagination
            
        Returns:
            Normalized search results in SCRS format
        """
        # Set up search parameters
        params = {
            "keywords": query,
            "format": "json",
            "size": max_results,
            "page": (offset // max_results) + 1 if max_results > 0 else 1
        }
        
        response = safe_api_call(f"{self.base_url}search/publications", params)
        
        try:
            data = response.json()
            results_data = data.get("response", {}).get("results", {})
            
            # Extract total count
            total_results = int(results_data.get("total", 0))
            
            # Extract results
            result_items = results_data.get("result", [])
            if not isinstance(result_items, list):
                result_items = [result_items]
            
            results = []
            for item in result_items:
                parsed_item = self._parse_openaire_item(item)
                if parsed_item:
                    results.append(parsed_item)
            
            return {
                "query": query,
                "total_results": total_results,
                "results": results
            }
            
        except (ValueError, KeyError) as e:
            raise APIError(f"Failed to parse OpenAIRE response: {str(e)}")
    
    def _parse_openaire_item(self, item) -> Dict:
        """
        Parse an OpenAIRE result item
        
        Args:
            item: OpenAIRE result item
            
        Returns:
            Parsed item data in SCRS format
        """
        try:
            # Extract metadata from nested structure
            metadata = item.get("metadata", {}).get("oaf:entity", {}).get("oaf:result", {})
            
            # Extract title
            title = ""
            title_data = metadata.get("title")
            if isinstance(title_data, dict) and "value" in title_data:
                title = title_data["value"]
            elif isinstance(title_data, list) and len(title_data) > 0:
                for t in title_data:
                    if isinstance(t, dict) and "value" in t:
                        title = t["value"]
                        break
            
            # Extract DOI
            doi = None
            pid_data = metadata.get("pid")
            if pid_data:
                if isinstance(pid_data, list):
                    for pid in pid_data:
                        if isinstance(pid, dict) and pid.get("classid") == "doi":
                            doi = pid.get("value")
                            break
                elif isinstance(pid_data, dict) and pid_data.get("classid") == "doi":
                    doi = pid_data.get("value")
            
            # Extract authors
            authors = []
            creator_data = metadata.get("creator")
            if creator_data:
                if isinstance(creator_data, list):
                    for creator in creator_data:
                        if isinstance(creator, dict) and "value" in creator:
                            authors.append(creator["value"])
                elif isinstance(creator_data, dict) and "value" in creator_data:
                    authors.append(creator_data["value"])
            
            # Extract publication date
            pub_date = ""
            date_data = metadata.get("dateofacceptance")
            if date_data:
                if isinstance(date_data, dict) and "value" in date_data:
                    pub_date = date_data["value"]
                elif isinstance(date_data, str):
                    pub_date = date_data
            
            # Extract journal
            journal = ""
            journal_data = metadata.get("journal")
            if journal_data:
                if isinstance(journal_data, dict) and "value" in journal_data:
                    journal = journal_data["value"]
                elif isinstance(journal_data, str):
                    journal = journal_data
            
            # Extract description/abstract
            abstract = ""
            description_data = metadata.get("description")
            if description_data:
                if isinstance(description_data, dict) and "value" in description_data:
                    abstract = description_data["value"]
                elif isinstance(description_data, list) and len(description_data) > 0:
                    for d in description_data:
                        if isinstance(d, dict) and "value" in d:
                            abstract = d["value"]
                            break
            
            # Extract PDF URL
            pdf_url = None
            pdf_available = False
            instance_data = metadata.get("instance")
            if instance_data:
                if isinstance(instance_data, list):
                    for instance in instance_data:
                        if isinstance(instance, dict) and "accessright" in instance:
                            if instance["accessright"] in ["OPEN", "open"]:
                                webresource = instance.get("webresource")
                                if webresource and isinstance(webresource, dict) and "url" in webresource:
                                    url = webresource["url"]
                                    if url.lower().endswith(".pdf"):
                                        pdf_url = url
                                        pdf_available = True
                                        break
                elif isinstance(instance_data, dict) and "accessright" in instance_data:
                    if instance_data["accessright"] in ["OPEN", "open"]:
                        webresource = instance_data.get("webresource")
                        if webresource and isinstance(webresource, dict) and "url" in webresource:
                            url = webresource["url"]
                            if url.lower().endswith(".pdf"):
                                pdf_url = url
                                pdf_available = True
            
            # Generate result ID
            result_id = doi if doi else f"openaire_{title.lower().replace(' ', '_')[:50]}"
            
            return {
                "title": title,
                "authors": authors,
                "publication_date": pub_date,
                "journal": journal,
                "snippet": abstract[:200] + "..." if len(abstract) > 200 else abstract,
                "abstract": abstract,
                "doi": doi,
                "pdf_available": pdf_available,
                "pdf_url": pdf_url,
                "full_text_available": False,  # We don't parse full text
                "full_text": None,
                "citation_count": 0,  # Not available from OpenAIRE
                "source": "openaire",
                "source_url": f"https://explore.openaire.eu/search/publication?pid={doi}" if doi else None,
                "result_id": result_id
            }
        except Exception as e:
            # Log error but continue with other results
            print(f"Error parsing OpenAIRE item: {str(e)}")
            return None


class UnpaywallClient:
    """Client for resolving PDFs using Unpaywall API"""
    
    def __init__(self, email: str):
        """
        Initialize the Unpaywall client
        
        Args:
            email: Contact email for Unpaywall API
        """
        if not email:
            raise ConfigurationError("Email is required for Unpaywall API")
            
        self.email = email
        self.base_url = "https://api.unpaywall.org/v2/"
    
    @lru_cache(maxsize=128)
    def resolve_pdf(self, doi: str) -> Dict:
        """
        Resolve PDF for a DOI using Unpaywall
        
        Args:
            doi: The DOI to resolve
            
        Returns:
            Dictionary with PDF URL and source if available
        """
        if not doi:
            return {"pdf_available": False, "pdf_url": None, "oa_status": None}
        
        url = f"{self.base_url}{doi}?email={self.email}"
        
        try:
            response = safe_api_call(url)
            data = response.json()
            
            # Check for best OA location
            best_oa_location = data.get("best_oa_location", {})
            oa_status = data.get("oa_status")
            
            if best_oa_location and isinstance(best_oa_location, dict):
                # Try direct PDF URL first
                pdf_url = best_oa_location.get("url_for_pdf")
                
                # Fall back to landing page if no direct PDF
                if not pdf_url:
                    pdf_url = best_oa_location.get("url")
                
                if pdf_url:
                    return {
                        "pdf_available": True,
                        "pdf_url": pdf_url,
                        "oa_status": oa_status,
                        "source": best_oa_location.get("repository_institution") or "unpaywall"
                    }
            
            return {"pdf_available": False, "pdf_url": None, "oa_status": oa_status}
            
        except (APIError, ValueError) as e:
            # Log error but don't fail the entire request
            print(f"Error resolving DOI {doi} with Unpaywall: {str(e)}")
            return {"pdf_available": False, "pdf_url": None, "oa_status": None}
        
        # Look for 4-digit year
        year_match = re.search(r'\b(19|20)\d{2}\b', publication_info)
        if year_match:
            return year_match.group(0)
        
        return ""
    
    def _extract_journal(self, publication_info: str) -> str:
        """
        Extract journal from publication info string
        
        Args:
            publication_info: Publication info string from SerpAPI
            
        Returns:
            Journal name
        """
        if not publication_info:
            return ""
        
        # Common pattern: "Authors - Title, Year - journal"
        parts = publication_info.split(" - ")
        if len(parts) > 2:
            journal_part = parts[2].split(",")[0].strip()
            return journal_part
        
        return ""
    
    def _extract_doi(self, url: str) -> str:
        """
        Extract DOI from URL if present
        
        Args:
            url: URL that might contain a DOI
            
        Returns:
            DOI string if found, otherwise empty string
        """
        doi_match = re.search(r'10\.\d{4,9}/[-._;()/:a-zA-Z0-9]+', url)
        if doi_match:
            return doi_match.group(0)
        
        return ""


class ScholarlyContentRetrieval:
    """
    Main class for scholarly content retrieval that integrates various data sources
    """
    
    def __init__(self, config: Dict):
        """
        Initialize the scholarly content retrieval system
        
        Args:
            config: Configuration dictionary with API keys and settings
        """
        self._validate_config(config)
        self.config = config
        
        # Initialize clients
        self.serp_client = SerpAPIClient(
            api_key=config.get("serp_api", {}).get("api_key", ""),
            base_url=config.get("serp_api", {}).get("base_url", "https://serpapi.com/search")
        )
        
        # Initialize PubMed client if configured
        self.pubmed_client = None
        if "pubmed" in config:
            self.pubmed_client = PubMedClient(
                email=config.get("pubmed", {}).get("email", ""),
                api_key=config.get("pubmed", {}).get("api_key"),
                tool=config.get("pubmed", {}).get("tool", "scholarly-system")
            )
        
        # Initialize arXiv client
        self.arxiv_client = ArXivClient()
        
        # Initialize OpenAIRE client
        self.openaire_client = OpenAIREClient()
        
        # Initialize Unpaywall client if email is configured
        self.unpaywall_client = None
        unpaywall_email = config.get("unpaywall", {}).get("email") or config.get("pubmed", {}).get("email")
        if unpaywall_email:
            self.unpaywall_client = UnpaywallClient(email=unpaywall_email)
    
    def _validate_config(self, config: Dict):
        """
        Validate the configuration
        
        Args:
            config: Configuration dictionary
            
        Raises:
            ConfigurationError: If configuration is invalid
        """
        if not config:
            raise ConfigurationError("Configuration is required")
        
        # Check for at least one API key/configuration
        if not any(key in config for key in ["serp_api", "pubmed", "unpaywall"]):
            raise ConfigurationError("At least one API configuration is required")
        
        # Validate SerpAPI config if present
        if "serp_api" in config and not config.get("serp_api", {}).get("api_key"):
            raise ConfigurationError("SerpAPI API key is required if SerpAPI is configured")
        
        # Validate PubMed config if present
        if "pubmed" in config and not config.get("pubmed", {}).get("email"):
            raise ConfigurationError("Email is required for PubMed/NCBI E-utilities")
        
        # Validate Unpaywall config if present
        if "unpaywall" in config and not config.get("unpaywall", {}).get("email"):
            # Check if we can use PubMed email instead
            if not config.get("pubmed", {}).get("email"):
                raise ConfigurationError("Email is required for Unpaywall API")
    
    def search(self, params: Dict) -> Dict:
        """
        Search for scholarly content with the given parameters
        
        Args:
            params: Search parameters
                - query: Search query (required)
                - sources: List of acceptable sources (optional)
                - year_from: Start year for publication filter (optional)
                - year_to: End year for publication filter (optional)
                - journal: Filter by journal name (optional)
                - limit: Number of results (optional, default: 10)
                - offset: Results offset for pagination (optional, default: 0)
                - pdf_only: Return only results with PDF links (optional, default: False)
                - full_text_only: Return only results with full text (optional, default: False)
                - resolve_pdfs: Attempt to resolve PDF links using Unpaywall (optional, default: True)
                
        Returns:
            Standardized search results in SCRS format
        """
        self._validate_search_params(params)
        
        query = params.get("query", "")
        sources = params.get("sources", ["google_scholar", "arxiv", "pubmed", "openaire"])
        limit = params.get("limit", 10)
        offset = params.get("offset", 0)
        year_from = params.get("year_from")
        year_to = params.get("year_to")
        journal = params.get("journal")
        pdf_only = params.get("pdf_only", False)
        full_text_only = params.get("full_text_only", False)
        resolve_pdfs = params.get("resolve_pdfs", True)
        
        all_results = []
        result_count = 0
        source_results = {}
        
        # Process each source
        for source in sources:
            try:
                if source == "google_scholar" and self.serp_client:
                    source_results[source] = self.serp_client.search_scholar(
                        query=query,
                        limit=limit,
                        offset=offset,
                        year_from=year_from,
                        year_to=year_to,
                        journal=journal
                    )
                    result_count += source_results[source].get("total_results", 0)
                    all_results.extend(source_results[source].get("results", []))
                
                elif source == "pubmed" and self.pubmed_client:
                    source_results[source] = self.pubmed_client.search(
                        query=query,
                        max_results=limit,
                        offset=offset
                    )
                    result_count += source_results[source].get("total_results", 0)
                    all_results.extend(source_results[source].get("results", []))
                
                elif source == "arxiv":
                    source_results[source] = self.arxiv_client.search(
                        query=query,
                        max_results=limit,
                        offset=offset
                    )
                    result_count += source_results[source].get("total_results", 0)
                    all_results.extend(source_results[source].get("results", []))
                
                elif source == "openaire":
                    source_results[source] = self.openaire_client.search(
                        query=query,
                        max_results=limit,
                        offset=offset
                    )
                    result_count += source_results[source].get("total_results", 0)
                    all_results.extend(source_results[source].get("results", []))
            
            except Exception as e:
                # Log the error but continue with other sources
                print(f"Error searching {source}: {str(e)}")
        
        # If we have no results, return an empty result set
        if not all_results:
            return {
                "query": query,
                "total_results": 0,
                "results": [],
                "pagination": {
                    "current_page": 1,
                    "total_pages": 0,
                    "has_next": False,
                    "has_previous": False
                }
            }
        
        # Attempt to resolve PDFs using Unpaywall if requested and client is available
        if resolve_pdfs and self.unpaywall_client:
            for result in all_results:
                # Skip if already has PDF URL
                if result.get("pdf_available", False) and result.get("pdf_url"):
                    continue
                
                # Try to resolve PDF if DOI is available
                if result.get("doi"):
                    unpaywall_data = self.unpaywall_client.resolve_pdf(result["doi"])
                    if unpaywall_data.get("pdf_available", False) and unpaywall_data.get("pdf_url"):
                        result["pdf_available"] = True
                        result["pdf_url"] = unpaywall_data["pdf_url"]
                        # Add Unpaywall metadata to result
                        result["unpaywall"] = {
                            "oa_status": unpaywall_data.get("oa_status"),
                            "source": unpaywall_data.get("source")
                        }
        
        # Filter by year if requested
        if year_from or year_to:
            filtered_results = []
            for result in all_results:
                pub_date = result.get("publication_date", "")
                # Extract year part only
                year_match = re.search(r"\b(19|20)\d{2}\b", pub_date)
                if year_match:
                    year = int(year_match.group(0))
                    if year_from and year < year_from:
                        continue
                    if year_to and year > year_to:
                        continue
                filtered_results.append(result)
            all_results = filtered_results
        
        # Filter by journal if requested
        if journal:
            all_results = [
                r for r in all_results 
                if journal.lower() in r.get("journal", "").lower()
            ]
        
        # Apply PDF and full text filters
        if pdf_only:
            all_results = [
                r for r in all_results 
                if r.get("pdf_available", False)
            ]
            
        if full_text_only:
            all_results = [
                r for r in all_results 
                if r.get("full_text_available", False)
            ]
        
        # Convert to standardized format
        results = {
            "query": query,
            "total_results": len(all_results),
            "results": all_results
        }
        
        # Add pagination data
        results["pagination"] = {
            "current_page": offset // limit + 1 if limit > 0 else 1,
            "total_pages": (results["total_results"] + limit - 1) // limit if limit > 0 else 1,
            "has_next": offset + limit < results["total_results"] if limit > 0 else False,
            "has_previous": offset > 0
        }
        
        return results
    
    def get_document(self, result_id: str, source: Optional[str] = None, doi: Optional[str] = None, resolve_pdf: bool = True) -> Dict:
        """
        Get detailed document information for a specific result
        
        Args:
            result_id: The unique identifier for the result
            source: Optional source name to help route the request
            doi: Optional DOI for the document (helps with PDF resolution)
            resolve_pdf: Whether to attempt to resolve PDF link
            
        Returns:
            Detailed document information in SCRS format
        """
        if not result_id and not doi:
            raise ValidationError("Either result_id or DOI is required")
        
        result = None
        
        # If we only have a DOI, try to search for it across sources
        if doi and not result_id:
            print(f"Searching for document with DOI: {doi}")
            # Try each source to find the DOI - handle errors for each source separately
            source_errors = {}
            
            # Try arXiv first (usually fastest)
            if self.arxiv_client:
                try:
                    print("Searching arXiv...")
                    search_results = self.arxiv_client.search(f"doi:{doi}", max_results=1)
                    if search_results and search_results.get("results") and search_results["results"]:
                        result = search_results["results"][0]
                        source = "arxiv"
                        result_id = result.get("arxiv_id", "")
                        print(f"Found in arXiv with ID: {result_id}")
                except Exception as e:
                    source_errors["arxiv"] = str(e)
                    print(f"Error searching arXiv: {str(e)}")
            
            # Try PubMed next if we didn't find it in arXiv
            if not result and self.pubmed_client:
                try:
                    print("Searching PubMed...")
                    search_results = self.pubmed_client.search(f"{doi}[doi]", max_results=1)
                    if search_results and search_results.get("results") and search_results["results"]:
                        result = search_results["results"][0]
                        source = "pubmed"
                        result_id = result.get("pmid", "")
                        print(f"Found in PubMed with ID: {result_id}")
                except Exception as e:
                    source_errors["pubmed"] = str(e)
                    print(f"Error searching PubMed: {str(e)}")
            
            # Finally try OpenAIRE if we still haven't found it
            if not result and self.openaire_client:
                try:
                    print("Searching OpenAIRE...")
                    search_results = self.openaire_client.search(doi, max_results=1)
                    if search_results and search_results.get("results") and search_results["results"]:
                        result = search_results["results"][0]
                        source = "openaire"
                        result_id = result.get("result_id", "")
                        print(f"Found in OpenAIRE with ID: {result_id}")
                except Exception as e:
                    source_errors["openaire"] = str(e)
                    print(f"Error searching OpenAIRE: {str(e)}")
            
            # If we found a result, we can return early
            if result:
                # Try to resolve PDF link if requested
                if resolve_pdf and self.unpaywall_client and not result.get("pdf_available"):
                    try:
                        unpaywall_data = self.unpaywall_client.resolve_pdf(doi)
                        if unpaywall_data.get("pdf_available", False) and unpaywall_data.get("pdf_url"):
                            result["pdf_available"] = True
                            result["pdf_url"] = unpaywall_data["pdf_url"]
                            # Add Unpaywall metadata to result
                            result["unpaywall"] = {
                                "oa_status": unpaywall_data.get("oa_status"),
                                "source": unpaywall_data.get("source")
                            }
                    except Exception as e:
                        print(f"Error resolving PDF with Unpaywall: {str(e)}")
                return result
            
            # If we got here, we couldn't find the DOI in any source
            # Create a basic result with the DOI we have
            if not result:
                # If we have at least Unpaywall, try to get some basic info
                if self.unpaywall_client and doi:
                    try:
                        print("Trying Unpaywall for basic metadata...")
                        unpaywall_data = self.unpaywall_client.resolve_pdf(doi)
                        if unpaywall_data.get("pdf_available", False):
                            # Create a minimal result with the DOI and PDF info
                            result = {
                                "title": f"Document with DOI: {doi}",
                                "authors": [],
                                "publication_date": "",
                                "journal": "",
                                "abstract": "",
                                "doi": doi,
                                "pdf_available": True,
                                "pdf_url": unpaywall_data.get("pdf_url"),
                                "full_text_available": False,
                                "full_text": None,
                                "citation_count": 0,
                                "source": "unpaywall",
                                "source_url": f"https://doi.org/{doi}",
                                "result_id": doi,
                                "unpaywall": {
                                    "oa_status": unpaywall_data.get("oa_status"),
                                    "source": unpaywall_data.get("source")
                                }
                            }
                            return result
                    except Exception as e:
                        source_errors["unpaywall"] = str(e)
                        print(f"Error with Unpaywall: {str(e)}")
                
                # We've tried all sources and still couldn't find anything
                error_details = ", ".join([f"{s}: {e}" for s, e in source_errors.items()])
                raise ResourceNotFoundError(
                    f"Could not find document with DOI {doi} in any source. Errors: {error_details}"
                )
        
        # If we got here, we either have a result_id or we already handled the DOI case
        
        # Try to determine source if not provided
        if not source and result_id:
            if result_id.startswith("PMC") or result_id.isdigit():
                source = "pubmed"
            elif "." not in result_id and not result_id.startswith("openaire_"):
                source = "arxiv"
            elif result_id.startswith("openaire_"):
                source = "openaire"
            else:
                source = "google_scholar"  # Default to Google Scholar
        
        # Retrieve document based on source
        try:
            if source == "google_scholar":
                result = self.serp_client.get_citation(result_id)
            
            elif source == "pubmed" and self.pubmed_client:
                # For PubMed, we need to do a search by ID
                search_results = self.pubmed_client.search(f"ID:{result_id}", max_results=1)
                if search_results and search_results.get("results"):
                    result = search_results["results"][0]
            
            elif source == "arxiv":
                # For arXiv, we need to do a search by ID
                search_results = self.arxiv_client.search(f"id:{result_id}", max_results=1)
                if search_results and search_results.get("results"):
                    result = search_results["results"][0]
            
            elif source == "openaire":
                # For OpenAIRE, search by ID or DOI
                query = doi if doi else result_id
                search_results = self.openaire_client.search(query, max_results=1)
                if search_results and search_results.get("results"):
                    result = search_results["results"][0]
        
        except Exception as e:
            raise APIError(f"Failed to retrieve document from {source}: {str(e)}")
        
        # If no result found, raise an error
        if not result:
            raise ResourceNotFoundError(f"Document with ID {result_id} not found in {source} source")
        
        # Try to resolve PDF link if requested and if DOI is available
        if resolve_pdf and self.unpaywall_client and not result.get("pdf_available") and (doi or result.get("doi")):
            doc_doi = doi or result.get("doi")
            try:
                unpaywall_data = self.unpaywall_client.resolve_pdf(doc_doi)
                if unpaywall_data.get("pdf_available", False) and unpaywall_data.get("pdf_url"):
                    result["pdf_available"] = True
                    result["pdf_url"] = unpaywall_data["pdf_url"]
                    # Add Unpaywall metadata to result
                    result["unpaywall"] = {
                        "oa_status": unpaywall_data.get("oa_status"),
                        "source": unpaywall_data.get("source")
                    }
            except Exception as e:
                print(f"Error resolving PDF with Unpaywall: {str(e)}")
        
        return result
    
    def _validate_search_params(self, params: Dict):
        """
        Validate search parameters
        
        Args:
            params: Search parameters
            
        Raises:
            ValidationError: If parameters are invalid
        """
        if not params:
            raise ValidationError("Search parameters are required")
            
        if not params.get("query"):
            raise ValidationError("Query parameter is required")
            
        limit = params.get("limit", 10)
        offset = params.get("offset", 0)
        
        if not isinstance(limit, int) or limit < 1:
            raise ValidationError("Limit must be a positive integer")
            
        if not isinstance(offset, int) or offset < 0:
            raise ValidationError("Offset must be a non-negative integer")


def process_scholarly_request(request_data: Dict) -> Dict:
    """
    Process a scholarly content retrieval request in JSON-RPC format
    
    Args:
        request_data: JSON-RPC request data with the following structure:
            {
                "method": "search" or "get_document",
                "params": {
                    # For search method:
                    "query": "search query",
                    "sources": ["google_scholar", "pubmed", "arxiv", "openaire"],  # Optional
                    "year_from": 2020,  # Optional
                    "year_to": 2023,  # Optional
                    "journal": "Nature",  # Optional
                    "limit": 10,  # Optional
                    "offset": 0,  # Optional
                    "pdf_only": false,  # Optional
                    "full_text_only": false,  # Optional
                    "resolve_pdfs": true  # Optional
                    
                    # For get_document method:
                    "result_id": "document_id",  # Required if no DOI provided
                    "source": "google_scholar",  # Optional
                    "doi": "10.xxxx/yyyy",  # Optional, but helpful for PDF resolution
                    "resolve_pdf": true  # Optional
                },
                "id": 1  # Optional request ID
            }
            
    Returns:
        JSON-RPC response with results or error
    """
    # Validate the request
    if not isinstance(request_data, dict):
        return {
            "jsonrpc": "2.0",
            "error": {"code": -32600, "message": "Invalid Request"},
            "id": None
        }
        
    method = request_data.get("method")
    params = request_data.get("params", {})
    request_id = request_data.get("id")
    
    # Initialize response
    response = {
        "jsonrpc": "2.0",
        "id": request_id
    }
    
    try:
        # Get configuration from environment variables
        config = {
            # SerpAPI configuration
            "serp_api": {
                "api_key": os.environ.get("SERP_API_KEY", ""),
                "base_url": os.environ.get("SERP_API_BASE_URL", "https://serpapi.com/search")
            },
            # PubMed/NCBI configuration
            "pubmed": {
                "email": os.environ.get("PUBMED_EMAIL", ""),
                "api_key": os.environ.get("PUBMED_API_KEY", ""),
                "tool": os.environ.get("PUBMED_TOOL", "scholarly-system")
            },
            # Unpaywall configuration
            "unpaywall": {
                "email": os.environ.get("UNPAYWALL_EMAIL", os.environ.get("PUBMED_EMAIL", ""))
            },
            # System settings
            "system": {
                "cache_expiration": int(os.environ.get("CACHE_EXPIRATION", 86400)),
                "max_concurrent_requests": int(os.environ.get("MAX_CONCURRENT_REQUESTS", 10)),
                "default_search_limit": int(os.environ.get("DEFAULT_SEARCH_LIMIT", 10)),
                "timeout": int(os.environ.get("REQUEST_TIMEOUT", 30))
            }
        }
        
        # Create client
        client = ScholarlyContentRetrieval(config)
        
        # Process the request based on method
        if method == "search":
            response["result"] = client.search(params)
        elif method == "get_document":
            response["result"] = client.get_document(
                result_id=params.get("result_id", ""),
                source=params.get("source"),
                doi=params.get("doi"),
                resolve_pdf=params.get("resolve_pdf", True)
            )
        else:
            response["error"] = {
                "code": -32601,
                "message": f"Method '{method}' not found"
            }
            
    except ConfigurationError as e:
        response["error"] = {
            "code": -32603,
            "message": f"Configuration error: {str(e)}"
        }
    except ValidationError as e:
        response["error"] = {
            "code": -32602,
            "message": f"Invalid params: {str(e)}"
        }
    except APIError as e:
        response["error"] = {
            "code": -32001,
            "message": f"API error: {str(e)}"
        }
    except ResourceNotFoundError as e:
        response["error"] = {
            "code": -32002,
            "message": f"Resource not found: {str(e)}"
        }
    except RateLimitError as e:
        response["error"] = {
            "code": -32003,
            "message": f"Rate limit exceeded: {str(e)}"
        }
    except Exception as e:
        response["error"] = {
            "code": -32000,
            "message": f"Server error: {str(e)}"
        }
    
    return response


# Example usage
if __name__ == "__main__":
    # Set API keys and configuration in environment variables
    os.environ["SERP_API_KEY"] = "your_serp_api_key_here"
    os.environ["PUBMED_EMAIL"] = "your_email@example.com"
    os.environ["PUBMED_API_KEY"] = "your_pubmed_api_key_here"  # Optional
    os.environ["UNPAYWALL_EMAIL"] = "your_email@example.com"  # Or use PUBMED_EMAIL
    
    # Example 1: Search across all sources for quantum computing papers
    search_request = {
        "method": "search",
        "params": {
            "query": "quantum computing",
            "sources": ["google_scholar", "arxiv", "pubmed", "openaire"],
            "year_from": 2020,
            "limit": 5,
            "pdf_only": True,
            "resolve_pdfs": True
        },
        "id": 1
    }
    
    # Process request
    result = process_scholarly_request(search_request)
    print("Example 1: Search across all sources for quantum computing papers")
    print(json.dumps(result, indent=2))
    print("\n" + "-"*80 + "\n")
    
    # Example 2: Search specifically in arXiv
    arxiv_search_request = {
        "method": "search",
        "params": {
            "query": "neural networks",
            "sources": ["arxiv"],
            "limit": 3
        },
        "id": 2
    }
    
    # Process request
    arxiv_result = process_scholarly_request(arxiv_search_request)
    print("Example 2: Search specifically in arXiv")
    print(json.dumps(arxiv_result, indent=2))
    print("\n" + "-"*80 + "\n")
    
    # Example 3: Get document details by DOI
    if "result" in result and result["result"]["results"] and result["result"]["results"][0].get("doi"):
        # Get DOI from the first search result
        document_doi = result["result"]["results"][0]["doi"]
        
        document_request = {
            "method": "get_document",
            "params": {
                "doi": document_doi,
                "resolve_pdf": True
            },
            "id": 3
        }
        
        # Process request
        document_result = process_scholarly_request(document_request)
        print(f"Example 3: Get document details by DOI: {document_doi}")
        print(json.dumps(document_result, indent=2))