"""scripts/final_audit/pubmed_evidence.py - retrieve PubMed records for the evidence-review candidates (NCBI E-utilities; only drug/disease names are sent).
Records exactly what PubMed returned; classification is done separately and documented in INDEPENDENT_EVIDENCE_VALIDATION.md."""
import json, time, urllib.parse, urllib.request
from pathlib import Path
import pandas as pd
R = Path(__file__).resolve().parents[2] / "reports/final_audit_20261117"
B = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
SYN = {"lupus erythematosus": "lupus", "staphylococcal infection": "staphylococcal", "atopic conjunctivitis": "allergic conjunctivitis", "iridocyclitis (disease)": "iridocyclitis OR uveitis",
       "dermatitis, atopic": "atopic dermatitis", "neurotic disorder": "neurosis OR anxiety", "manic bipolar affective disorder": "mania OR bipolar", "intrinsic asthma": "asthma",
       "streptococcal infection": "streptococcal", "pulmonary emphysema": "emphysema OR COPD", "atopic eczema": "atopic dermatitis OR eczema", "anxiety disorder": "anxiety"}


def get(u, tries=4):
    for k in range(tries):
        try:
            return json.load(urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "research-audit-client/1.0"}), timeout=30))
        except Exception:
            if k == tries - 1:
                raise
            time.sleep(2 * (k + 1))


def main():
    c = pd.read_csv(R / "analysis/evidence_review_candidates.csv")
    out = []
    for r in c.itertuples():
        dis = SYN.get(r.disease_name, r.disease_name)
        term = f'("{r.drug_name}"[tiab]) AND ({" OR ".join(f"{x.strip()}[tiab]" for x in dis.split(" OR "))})'
        s = get(B + "esearch.fcgi?" + urllib.parse.urlencode({"db": "pubmed", "term": term, "retmax": 3, "sort": "relevance", "retmode": "json"}))["esearchresult"]
        ids = s.get("idlist", [])
        time.sleep(0.4)
        hits = []
        if ids:
            sm = get(B + "esummary.fcgi?" + urllib.parse.urlencode({"db": "pubmed", "id": ",".join(ids), "retmode": "json"}))["result"]
            time.sleep(0.4)
            hits = [{"pmid": i, "title": sm[i].get("title"), "pubdate": sm[i].get("pubdate"), "journal": sm[i].get("source"), "pubtype": sm[i].get("pubtype")} for i in ids if i in sm]
        out.append({"drug": r.drug_name, "drug_id": r.drug_id, "disease": r.disease_name, "disease_id": r.disease_id, "ranking_score": r.ranking_score,
                    "rank_within_drug": r.rank_within_drug_all_diseases, "pubmed_query": term, "pubmed_count": int(s.get("count", 0)), "top_hits": hits})
        print(f"{r.drug_name[:22]:22s} | {r.disease_name[:28]:28s} | n={s.get('count')} | " + " || ".join(f"{h['pmid']} {h['pubdate'][:4]} {h['title'][:80]}" for h in hits))
    (R / "evidence").mkdir(exist_ok=True)
    (R / "evidence/pubmed_retrieval.json").write_text(json.dumps({"retrieved_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                                                                  "source": "NCBI PubMed E-utilities (esearch, relevance sort; esummary)", "results": out}, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
