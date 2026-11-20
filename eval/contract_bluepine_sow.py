"""Synthetic contract bluepine-sow: Statement of Work for the license of healthcare utilization data.

Every party, person, address and number is fictional (Vizient, Inc. aside). SPEC is plain data read by
generate_contracts.py; its keys are described there. The text says nothing about affiliate sharing, de-identification,
geography or a Business Associate Agreement, so those four rights are Not Addressed. It does contain the Delaware
governing-law, venue and notice-address clauses, which must never be read as data-residency or sharing terms.
"""

from __future__ import annotations

from typing import Any

TITLE = "STATEMENT OF WORK NO. BP-2025-0417"
SOW_ID = 'This Statement of Work No. BP-2025-0417 (this "SOW")'
OPENING = f'{SOW_ID} is entered into as of January 15, 2025 (the "Effective Date")'
VENDOR = ('Bluepine Health Data, Inc., a Delaware corporation with its principal office at 410 Harbor Point Road, '
          'Suite 300, Wilmington, Delaware 19801 ("Provider")')
CLIENT = 'Vizient, Inc., a Delaware corporation with offices in Irving, Texas ("Client")'
PARENT = ('This SOW is issued under, and is governed by, Master Data License Agreement No. 70418822 dated '
          'March 3, 2021 (the "Master Agreement"), between Provider and Client.')
PERIOD = "Initial License Period: January 15, 2025 through January 14, 2028"
TERMINATION = ("Client may terminate this SOW for convenience effective at the end of any Annual License Period by "
               "giving Provider at least sixty (60) days' prior written notice; fees paid are non-refundable. This "
               "SOW does not renew automatically; any renewal requires a written amendment signed by both parties.")
ANALYTICS = ("Client may use the Licensed Data for its internal analytics, reporting and benchmarking for its own "
             "direct benefit.")
AIML = ("Client shall not use the Licensed Data to train, fine-tune or validate any machine learning or artificial "
        "intelligence model.")
PRODUCTS = ("Client may incorporate analytical outputs derived from the Licensed Data into Client's commercial "
            "products and services only with Provider's prior written consent, which shall not be unreasonably "
            "withheld.")
RETENTION = ("Client's right to use the Licensed Data continues for twelve (12) months after the final delivery of "
             "Licensed Data under this SOW, after which Client shall cease all use of the Licensed Data. Client may "
             "keep one (1) archival copy of the Licensed Data solely for audit and legal-compliance purposes.")
THIRD_PARTY = "Client shall not sell, license, distribute or disclose the Licensed Data to any third party."
LINKING = ("Client may link the Licensed Data to its own datasets provided it does not append Provider's record "
           "identifiers to any data supplied by a third party and does not attempt to identify any individual.")
DESTRUCTION = ("Within thirty (30) days after expiration or termination of this SOW, Client shall destroy all "
               "Licensed Data and certify the destruction in writing, except for the one (1) archival copy "
               "described in Section 9.1.")

