# data/external

Downloaded / derived third-party files live here and are **git-ignored** (size and licences:
DrugBank, DisGeNET, DrugCentral). Re-create them with:

    python scripts/fetch_public_data.py --primekg      # PrimeKG kg.csv, MONDO, Hetionet, PharmacotherapyDB, DrugCentral
    python scripts/audit_primekg_mapping.py            # MONDO->DOID audit + corrected WHO NTD list

Optional hand-supplied inputs (see Docs/COLAB_PLAYBOOK.md): daly_burden.csv, who_eml.csv.
