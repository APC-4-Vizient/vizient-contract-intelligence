"""Synthetic contract bluepine-amendment: Amendment No. 1 to the Statement of Work in contract_bluepine_sow.

Every party, person and number is fictional (Vizient, Inc. aside). The amendment extends the license period and sets one
fee, and deliberately says nothing about data rights, renewal or termination. SPEC is plain data read by
generate_contracts.py; its keys are described there. The signer title "President, Data and Analytics" is exempt from
the forbidden-word check because the Signatories fact requires it; it is a job title, not a statement about data use.
"""

from __future__ import annotations

from typing import Any

TITLE = "AMENDMENT NO. 1 TO STATEMENT OF WORK NO. BP-2025-0417"
AMENDMENT_ID = 'This Amendment No. 1 to Statement of Work No. BP-2025-0417 (this "Amendment")'
OPENING = f'{AMENDMENT_ID} is entered into as of September 2, 2025 (the "Amendment Effective Date")'
VENDOR = ('Bluepine Health Data, Inc., a Delaware corporation with its principal office at 410 Harbor Point Road, '
          'Suite 300, Wilmington, Delaware 19801 ("Provider")')
CLIENT = 'Vizient, Inc., a Delaware corporation with offices in Irving, Texas ("Client")'
PARENT = 'Provider and Client are parties to Statement of Work No. BP-2025-0417 dated January 15, 2025 (the "SOW")'
EXTENSION = ("The Initial License Period stated in Schedule 1 to the SOW is extended so that it runs from "
             "January 15, 2025 through January 14, 2029.")