SPEC: dict[str, Any] = {
    "id": "bluepine-sow",
    "header_title": "Statement of Work BP-2025-0417",
    "blocks": [
        ("title", TITLE),
        ("subtitle", "License of Healthcare Utilization Data"),
        ("p", f'{OPENING} by and between {VENDOR}, and {CLIENT}. Provider and Client are each a "party" and '
              'together the "parties."'),
        ("p", PARENT),
        ("h1", "Recitals"),
        ("p", "A. Provider compiles healthcare utilization data from the facilities that report to it and licenses "
              "that data to health care organizations for their own analysis."),
        ("p", "B. Client wishes to receive a license to the data that Schedule 1 describes, for the license period "
              "and on the terms that this SOW states."),
        ("p", "C. Provider and Client have agreed that the Master Agreement will govern their relationship in "
              "general and that this SOW will set out the data, the license period and the fees."),
        ("p", "The parties therefore agree as follows:"),

        ("h1", "1. Definitions"),
        ("p", "In this SOW the following terms have the meanings given below. Other capitalized terms are defined "
              "where they first appear."),
        ("d", "1.1", "Annual License Period", "means each of the consecutive twelve (12) month periods into which "
                                              "Schedule 1 divides the Initial License Period."),
        ("d", "1.2", "Confidential Information", "means non-public information that a party discloses to the other "
                  "party in connection with this SOW and that is marked as confidential or that a reasonable person "
                  "would understand to be confidential, and includes the Licensed Data and the terms of this SOW."),
        ("d", "1.3", "Data Release", "means a delivery of Licensed Data that Provider makes to Client on or before a "
                                     "Delivery Date."),
        ("d", "1.4", "Delivery Date", "means a date that Schedule 1 lists for a Data Release."),
        ("d", "1.5", "Documentation", "means the data dictionary, file layouts and other written descriptions of the "
                                      "Licensed Data that Provider supplies, including the summary in Schedule 1."),
        ("d", "1.6", "Initial License Period", "means the period that Schedule 1 states, which begins on the "
                                               "Effective Date."),
        ("d", "1.7", "License Fee", "means the fee that Schedule 1 states for an Annual License Period."),
        ("d", "1.8", "License Period", "means the Initial License Period or, if this SOW is terminated, the part of "
                                       "the Initial License Period that ends on the effective date of termination."),
        ("d", "1.9", "Licensed Data", "means the healthcare utilization data that Provider delivers to Client in the "
                  "Data Releases, as Schedule 1 describes it, together with any correction or replacement that "
                  "Provider delivers for it."),

        ("h1", "2. Scope and Delivery"),
        ("c", "2.1", "Scope", "Provider shall deliver the Licensed Data to Client, and Client shall pay the License "
                              "Fees, in each case as this SOW provides."),
        ("c", "2.2", "Data Releases", "Provider shall deliver one Data Release for each Annual License Period on or "
                  "before the Delivery Date that Schedule 1 lists for it. Each Data Release shall cover the most "
                  "recent full calendar year for which Provider has completed its compilation of the data."),
        ("c", "2.3", "Method of Delivery", "Provider shall deliver each Data Release by secure file transfer to the "
                  "account that Client designates in writing, in the file layout that the Documentation describes. "
                  "Provider shall send Client a delivery confirmation that lists the files, their sizes and their "
                  "checksums."),
        ("c", "2.4", "Review of a Data Release", "Client has thirty (30) days after it receives a Data Release (the "
                  "\"Review Period\") to check that the Data Release conforms to the Documentation. If it does not, "
                  "Client shall notify Provider in writing during the Review Period and describe the nonconformity "
                  "in reasonable detail. If Client gives no notice during the Review Period, the Data Release is "
                  "accepted."),
        ("c", "2.5", "Correction", "Provider shall correct a nonconformity that Client reports under Section 2.4 by "
                  "delivering a corrected Data Release within fifteen (15) days after it receives Client's notice. "
                  "The Review Period applies again to the corrected Data Release."),
        ("c", "2.6", "Subcontractors", "Provider may use subcontractors to compile or deliver the Licensed Data. "
                  "Provider remains responsible for the performance of its subcontractors and shall ensure that each "
                  "of them is bound by duties of confidentiality at least as protective as those in Article 7."),
        ("c", "2.7", "Relationship Managers", "Each party shall name a relationship manager who is responsible for "
                  "the day-to-day administration of this SOW and who is that party's first contact for questions "
                  "about it. A party may replace its relationship manager by notice to the other party."),
        ("c", "2.8", "Client Cooperation", "Client shall give Provider the account information and the access that "
                  "Provider reasonably needs to make each delivery, and shall tell Provider promptly if an account "
                  "changes."),
        ("c", "2.9", "Changes", "A change to the scope of this SOW, to a Delivery Date or to a License Fee is "
                                "effective only if it is stated in a written amendment that both parties sign."),
        ("c", "2.10", "Late Delivery", "If Provider expects to miss a Delivery Date, it shall tell Client promptly, "
                  "explain the reason and give a revised delivery date, and it shall deliver the Data Release as "
                  "soon as it reasonably can. A late delivery does not change the Annual License Period to which "
                  "the Data Release relates."),
        ("c", "2.11", "Business Reviews", "The relationship managers shall meet once in each calendar quarter, in "
                  "person or by video conference, to review delivery performance, support requests and any planned "
                  "change to the Licensed Data or its Documentation."),
        ("c", "2.12", "Sample File", "Before the first Data Release, Provider shall deliver a sample file of not more "
                  "than ten thousand (10,000) records so that Client can test its systems. The sample file is "
                  "Licensed Data and is subject to every term of this SOW that applies to Licensed Data."),
        ("c", "2.13", "Documentation Updates", "Provider shall update the Documentation whenever it changes a file "
                  "layout or a field definition, and shall deliver the updated Documentation with the next Data "
                  "Release."),
        ("c", "2.14", "Completeness", "Provider shall use commercially reasonable efforts to include in each Data "
                  "Release all of the records that it has compiled for the period the Data Release covers, other than "
                  "records that law or an agreement with a reporting facility requires Provider to leave out."),
        ("c", "2.15", "Record Counts", "Each delivery confirmation shall state the number of records in each file. "
                  "If the number of records differs by more than five percent (5%) from the number in the prior Data "
                  "Release, Provider shall explain the difference in writing."),
        ("c", "2.16", "Errors Found by Provider", "If Provider finds an error in a Data Release after delivering it, "
                  "Provider shall tell Client promptly and shall deliver a corrected Data Release within fifteen (15) "
                  "days after it finds the error. Section 2.4 applies to the corrected Data Release."),
        ("c", "2.17", "Delivery Notices", "Provider shall send each delivery confirmation to Client's relationship "
                  "manager, and Client shall send each notice of nonconformity to Provider's relationship manager."),

        ("h1", "3. License Grant"),
        ("c", "3.1", "License", "Provider grants Client a non-exclusive, non-transferable and non-sublicensable "
                  "license to receive the Licensed Data during the License Period and to use it for the periods and "
                  "purposes that this SOW permits."),
        ("c", "3.2", "Internal Analytics", ANALYTICS),
        ("c", "3.3", "Use in Client Products", PRODUCTS),
        ("c", "3.4", "Requests for Consent", "Client shall make a request for consent under Section 3.3 in writing "
                  "and shall describe the analytical outputs and the products or services in which Client proposes "
                  "to use them. Provider shall respond within fifteen (15) business days after it receives the "
                  "request."),
        ("c", "3.5", "Ownership", "Provider and its licensors own the Licensed Data and all intellectual property "
                  "rights in it. Client acquires only the license that this SOW expressly grants."),
        ("c", "3.6", "Client Materials", "Client owns its own datasets, and it owns the analyses, reports and "
                  "benchmarks that it prepares for its internal use under Section 3.2, subject to Provider's "
                  "ownership of the Licensed Data that they contain."),
        ("c", "3.7", "Suggestions", "If Client gives Provider a suggestion about the Licensed Data or the "
                  "Documentation, Provider may use the suggestion without obligation to Client."),
        ("c", "3.8", "Responsibility for Employees", "Client is responsible for the compliance of its employees "
                  "with this SOW. Before an employee first uses the Licensed Data, Client shall tell the employee "
                  "about the restrictions in Article 4."),

        ("h1", "4. Use Restrictions"),
        ("c", "4.1", "Models", AIML),
        ("c", "4.2", "Third Parties", THIRD_PARTY),
        ("c", "4.3", "Linking", LINKING),
        ("c", "4.4", "Other Restrictions", "Client shall not (a) remove or change any proprietary notice that appears "
                  "on the Licensed Data or the Documentation, (b) circumvent any technical measure that Provider uses "
                  "to control access to a Data Release, (c) reverse engineer or try to discover the methods that "
                  "Provider uses to compile the Licensed Data, or (d) use the Licensed Data in a way that violates "
                  "applicable law."),
        ("c", "4.5", "Compliance Certification", "Once in each Annual License Period, Provider may ask Client in "
                  "writing to certify that it is using the Licensed Data in accordance with this SOW. Client shall "
                  "deliver the certification, signed by an officer of Client, within thirty (30) days after it "
                  "receives the request."),
        ("c", "4.6", "Notice of Misuse", "Client shall notify Provider promptly if it learns of any use of the "
                  "Licensed Data that this SOW does not permit, and shall take reasonable steps to stop it."),

        ("h1", "5. Fees and Payment"),
        ("c", "5.1", "License Fees", "Client shall pay Provider the License Fee for each Annual License Period, in "
                  "the amount that Schedule 1 states. The License Fees are the only amounts that Client owes for the "
                  "Licensed Data unless the parties agree otherwise in a written amendment."),
        ("c", "5.2", "Invoicing", "Provider shall invoice each License Fee on or after the first day of the Annual "
                  "License Period to which it relates. Each invoice shall state the number of this SOW, the Annual "
                  "License Period and the amount due, and shall show any tax separately."),
        ("c", "5.3", "Payment", "Client shall pay each undisputed invoice within forty-five (45) days after it "
                  "receives the invoice. Client shall pay in dollars, by electronic funds transfer to the account "
                  "that Provider designates in writing."),
        ("c", "5.4", "Disputed Amounts", "If Client disputes part of an invoice in good faith, it shall pay the "
                  "undisputed part when due and shall notify Provider of the dispute, and its basis, within thirty "
                  "(30) days after it receives the invoice. The parties shall work in good faith to resolve the "
                  "dispute promptly, and Client shall pay any amount that is resolved in Provider's favor within "
                  "fifteen (15) days after the resolution."),
        ("c", "5.5", "Late Payment", "An undisputed amount that remains unpaid after its due date bears interest "
                  "from the due date until it is paid, at one percent (1%) per month or at the highest rate that law "
                  "allows if that rate is lower."),
        ("c", "5.6", "Suspension for Non-Payment", "If an undisputed amount is more than sixty (60) days past due "
                  "and Provider has given Client written notice of the non-payment, Provider may suspend further "
                  "deliveries until Client pays the amount in full. A suspension does not extend the License Period."),

        ("h1", "6. Taxes"),
        ("c", "6.1", "Responsibility", "The License Fees do not include sales, use, value added, excise or similar "
                  "taxes that a government imposes on the license or on Client's receipt of the Licensed Data. Client "
                  "shall pay those taxes, other than taxes on Provider's income, property, employees or franchise, "
                  "which Provider shall pay."),
        ("c", "6.2", "Exemption", "If Client is exempt from a tax, Client shall give Provider a valid exemption "
                  "certificate before the invoice date, and Provider shall not charge that tax on later invoices."),
        ("c", "6.3", "Withholding", "If law requires Client to withhold tax from a payment, Client shall withhold "
                  "the tax, pay it to the proper authority when due, and give Provider an official receipt. The "
                  "withheld amount is treated as paid to Provider."),
        ("c", "6.4", "Cooperation", "The parties shall cooperate in good faith to lawfully minimize any tax that "
                  "applies to the transactions under this SOW, and each shall give the other the information that it "
                  "reasonably needs for that purpose."),

        ("h1", "7. Confidentiality"),
        ("c", "7.1", "Obligations", "Each party, as a recipient of the other party's Confidential Information, shall "
                  "(a) use it only to perform its obligations and exercise its rights under this SOW, (b) protect it "
                  "with at least the care that the recipient uses to protect its own information of a similar kind, "
                  "and never less than reasonable care, and (c) not disclose it except as Section 7.3 permits."),
        ("c", "7.2", "Exclusions", "Section 7.1 does not apply to information that the recipient can show (a) is or "
                  "becomes public without the recipient's breach, (b) was known to the recipient without a duty of "
                  "confidence before the other party disclosed it, (c) the recipient received from a third party "
                  "that was free to disclose it, or (d) the recipient developed independently without using the "
                  "other party's Confidential Information. Information is not within these exclusions merely "
                  "because individual elements of it are public."),
        ("c", "7.3", "Permitted Disclosures", "A recipient may disclose the other party's Confidential Information "
                  "(a) to its employees and professional advisors who need to know it for the purposes of this SOW "
                  "and who are bound by duties of confidentiality at least as protective as this Article 7, and "
                  "(b) to the extent that law, regulation or a court order requires, after giving the other party "
                  "prompt written notice where the law allows it. This Section 7.3 does not permit the disclosure "
                  "of the Licensed Data, which Section 4.2 governs."),
        ("c", "7.4", "Duration", "The obligations in this Article 7 continue for five (5) years after this SOW "
                  "expires or is terminated, except that they continue for as long as a trade secret remains a "
                  "trade secret under applicable law and, for the Licensed Data, for as long as Client has any of "
                  "it."),
        ("c", "7.5", "Equitable Relief", "Each party acknowledges that a breach of this Article 7 may cause harm for "
                  "which money is not an adequate remedy. The other party may therefore seek an injunction or other "
                  "equitable relief, without posting a bond to the extent that law allows, in addition to its other "
                  "remedies."),

        ("h1", "8. Security"),
        ("c", "8.1", "Safeguards", "Each party shall maintain administrative, technical and physical safeguards that "
                  "are appropriate to the sensitivity of the Licensed Data and that meet or exceed generally "
                  "accepted industry practice for the protection of information of this kind."),
        ("c", "8.2", "Provider Controls", "Provider shall protect each Data Release during transfer with encryption "
                  "that is generally accepted in the industry, shall scan each Data Release for malicious code "
                  "before it delivers the Data Release, and shall keep the credentials that it issues to Client "
                  "secure."),
        ("c", "8.3", "Client Controls", "Client shall limit access to the Licensed Data to its employees who need it "
                  "for the uses that this SOW permits, shall protect the Licensed Data with access controls and "
                  "encryption that are generally accepted in the industry, and shall keep a current list of the "
                  "employees who have access."),
        ("c", "8.4", "Security Incidents", "A party that learns of unauthorized access to, or unauthorized "
                  "acquisition of, the Licensed Data shall notify the other party without undue delay and in any "
                  "event within seventy-two (72) hours. The notifying party shall investigate the incident, take "
                  "reasonable steps to stop it and prevent its recurrence, and keep the other party informed of its "
                  "progress."),
        ("c", "8.5", "Security Assessments", "Once in each Annual License Period, Provider shall give Client, on "
                  "Client's written request, a summary of the results of Provider's most recent independent "
                  "security assessment and a description of the steps that it has taken to correct any significant "
                  "finding."),
        ("c", "8.6", "Business Continuity", "Provider shall maintain a written business continuity plan for the "
                  "systems that it uses to compile and deliver the Licensed Data, shall test the plan at least once "
                  "each year, and shall give Client a summary of the plan on request."),
        ("c", "8.7", "Credentials", "Client shall protect the credentials that Provider issues for the file transfer "
                  "service, shall not share them with any other person, and shall tell Provider promptly if they "
                  "are lost or may have been compromised."),
        ("c", "8.8", "Security Questionnaire", "Once in each Annual License Period, Client may send Provider a "
                  "written questionnaire about the controls that protect the Licensed Data while Provider compiles "
                  "and delivers it. Provider shall complete the questionnaire accurately within thirty (30) days "
                  "after it receives it."),

        ("h1", "9. Retention and Destruction"),
        ("c", "9.1", "Period of Use and Archival Copy", RETENTION),
        ("c", "9.2", "Destruction", DESTRUCTION),
        ("c", "9.3", "Certificate of Destruction", "The written certification that Section 9.2 requires shall "
                  "identify the Licensed Data that Client destroyed and the date and method of destruction, and an "
                  "officer of Client shall sign it. Client shall deliver the certification to Provider within the "
                  "time that Section 9.2 states."),
        ("c", "9.4", "Care of the Archival Copy", "Client shall keep the archival copy described in Section 9.1 in a "
                  "repository with restricted access, shall not use it for any purpose other than audit and legal "
                  "compliance, and shall continue to protect it under Article 8 for as long as Client has it."),
        ("c", "9.5", "Effect on Other Terms", "Nothing in this Article 9 extends the License Period or Client's "
                  "obligation to pay License Fees, and nothing in it limits Provider's rights under Article 4."),

        ("h1", "10. Warranties and Disclaimers"),
        ("c", "10.1", "Mutual Warranties", "Each party represents and warrants that it is duly organized and in good "
                  "standing, that it has the power and authority to enter into and perform this SOW, and that doing "
                  "so does not breach any agreement that binds it."),
        ("c", "10.2", "Provider Warranties", "Provider represents and warrants that (a) it has the right to license "
                  "the Licensed Data to Client as this SOW provides, (b) each Data Release will conform in all "
                  "material respects to the Documentation when delivered, and (c) it will perform its obligations "
                  "under this SOW in a professional manner that is consistent with generally accepted industry "
                  "standards."),
        ("c", "10.3", "Remedy for Nonconformity", "If a Data Release does not conform to the warranty in Section "
                  "10.2(b), Provider shall correct it or deliver a replacement as Section 2.5 provides. Correction "
                  "or replacement is Client's sole remedy for the nonconformity, but this Section 10.3 does not "
                  "limit Provider's obligations under Article 11."),
        ("c", "10.4", "Disclaimer", "EXCEPT AS THIS ARTICLE 10 EXPRESSLY STATES, PROVIDER MAKES NO WARRANTY ABOUT THE "
                  "LICENSED DATA OR THE DOCUMENTATION, WHETHER EXPRESS, IMPLIED OR STATUTORY, AND DISCLAIMS ALL "
                  "IMPLIED WARRANTIES, INCLUDING THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A "
                  "PARTICULAR PURPOSE. PROVIDER DOES NOT WARRANT THAT THE LICENSED DATA IS COMPLETE OR FREE FROM "
                  "ERRORS OR THAT CLIENT'S USE OF IT WILL BE UNINTERRUPTED."),
        ("c", "10.5", "Client Acknowledgment", "Client acknowledges that Provider compiles the Licensed Data from "
                  "information that others report to it, and that Client is responsible for the conclusions that it "
                  "draws from the Licensed Data and for the decisions that it makes in reliance on them."),
        ("c", "10.6", "Compliance with Laws", "Each party shall comply with the laws and regulations that apply to "
                  "its own performance of this SOW and to its own use of the Licensed Data."),
        ("c", "10.7", "Changes to Methods", "Provider may change the methods that it uses to compile the Licensed "
                  "Data if the change does not materially reduce the content or quality of the Licensed Data. "
                  "Provider shall tell Client about a material change at least thirty (30) days before the Data "
                  "Release in which the change first appears."),

        ("h1", "11. Indemnification"),
        ("c", "11.1", "By Provider", "Provider shall defend Client against any claim that a third party brings "
                  "alleging that Client's use of the Licensed Data, as this SOW permits, infringes that third "
                  "party's copyright, trade secret or other intellectual property right, and shall pay the losses, "
                  "costs and expenses, including reasonable attorneys' fees, that a court finally awards against "
                  "Client or that Provider agrees to pay in a settlement of the claim."),
        ("c", "11.2", "By Client", "Client shall defend Provider against any claim that a third party brings arising "
                  "from Client's use of the Licensed Data in breach of this SOW, and shall pay the losses, costs "
                  "and expenses, including reasonable attorneys' fees, that a court finally awards against Provider "
                  "or that Client agrees to pay in a settlement of the claim."),
        ("c", "11.3", "Procedure", "A party seeking indemnification shall give the other party prompt written notice "
                  "of the claim, allow the indemnifying party to control its defense and settlement, and cooperate "
                  "reasonably at the indemnifying party's expense. The indemnifying party shall not settle a claim "
                  "in a way that imposes an obligation on the indemnified party without the indemnified party's "
                  "written consent, which shall not be unreasonably withheld. A delay in giving notice relieves the "
                  "indemnifying party only to the extent that the delay prejudices its defense."),
        ("c", "11.4", "Exclusions", "Provider has no obligation under Section 11.1 to the extent that the claim "
                  "arises from Client's modification of the Licensed Data, from Client's use of the Licensed Data "
                  "together with materials that Provider did not supply, or from Client's use of the Licensed Data "
                  "in breach of this SOW."),
        ("c", "11.5", "Mitigation", "If a claim of the kind that Section 11.1 describes is made or appears likely, "
                  "Provider may, at its own expense, procure for Client the right to keep using the affected "
                  "Licensed Data, or modify or replace the affected Licensed Data so that it no longer infringes "
                  "while it keeps substantially the same function."),

        ("h1", "12. Limitation of Liability"),
        ("c", "12.1", "Excluded Loss", "NEITHER PARTY IS LIABLE TO THE OTHER FOR ANY INDIRECT, INCIDENTAL, SPECIAL, "
                  "CONSEQUENTIAL OR PUNITIVE LOSS, OR FOR LOST PROFITS, LOST REVENUE OR LOST BUSINESS "
                  "OPPORTUNITY, ARISING OUT OF OR RELATING TO THIS SOW, EVEN IF THAT PARTY HAS BEEN ADVISED OF THE "
                  "POSSIBILITY OF THE LOSS."),
        ("c", "12.2", "Liability Cap", "EACH PARTY'S TOTAL LIABILITY ARISING OUT OF OR RELATING TO THIS SOW IS "
                  "LIMITED TO THE LICENSE FEES THAT CLIENT HAS PAID OR OWES FOR THE ANNUAL LICENSE PERIOD IN WHICH "
                  "THE EVENT THAT GAVE RISE TO THE LIABILITY OCCURRED."),
        ("c", "12.3", "Exceptions", "Sections 12.1 and 12.2 do not apply to a party's obligations under Article 11, "
                  "to a breach of Article 7, to Client's use of the Licensed Data in breach of Article 4, to a "
                  "party's willful misconduct or gross negligence, or to any liability that applicable law does not "
                  "allow a party to limit."),
        ("c", "12.4", "Basis of the Bargain", "The parties have set the License Fees in reliance on the limits in "
                  "this Article 12. Those limits apply however a claim arises, whether in contract, tort or "
                  "otherwise, and even if a limited remedy fails of its essential purpose."),

        ("h1", "13. Term and Termination"),
        ("c", "13.1", "Term", "This SOW begins on the Effective Date and, unless it ends earlier under Section 13.2, "
                  "expires on the last day of the Initial License Period that Schedule 1 states."),
        ("c", "13.2", "Termination for Convenience; No Renewal", TERMINATION),
        ("c", "13.3", "Effect of Expiration or Termination", "When this SOW expires or is terminated, Provider's "
                  "obligation to deliver further Data Releases ends, the license in Section 3.1 to receive the "
                  "Licensed Data ends, and Article 9 governs what Client may do with the Licensed Data that it "
                  "already has. Client shall pay all License Fees that fell due before the effective date of the "
                  "expiration or termination."),
        ("c", "13.4", "Survival", "Articles 4, 7, 9, 11 and 12, Section 3.5, and any other term that by its nature is "
                  "meant to continue, survive the expiration or termination of this SOW."),

        ("h1", "14. Relationship to the Master Agreement"),
        ("c", "14.1", "Governing Agreement", "This SOW is issued under the Master Agreement, and the terms of the "
                  "Master Agreement govern this SOW except where this SOW expressly changes them."),
        ("c", "14.2", "Order of Precedence", "If a term of this SOW conflicts with a term of the Master Agreement, "
                  "this SOW controls as to the Licensed Data, the Delivery Dates and the License Fees, and the "
                  "Master Agreement controls as to every other matter. Within this SOW, the numbered Articles "
                  "control over the Schedules."),
        ("c", "14.3", "Other Statements of Work", "This SOW does not change any other statement of work that the "
                  "parties have signed under the Master Agreement, and no other statement of work changes this SOW."),

        ("h1", "15. Governing Law and Venue"),
        ("c", "15.1", "Governing Law", "This SOW, and any dispute that arises out of or relates to it, is governed "
                  "by the laws of the State of Delaware, without regard to its conflict-of-laws rules."),
        ("c", "15.2", "Venue", "Each party irrevocably submits to the exclusive jurisdiction and venue of the state "
                  "courts of the State of Delaware sitting in New Castle County for any action that arises out of or "
                  "relates to this SOW, and waives any objection that the venue is inconvenient."),
        ("c", "15.3", "Escalation", "Before a party starts a court action, other than an action for equitable "
                  "relief, it shall give the other party written notice of the dispute, and the parties' "
                  "relationship managers shall meet, in person or by telephone, within twenty (20) days after the "
                  "notice to try to resolve it."),
        ("c", "15.4", "Jury Waiver", "EACH PARTY WAIVES, TO THE FULLEST EXTENT THAT LAW ALLOWS, ANY RIGHT TO A TRIAL "
                  "BY JURY IN ANY ACTION THAT ARISES OUT OF OR RELATES TO THIS SOW."),

        ("h1", "16. Notices"),
        ("c", "16.1", "Form and Delivery", "A notice under this SOW must be in writing and must be delivered by "
                  "hand, by a nationally recognized overnight courier, or by certified mail with return receipt "
                  "requested, to the address in Section 16.2 or to another address that the receiving party "
                  "designates by notice."),
        ("c", "16.2", "Addresses", "Notices shall be addressed as follows:"),
        ("s", "(a)", "Notices to Provider: Bluepine Health Data, Inc., Attention: Contracts Administration, "
                     "410 Harbor Point Road, Suite 300, Wilmington, Delaware 19801."),
        ("s", "(b)", "Notices to Client: Vizient, Inc., Attention: Legal Department, 1500 Corporate Circle, "
                     "Suite 200, Irving, Texas 75038."),
        ("c", "16.3", "When Effective", "A notice is effective when it is delivered or when the receiving party "
                  "refuses delivery. A notice that a courier delivers is delivered on the date that the courier's "
                  "records show, and a notice sent by certified mail is delivered on the date that the return "
                  "receipt shows."),
        ("c", "16.4", "Routine Communications", "Routine operational communications, such as delivery "
                  "confirmations and support requests, may be sent by e-mail to the contacts that Schedule 2 lists. "
                  "They are not notices under this Article 16."),

        ("h1", "17. General"),
        ("c", "17.1", "Assignment", "Neither party may assign this SOW, or any right or obligation under it, "
                  "without the other party's prior written consent, which the other party shall not unreasonably "
                  "withhold. Either party may, on written notice to the other, assign this SOW to a successor to "
                  "all or substantially all of its business to which this SOW relates. Any other attempted "
                  "assignment is void."),
        ("c", "17.2", "Force Majeure", "Neither party is liable for a delay in performing, or a failure to perform, "
                  "an obligation under this SOW, other than an obligation to pay money, to the extent that an event "
                  "beyond its reasonable control causes the delay or failure, including a natural disaster, fire, "
                  "flood, epidemic, war, act of terrorism, civil unrest, labor dispute, act of government, or "
                  "failure of a public utility or telecommunications network. The affected party shall give the "
                  "other party prompt notice and shall use reasonable efforts to resume performance."),
        ("c", "17.3", "Entire Agreement", "This SOW, together with the Master Agreement, is the entire agreement of "
                  "the parties on its subject matter and replaces all earlier proposals, statements and "
                  "understandings about it."),
        ("c", "17.4", "Amendment and Waiver", "This SOW may be amended only by a written document that both parties "
                  "sign. A failure or delay in enforcing a right is not a waiver of that right, and a waiver is "
                  "effective only if it is in writing and signed by the party that gives it."),
        ("c", "17.5", "Severability", "If a court holds a provision of this SOW to be invalid or unenforceable, the "
                  "provision shall be enforced to the extent that the law allows, and the rest of this SOW remains "
                  "in effect."),
        ("c", "17.6", "Independent Contractors", "The parties are independent contractors. Nothing in this SOW "
                  "creates a partnership, joint venture, agency or employment relationship between them."),
        ("c", "17.7", "Insurance", "During the term of this SOW each party shall maintain commercial general "
                  "liability insurance with limits of at least $2,000,000 per occurrence, and Provider shall also "
                  "maintain cyber liability insurance with limits of at least $5,000,000 per claim. Each party "
                  "shall give the other a certificate of insurance on request."),
        ("c", "17.8", "Publicity", "Neither party shall use the other party's name or marks in a press release, "
                  "advertisement or customer list without the other party's prior written consent."),
        ("c", "17.9", "No Third-Party Beneficiaries", "This SOW creates rights only for the parties and their "
                  "permitted successors and assigns. No other person may enforce it."),
        ("c", "17.10", "Interpretation", "Headings are for convenience only. The word \"including\" means "
                  "including without limitation. Both parties have had the opportunity to review this SOW with "
                  "counsel, and no rule that construes a term against its drafter applies to it."),
        ("c", "17.11", "Cumulative Remedies", "Unless this SOW says that a remedy is exclusive, each right and remedy "
                  "in this SOW is in addition to every other right and remedy that a party has under this SOW or "
                  "under law."),
        ("c", "17.12", "Costs", "Each party bears its own costs of negotiating, signing and performing this SOW, "
                  "except as this SOW expressly provides."),
        ("c", "17.13", "Further Assurances", "Each party shall sign the documents and take the actions that the "
                  "other party reasonably requests to carry out the intent of this SOW."),
        ("c", "17.14", "Equitable Relief", "Each party acknowledges that a breach of Article 4 or Article 7 may cause "
                  "the other party harm for which money is not an adequate remedy, and that the other party may "
                  "therefore ask a court for an injunction or other equitable relief in addition to any other "
                  "remedy that it has."),
        ("c", "17.15", "Authority to Sign", "Each person who signs this SOW for a party represents that he or she is "
                  "authorized to sign it for that party and to bind that party to its terms."),
        ("c", "17.16", "Accrued Rights", "The expiration or termination of this SOW does not affect a right or an "
                  "obligation that accrued before the date of the expiration or termination."),
        ("c", "17.17", "Counterparts", "This SOW may be signed in counterparts, each of which is an original and "
                  "all of which together are one agreement. A signature that is delivered electronically is as "
                  "effective as an original signature."),

        ("break",),
        ("h1", "Schedule 1: Description of Data, License Period and Fees"),
        ("p", "This Schedule 1 is part of the SOW. Capitalized terms have the meanings given in the SOW."),
        ("h2", "Part A. Description of the Licensed Data"),
        ("c", "A.1", "Data Product", "The Licensed Data is the Bluepine Utilization Panel, a collection of "
                  "record-level healthcare utilization data that Provider compiles from the facilities that report "
                  "to it."),
        ("c", "A.2", "Content", "Each record describes one inpatient or outpatient encounter. It carries a record "
                  "identifier that Provider assigns, together with the facility code, service line, diagnosis group, "
                  "procedure group, payer category, calendar quarter, length of stay and charge band for the "
                  "encounter."),
        ("c", "A.3", "Coverage", "The Licensed Data covers encounters at acute care hospitals and ambulatory "
                  "surgery centers that report to Provider, for the calendar year to which a Data Release relates."),
        ("c", "A.4", "Format", "Provider delivers each Data Release as comma-separated text files with a header "
                  "row, encoded in UTF-8, together with a data dictionary that describes each field."),
        ("c", "A.5", "Data Dictionary Summary", "The principal fields are:"),
        ("s", "(a)", "RECORD_ID: the record identifier that Provider assigns to the record."),
        ("s", "(b)", "FACILITY_CODE: Provider's code for the reporting facility."),
        ("s", "(c)", "SERVICE_LINE: the clinical service line, such as cardiology or orthopedics."),
        ("s", "(d)", "DIAGNOSIS_GROUP and PROCEDURE_GROUP: the diagnosis group and the procedure group for the "
                     "encounter."),
        ("s", "(e)", "PAYER_CATEGORY: the category of payer, such as commercial, government or self-pay."),
        ("s", "(f)", "SERVICE_QUARTER: the calendar quarter in which the encounter took place."),
        ("s", "(g)", "LENGTH_OF_STAY: the length of stay in days, which is zero for an outpatient encounter."),
        ("s", "(h)", "CHARGE_BAND: the band that contains the total charge for the encounter."),
        ("h2", "Part B. License Period"),
        ("s", "(a)", f"{PERIOD}."),
        ("s", "(b)", "First Annual License Period: January 15, 2025 through January 14, 2026."),
        ("s", "(c)", "Second Annual License Period: January 15, 2026 through January 14, 2027."),
        ("s", "(d)", "Third Annual License Period: January 15, 2027 through January 14, 2028."),
        ("h2", "Part C. Delivery Dates"),
        ("s", "(a)", "First Data Release: on or before January 31, 2025."),
        ("s", "(b)", "Second Data Release: on or before January 31, 2026."),
        ("s", "(c)", "Third Data Release: on or before January 31, 2027."),
        ("h2", "Part D. License Fees"),
        ("s", "(a)", "License Fee for the First Annual License Period: $385,000."),
        ("s", "(b)", "License Fee for the Second Annual License Period: $400,000."),
        ("s", "(c)", "License Fee for the Third Annual License Period: $415,000."),
        ("s", "(d)", "Total of the License Fees for the Initial License Period: $1,200,000."),
        ("p", "Provider invoices each License Fee under Section 5.2, and Client pays it under Section 5.3."),
        ("h2", "Part E. Billing Contacts"),
        ("s", "(a)", "Invoices to Client: Vizient, Inc., Attention: Accounts Payable, 1500 Corporate Circle, "
                     "Suite 200, Irving, Texas 75038."),
        ("s", "(b)", "Payments to Provider: by electronic funds transfer to the account that Provider's invoice "
                     "identifies, with the invoice number in the payment reference."),

        ("h1", "Schedule 2: Delivery and Support Terms"),
        ("p", "This Schedule 2 is part of the SOW. Capitalized terms have the meanings given in the SOW."),
        ("s", "(a)", "Delivery method: Provider delivers each Data Release by secure file transfer to the account "
                     "that Client designates in writing under Section 2.3. Each delivery includes a manifest that "
                     "lists every file with its size and checksum."),
        ("s", "(b)", "Support hours: Provider's data operations desk answers Client's support requests on business "
                     "days from 8:00 a.m. to 6:00 p.m. Central Time."),
        ("s", "(c)", "Response targets: Provider shall acknowledge a request that reports a Data Release that cannot "
                     "be opened or read within four (4) business hours, a request that reports a significant "
                     "nonconformity within one (1) business day, and any other request within three (3) business "
                     "days."),
        ("s", "(d)", "Support contacts: Provider's data operations desk can be reached at dataops@bluepine.example, "
                     "and Client's relationship manager can be reached at datalicensing@vizient.example."),
        ("s", "(e)", "Escalation: If Provider does not meet a response target, Client may escalate the request to "
                     "Provider's relationship manager and then to Provider's Vice President of Data Operations."),
        ("s", "(f)", "Maintenance: Provider shall give Client at least five (5) business days' notice of planned "
                     "maintenance that will make the file transfer service unavailable for more than four (4) "
                     "hours."),
        ("s", "(g)", "Quality measures: Provider shall aim for at least ninety-five percent (95%) of the records in "
                     "each Data Release to have a value in every field that the data dictionary summary in "
                     "Schedule 1 lists, and for no record identifier to appear more than once in the same Data "
                     "Release."),
        ("s", "(h)", "Quarterly report: Within ten (10) business days after the end of each calendar quarter, "
                     "Provider shall send Client a short report that lists Client's support requests during the "
                     "quarter and Provider's response times."),

        ("break",),
        ("h1", "Signature Page"),
        ("p", "IN WITNESS WHEREOF, the parties have caused this SOW to be signed by their authorized "
              "representatives on the dates written below, to take effect as of the Effective Date."),
        ("signatures",),
    ],
    "signers": [
        ("Provider", "Bluepine Health Data, Inc.", "Maren Okafor", "President, Data and Analytics", "01/22/2025"),
        ("Client", "Vizient, Inc.", "Tobias Lindqvist", "Vice President and General Manager", "01/21/2025"),
    ],
    "details": {
        "Vendor": ("Bluepine Health Data, Inc.", VENDOR),
        "VizientEntity": ("Vizient, Inc.", CLIENT),
        "DocumentType": ("SOW", TITLE),
        "ContractIdentifier": ("Statement of Work No. BP-2025-0417", SOW_ID),
        "EffectiveDate": ("2025-01-15", OPENING),
        "ExpirationDate": ("2028-01-14", PERIOD),
        "RenewalTermination": ("Client may terminate at the end of any Annual License Period on at least 60 days' "
                               "written notice; no refund of fees paid; no automatic renewal", TERMINATION),
        "Signatories": ("Maren Okafor (President, Data and Analytics, 01/22/2025); Tobias Lindqvist (Vice President "
                        "and General Manager, 01/21/2025)", "Maren Okafor"),
        "ParentAgreementReference": ("Master Data License Agreement No. 70418822 dated March 3, 2021", PARENT),
    },
    "rights": {
        "Right_InternalAnalytics": ("Permitted", ANALYTICS),
        "Right_AIML": ("Prohibited", AIML),
        "Right_ProductDevelopment": ("Conditional", PRODUCTS),
        "Right_BAARequired": ("Not Addressed", ""),
        "Right_Retention": ("Conditional", RETENTION),
        "Right_AffiliateSharing": ("Not Addressed", ""),
        "Right_ThirdPartySharing": ("Prohibited", THIRD_PARTY),
        "Right_DataLinking": ("Conditional", LINKING),
        "Right_DeIdentification": ("Not Addressed", ""),
        "Right_Destruction": ("Conditional", DESTRUCTION),
        "Right_Geographic": ("Not Addressed", ""),
    },
    "forbidden": (
        "affiliate", "business associate", "baa", "hipaa", "de-identif", "deidentif", "anonymi", "aggregat",
        "offshore", "united states", "outside of", "residency", "data center", "foreign", "overseas",
    ),
    "exempt": (),
}
