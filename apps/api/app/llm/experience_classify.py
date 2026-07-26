import re

def classify(*, title: str, description: str | None = None) -> str:
    title_lower = title.lower()
    
    # Check title keywords (which are highly predictive of the level)
    # Junior indicators
    junior_keywords = [
        r"\bjunior\b", r"\bjr\b", r"\bintern\b", r"\binternship\b", 
        r"\bgraduate\b", r"\bgrad\b", r"\bentry[- ]level\b", r"\bassociate\b"
    ]
    if any(re.search(kw, title_lower) for kw in junior_keywords):
        return "junior"
        
    # Lead / Manager / Executive indicators
    lead_keywords = [
        r"\blead\b", r"\bmanager\b", r"\bdirector\b", r"\bhead\b", r"\bvp\b", 
        r"\bchief\b", r"\barchitect\b", r"\bprincipal\b"
    ]
    if any(re.search(kw, title_lower) for kw in lead_keywords):
        return "lead"
        
    # Senior indicators
    senior_keywords = [
        r"\bsenior\b", r"\bsr\b", r"\bstaff\b"
    ]
    if any(re.search(kw, title_lower) for kw in senior_keywords):
        return "senior"
        
    # Default fallback
    return "mid"