SPEC: dict[str, Any] = {
    "id": "bluepine-amendment",
    "header_title": "Amendment No. 1 to SOW BP-2025-0417",
    "blocks": [
        ("title", TITLE),
        ("subtitle", "Extension of the License Period and Fee Adjustment"),
        ("p", f'{OPENING} by and between {VENDOR}, and {CLIENT}. Provider and Client are each a "party" and '
              'together the "parties."'),
        ("h1", "Recitals"),
        ("p", f"A. {PARENT}."),
        ("p", "B. Under the SOW, Provider delivers data to Client during the Initial License Period that Schedule 1 "
              "to the SOW states, and Client pays a License Fee for each Annual License Period."),
        ("p", "C. The parties wish to lengthen the Initial License Period by one year, to add a fourth Annual License "
              "Period, to set the License Fee for that period, and to record those changes in this Amendment."),
        ("p", "The parties therefore agree as follows:"),
        ("h1", "1. Defined Terms"),
        ("c", "1.1", "SOW Terms", "Capitalized terms that this Amendment uses but does not define have the meanings "
                                  "given in the SOW."),
        ("d", "1.2", "Fourth Annual License Period", "means the twelve (12) month period from January 15, 2028 "
                                                     "through January 14, 2029."),
        ("h1", "2. Extension of the Initial License Period"),
        ("c", "2.1", "Extended Period", f"{EXTENSION} The Initial License Period is divided into four (4) Annual "
                                        "License Periods."),
        ("c", "2.2", "Fourth Annual License Period", "Schedule 1 to the SOW is amended to add the Fourth Annual "
                                                     "License Period as an additional Annual License Period. Each "
                                                     "reference in the SOW to an Annual License Period includes the "
                                                     "Fourth Annual License Period."),
        ("c", "2.3", "Delivery Date", "Provider shall deliver a fourth Data Release, covering the most recent full "
                                      "calendar year, on or before January 31, 2028. Schedule 1 to the SOW is "
                                      "amended to list that date as the Delivery Date for the fourth Data Release."),
        ("h1", "3. License Fee for the Fourth Annual License Period"),
        ("c", "3.1", "Fee", "The License Fee for the Fourth Annual License Period is $431,600, which is four percent "
                            "(4%) more than the License Fee for the Third Annual License Period. Provider shall "
                            "invoice it on or after January 15, 2028 under Section 5.2 of the SOW."),
        ("c", "3.2", "Fee Schedule", "Schedule 1 to the SOW is amended to add the following line to its list of "
                                     "License Fees: License Fee for the Fourth Annual License Period: $431,600. The "
                                     "total of the License Fees for the Initial License Period, as extended by this "
                                     "Amendment, is $1,631,600, which is $1,200,000 for the first three Annual "
                                     "License Periods plus $431,600 for the fourth."),
        ("c", "3.3", "Earlier Fees", "The License Fees for the First, Second and Third Annual License Periods are "
                                     "not changed by this Amendment."),
        ("h1", "4. Effect of this Amendment"),
        ("c", "4.1", "Other Terms Unchanged", "Except as this Amendment expressly changes it, the SOW is unchanged "
                                              "and remains in full force and effect. If this Amendment conflicts "
                                              "with the SOW on a matter that this Amendment addresses, this "
                                              "Amendment controls."),
        ("c", "4.2", "References", "After the Amendment Effective Date, each reference in the SOW to the SOW means "
                                   "the SOW as amended by this Amendment."),
        ("h1", "5. Governing Law and Notices"),
        ("c", "5.1", "Governing Law", "This Amendment, and any dispute that arises out of or relates to it, is "
                                      "governed by the laws of the State of Delaware, without regard to its "
                                      "conflict-of-laws rules."),
        ("c", "5.2", "Venue", "Each party irrevocably submits to the exclusive jurisdiction and venue of the state "
                              "courts of the State of Delaware sitting in New Castle County for any action that "
                              "arises out of or relates to this Amendment."),
        ("c", "5.3", "Notices", "A notice under this Amendment must be given in writing in the manner that the SOW "
                                "describes, to the address below or to another address that the receiving party "
                                "designates by notice."),
        ("s", "(a)", "Notices to Provider: Bluepine Health Data, Inc., Attention: Contracts Administration, "
                     "410 Harbor Point Road, Suite 300, Wilmington, Delaware 19801."),
        ("s", "(b)", "Notices to Client: Vizient, Inc., Attention: Legal Department, 1500 Corporate Circle, "
                     "Suite 200, Irving, Texas 75038."),
        ("h1", "6. General"),
        ("c", "6.1", "Complete Statement", "This Amendment is part of the SOW. Together they are the complete "
                                           "statement of the parties' agreement on the matters they cover, and this "
                                           "Amendment replaces any earlier discussion of the changes that it makes."),
        ("c", "6.2", "Counterparts", "This Amendment may be signed in counterparts, each of which is an original and "
                                     "all of which together are one agreement. A signature delivered electronically "
                                     "is as effective as an original signature."),
        ("break",),
        ("h1", "Signature Page"),
        ("p", "IN WITNESS WHEREOF, the parties have caused this Amendment to be signed by their authorized "
              "representatives on the dates written below, to take effect as of the Amendment Effective Date."),
        ("signatures",),
    ],
    "signers": [
        ("Provider", "Bluepine Health Data, Inc.", "Maren Okafor", "President, Data and Analytics", "09/09/2025"),
        ("Client", "Vizient, Inc.", "Priya Raman", "Senior Director, Product and Strategy", "09/08/2025"),
    ],
    "details": {
        "Vendor": ("Bluepine Health Data, Inc.", VENDOR),
        "VizientEntity": ("Vizient, Inc.", CLIENT),
        "DocumentType": ("Amendment", TITLE),
        "ContractIdentifier": ("Amendment No. 1 to Statement of Work No. BP-2025-0417", AMENDMENT_ID),
        "EffectiveDate": ("2025-09-02", OPENING),
        "ExpirationDate": ("2029-01-14", EXTENSION),
        "RenewalTermination": ("", ""),
        "Signatories": ("Maren Okafor (President, Data and Analytics, 09/09/2025); "
                        "Priya Raman (Senior Director, Product and Strategy, 09/08/2025)", "Maren Okafor"),
        "ParentAgreementReference": ("Statement of Work No. BP-2025-0417 dated January 15, 2025", PARENT),
    },
    "rights": {
        "Right_InternalAnalytics": ("Not Addressed", ""),
        "Right_AIML": ("Not Addressed", ""),
        "Right_ProductDevelopment": ("Not Addressed", ""),
        "Right_BAARequired": ("Not Addressed", ""),
        "Right_Retention": ("Not Addressed", ""),
        "Right_AffiliateSharing": ("Not Addressed", ""),
        "Right_ThirdPartySharing": ("Not Addressed", ""),
        "Right_DataLinking": ("Not Addressed", ""),
        "Right_DeIdentification": ("Not Addressed", ""),
        "Right_Destruction": ("Not Addressed", ""),
        "Right_Geographic": ("Not Addressed", ""),
    },
    "forbidden": (
        "affiliate", "business associate", "baa", "hipaa", "de-identif", "deidentif", "anonymi", "aggregat",
        "offshore", "united states", "residency", "machine learning", "artificial intelligence", "retain",
        "retention", "destroy", "destruction", "sublicens", "third part", "link", "derivative", "analytics",
        "product development", "renew", "renewal", "terminate", "termination",
    ),
    "exempt": ("president, data and analytics",),
}
