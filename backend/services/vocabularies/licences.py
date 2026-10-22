"""
The licences Brubru declares, and the credit it gives its EU sources.

One rule (Victor, 22 Oct 2026): data Brubru gives away without a key is
CC BY 4.0; data served behind a key is under Brubru's own terms (the
"Data licence" section of /terms). The EU's own content inside either
stays under the EU's reuse terms, which is what SOURCE_CREDIT says.

Licences are written as the EU licence authority table's addresses
(the list data.europa.eu's Licensing Assistant shows), because the
portal's quality check scores dct:license only when it is in that list.
"""

# The EU licence authority table's address for CC BY 4.0. Not the
# creativecommons.org page: the portal does not recognise that one.
CC_BY_4_0 = "http://publications.europa.eu/resource/authority/licence/CC_BY_4_0"

# Brubru's own terms for keyed data: the "Data licence" section of the
# Terms of Service. Not in the EU list, so it is described in the
# catalogue as a dct:LicenseDocument with a title.
BRUBRU_DATA_TERMS = "https://brubru.beresol.eu/terms#data-licence"
BRUBRU_DATA_TERMS_TITLE = "Brubru data terms (Beresol BV)"

# Datasets anyone can read without a key. Everything else in
# brubru_dataset_catalog is keyed and takes BRUBRU_DATA_TERMS.
OPEN_DATASETS = {
    "https://brubru.beresol.eu/datasets/catalan-eu-laws",
    "https://brubru.beresol.eu/datasets/europa-source-registry",
}


def licence_for(dcat_uri: str) -> str:
    """The licence a catalogue dataset carries, by the rule above."""
    return CC_BY_4_0 if dcat_uri in OPEN_DATASETS else BRUBRU_DATA_TERMS


# The credit every /api/v1 and /api/v2 response carries (header
# X-Source-Credit). CC BY 4.0 asks for the source and for any change to
# be stated; the Parliament asks for the source and the item's link,
# which each item's public_url gives. ASCII only: it is a header value.
SOURCE_CREDIT = (
    "Contains content of the EU institutions and bodies, (c) European Union, "
    "reused under Commission Decision 2011/833/EU, CC BY 4.0 and each source's "
    "reuse notice. Brubru changed it: structure, classification, summaries and "
    "translations. Each item's public_url links its original; only the Official "
    "Journal is authentic. Terms: " + BRUBRU_DATA_TERMS
)
