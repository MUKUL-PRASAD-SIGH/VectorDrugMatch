"""
src/scoring/literature.py - PubMed Evidence Scoring

Queries the NCBI Entrez API to count the number of published papers
mentioning both the candidate drug and the target disease.

Implements caching via SQLite to avoid hitting rate limits for 
repeated queries.
"""

import os
import time
from typing import Optional

try:
    from Bio import Entrez
    import sqlitedict
    BIO_AVAILABLE = True
except ImportError:
    BIO_AVAILABLE = False


# The Entrez email must be set to comply with NCBI guidelines
Entrez.email = os.getenv("ENTREZ_EMAIL", "researcher@example.com")
CACHE_FILE = "data/processed/pubmed_cache.sqlite"


def get_pubmed_data(drug_name: str, disease_name: str, use_cache: bool = True, max_results: int = 5) -> dict:
    """Query PubMed for co-occurrence of drug and disease and fetch metadata.
    
    Args:
        drug_name: Name of the drug.
        disease_name: Name of the disease.
        use_cache: Whether to use local SQLite cache to prevent API spam.
        max_results: Maximum number of publication metadata to extract.
        
    Returns:
        Dict containing total 'count' and 'papers' (list of metadata).
    """
    empty_result = {"count": 0, "papers": []}
    if not BIO_AVAILABLE:
        print("[WARNING] Biopython not installed. Returning literature count 0.")
        return empty_result
        
    if not drug_name or not disease_name:
        return empty_result
        
    query = f'"{drug_name}"[Title/Abstract] AND "{disease_name}"[Title/Abstract]'
    
    # 1. Check Cache
    if use_cache:
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
        try:
            with sqlitedict.SqliteDict(CACHE_FILE, autocommit=True) as cache:
                if query in cache:
                    # Backward compatibility for old cache
                    cached = cache[query]
                    if isinstance(cached, int):
                        return {"count": cached, "papers": []}
                    return cached
        except Exception as e:
            print(f"Cache error: {e}")
            
    # 2. Query API
    try:
        # Respect NCBI guidelines: max 3 requests per second
        time.sleep(0.35) 
        
        handle = Entrez.esearch(db="pubmed", term=query, retmax=max_results)
        record = Entrez.read(handle)
        handle.close()
        
        count = int(record["Count"])
        paper_ids = record.get("IdList", [])
        papers = []
        
        # 3. Fetch Metadata
        if paper_ids:
            time.sleep(0.35)
            summary_handle = Entrez.esummary(db="pubmed", id=",".join(paper_ids))
            summaries = Entrez.read(summary_handle)
            summary_handle.close()
            
            for summary in summaries:
                papers.append({
                    "id": summary.get("Id", ""),
                    "title": summary.get("Title", ""),
                    "pub_date": summary.get("PubDate", ""),
                    "source": summary.get("Source", "")
                })
        
        result = {"count": count, "papers": papers}
        
        # 4. Save to Cache
        if use_cache:
            try:
                with sqlitedict.SqliteDict(CACHE_FILE, autocommit=True) as cache:
                    cache[query] = result
            except Exception:
                pass
                
        return result
        
    except Exception as e:
        print(f"PubMed API Error for '{query}': {e}")
        return empty_result


def compute_literature_score(drug_name: str, disease_name: str, 
                             max_papers: int = 50, use_cache: bool = True) -> float:
    """Compute normalized literature score [0, 1].
    
    Args:
        drug_name: Name of the drug.
        disease_name: Name of the disease.
        max_papers: Cap the count at this number for normalization.
        use_cache: Whether to use SQLite caching.
        
    Returns:
        Normalized score [0.0, 1.0].
    """
    data = get_pubmed_data(drug_name, disease_name, use_cache=use_cache)
    return min(data["count"] / max_papers, 1.0)
