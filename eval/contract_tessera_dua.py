"""Synthetic contract tessera-dua: Data Use Agreement for a clinical research registry extract.

Every party, person, address and number is fictional (Vizient, Inc. aside). SPEC is plain data read by
generate_contracts.py; its keys are described there. The Vizient-side party is Meridian Care Analytics, LLC, a
subsidiary. The text never mentions product development, so that right is Not Addressed, and the contract refers to no
other numbered or dated agreement. It does contain the Delaware governing-law, venue and notice-address clauses, which
must never be read as data-residency or sharing terms.
"""

from __future__ import annotations

from typing import Any

TITLE = "DATA USE AGREEMENT NO. TCR-DUA-2025-118"
DUA_ID = 'This Data Use Agreement No. TCR-DUA-2025-118 (this "Agreement")'
OPENING = f'{DUA_ID} is entered into as of April 1, 2025 (the "Effective Date")'
VENDOR = ('Tessera Clinical Research Analytics, LLC, a Delaware limited liability company with its principal office '
          'at 88 Meadowlark Lane, Suite 12, Cambridge, Massachusetts 02139 ("Provider")')
CLIENT = 'Meridian Care Analytics, LLC, a Texas limited liability company with offices in Irving, Texas ("Client")'
INITIAL_TERM = ('The initial term of this Agreement is two (2) years, beginning on the Effective Date and ending on '
                'March 31, 2027 (the "Initial Term").')
TERMINATION = ("This Agreement renews automatically for successive one-year terms unless either party gives at least "
               "ninety (90) days' written non-renewal notice. Either party may terminate for uncured material breach "
               "after thirty (30) days' notice; Client may terminate for convenience on thirty (30) days' notice.")
ANALYTICS = "Client may use the Licensed Data for its internal research, reporting, benchmarking and analytics."
AIML = ("Client may use the Licensed Data to develop, train and validate machine learning models solely within "
        "Client's secure environment, provided that no Licensed Data and no model that embodies Licensed Data is "
        "disclosed outside Client without Provider's prior written approval.")
BAA = ("Before Provider delivers any Protected Health Information to Client, the parties shall enter into a "
       "Business Associate Agreement.")
RETENTION = ("Client may retain the Licensed Data during the Term, and shall retain audit logs of all access to the "
             "Licensed Data for six (6) years.")
AFFILIATES = ("Client may share the Licensed Data with its wholly owned Affiliates that have agreed in writing to be "
              "bound by this Agreement.")
THIRD_PARTY = ("Client shall not disclose, sell, sublicense or otherwise make the Licensed Data available to any "
               "third party.")
LINKING = "Client shall not link, merge or combine the Licensed Data with any other dataset or data source."
DEIDENTIFY = ("Client may de-identify, anonymize or aggregate the Licensed Data in accordance with applicable law and "
              "may use the resulting de-identified data for its internal research and analytics without further "
              "obligation to Provider.")
DESTRUCTION = ("Within thirty (30) days after expiration or termination of this Agreement, Client shall return or "
               "destroy all Licensed Data and certify the destruction in writing, except for copies that Client is "
               "required by law to retain.")
GEOGRAPHIC = ("Licensed Data shall be stored and accessed only within the United States, and Client shall not permit "
              "access to Licensed Data from outside the United States.")

SPEC: dict[str, Any] = {
    "id": "tessera-dua",
    "header_title": "Data Use Agreement TCR-DUA-2025-118",
    "blocks": [
        ("title", TITLE),
        ("subtitle", "License of Clinical Research Registry Data"),
        ("p", f'{OPENING} by and between {VENDOR}, and {CLIENT}. Client is a wholly owned subsidiary of '
              'Vizient, Inc. Provider and Client are each a "party" and together the "parties."'),
        ("h1", "Recitals"),
        ("p", "A. Provider maintains a registry of coded clinical outcome records that research sites contribute for "
              "use in health services research."),
        ("p", "B. Client wishes to obtain a license to a defined extract of the registry, and Provider is willing to "
              "grant that license on the terms of this Agreement."),
        ("p", "C. The parties also wish to set out how Client must protect the extract, and what each of them must do "
              "before any Protected Health Information is delivered."),
        ("p", "The parties therefore agree as follows:"),

        ("h1", "1. Definitions"),
        ("p", "In this Agreement the following terms have the meanings given below. Other capitalized terms are "
              "defined where they first appear."),
        ("d", "1.1", "Affiliate", "means, for a party, an entity that directly or indirectly controls, is controlled "
                  "by, or is under common control with that party, where \"control\" means ownership of more than "
                  "fifty percent (50%) of the voting interests of the entity."),
        ("d", "1.2", "Confidential Information", "means non-public information that a party discloses to the other "
                  "party in connection with this Agreement and that is marked as confidential or that a reasonable "
                  "person would understand to be confidential, and includes the Licensed Data and the terms of this "
                  "Agreement."),
        ("d", "1.3", "Contract Year", "means each twelve (12) month period that begins on the Effective Date or on an "
                                      "anniversary of the Effective Date."),
        ("d", "1.4", "Data Fee", "means the annual fee that Schedule 1 states for a Contract Year."),
        ("d", "1.5", "Documentation", "means the data dictionary, file layouts and other written descriptions of the "
                                      "Licensed Data that Provider supplies, including the summary in Schedule 1."),
        ("d", "1.6", "HIPAA", "means the Health Insurance Portability and Accountability Act of 1996 and the "
                              "regulations that implement it, as amended."),
        ("d", "1.7", "Licensed Data", "means the clinical research registry records that Provider delivers to Client "
                  "under this Agreement, as Schedule 1 describes them, together with any correction or replacement "
                  "that Provider delivers for them."),
        ("d", "1.8", "Protected Health Information", "means individually identifiable health information that HIPAA "
                                                     "protects."),
        ("d", "1.9", "Renewal Term", "means each one-year term for which this Agreement renews under Section 15.2."),
        ("d", "1.10", "Term", "means the Initial Term and each Renewal Term."),

        ("h1", "2. Purpose and Scope"),
        ("c", "2.1", "Scope", "Provider shall deliver the Licensed Data to Client, and Client shall pay the Data Fee, "
                              "in each case as this Agreement provides."),
        ("c", "2.2", "Stand-Alone Agreement", "This Agreement is a stand-alone agreement. It is not issued under, and "
                  "does not amend or supplement, any other agreement between the parties."),
        ("c", "2.3", "Schedules", "Schedule 1 (Description of Data, License Period and Fees) and Schedule 2 "
                  "(Security Requirements) are part of this Agreement. If a Schedule conflicts with the numbered "
                  "Articles, the numbered Articles control."),
        ("c", "2.4", "Relationship Managers", "Each party shall name a relationship manager who is responsible for "
                  "the day-to-day administration of this Agreement and who is that party's first contact for "
                  "questions about it. A party may replace its relationship manager by notice to the other party."),
        ("c", "2.5", "Research Sites", "Provider shall list in the Documentation the research sites that contribute "
                  "records to the registry, identifying each site only by its site code. Provider may add or remove "
                  "contributing sites at any time, and a change in the contributing sites does not by itself entitle "
                  "either party to a change in the Data Fee."),

        ("h1", "3. Delivery of the Licensed Data"),
        ("c", "3.1", "Delivery Dates", "Provider shall deliver the Licensed Data on or before the dates that "
                  "Schedule 1 lists."),
        ("c", "3.2", "Method of Delivery", "Provider shall deliver the Licensed Data by secure file transfer to the "
                  "destination that Client designates in writing, in the file layout that the Documentation "
                  "describes. Provider shall send Client a delivery confirmation that lists the files, their sizes "
                  "and their checksums."),
        ("c", "3.3", "Verification", "Client has thirty (30) days after each delivery to check that it conforms to "
                  "the Documentation. If it does not, Client shall notify Provider in writing within that period and "
                  "describe the nonconformity in reasonable detail. Provider shall correct the nonconformity by "
                  "delivering corrected Licensed Data within fifteen (15) days after it receives the notice."),
        ("c", "3.4", "Errors Found by Provider", "If Provider finds an error in Licensed Data after delivering it, "
                  "Provider shall tell Client promptly and shall deliver corrected Licensed Data within fifteen (15) "
                  "days after it finds the error."),
        ("c", "3.5", "Changes to Data Elements", "Provider may remove a data element from future deliveries if law "
                  "or an obligation to a contributing research site requires it. Provider shall tell Client about "
                  "the removal at least thirty (30) days before the first delivery that omits the data element, "
                  "unless the law requires a shorter period."),
        ("c", "3.6", "Support", "Provider shall answer Client's reasonable questions about the Licensed Data and the "
                  "Documentation by e-mail, within three (3) business days after it receives each question."),
        ("c", "3.7", "Late Delivery", "If Provider expects to miss a delivery date, it shall tell Client promptly, "
                  "explain the reason and give a revised date. A late delivery does not change the length of the "
                  "Term."),
        ("c", "3.8", "Delivery Contacts", "Each party shall name to the other the person who sends or receives "
                  "deliveries and shall tell the other promptly if that person changes. Provider shall not send "
                  "Licensed Data to any destination that Client has not confirmed in writing."),
        ("c", "3.9", "Changes to File Layout", "Provider may change the file layout or the encoding of future "
                  "deliveries if it gives Client at least sixty (60) days' written notice, together with an updated "
                  "data dictionary. Such a change does not entitle Provider to any additional fee."),
        ("c", "3.10", "Lost or Corrupted Deliveries", "The risk of loss of Licensed Data in transit passes to Client "
                  "when the destination that Client designated receives it. If a delivery is lost or corrupted "
                  "before then, Provider shall deliver it again at no charge."),
        ("c", "3.11", "Confirmation of Receipt", "Client shall confirm receipt of each delivery in writing within five "
                  "(5) business days after Provider's delivery confirmation arrives. A confirmation of receipt does "
                  "not accept the Licensed Data and does not limit Client's rights under Section 3.3."),

        ("h1", "4. License and Permitted Uses"),
        ("c", "4.1", "License Grant", "Provider grants Client a non-exclusive, non-transferable license to receive "
                  "the Licensed Data during the Term and to use it as this Agreement provides."),
        ("c", "4.2", "Internal Research and Analytics", ANALYTICS),
        ("c", "4.3", "Machine Learning Models", f"{AIML} Client shall describe each such model to Provider in "
                  "writing on request."),
        ("c", "4.4", "Affiliates", f"{AFFILIATES} Client is responsible for the compliance of each such Affiliate "
                  "with this Agreement, and a disclosure to such an Affiliate is not a disclosure to a third party "
                  "for the purposes of Section 5.1."),
        ("c", "4.5", "De-identified Data", DEIDENTIFY),
        ("c", "4.6", "Ownership", "As between the parties, Provider retains all right, title and interest in the "
                  "Licensed Data, and this Agreement does not transfer ownership of the Licensed Data to Client. "
                  "Client owns the analyses and reports that it prepares, subject to Provider's rights in any "
                  "Licensed Data that they contain."),
        ("c", "4.7", "Responsibility for Employees", "Client is responsible for the compliance of its employees with "
                  "this Agreement. Before an employee is given access to the Licensed Data, Client shall tell the "
                  "employee about the restrictions in Articles 5 and 6."),
        ("c", "4.8", "Authorized Users", "Client shall keep a list of the individuals to whom it has given access to "
                  "the Licensed Data, showing for each person the date on which access began and the date on which "
                  "it ended. Client shall give Provider a copy of the list within ten (10) business days after "
                  "Provider asks for it."),
        ("c", "4.9", "Notices of Ownership", "Client shall not remove or obscure any copyright notice, source label or "
                  "confidentiality marking that appears in the Licensed Data or the Documentation."),

        ("h1", "5. Restrictions on Use"),
        ("c", "5.1", "Third Parties", f"{THIRD_PARTY} Client's own employees who need access to the Licensed Data to "
                  "perform their duties may use it on Client's behalf, and they are not third parties for the "
                  "purposes of this Section."),
        ("c", "5.2", "Linking", f"{LINKING} This Section applies however Client would do the linking, whether by "
                  "matching on identifiers, by probabilistic matching or by any other method."),
        ("c", "5.3", "No Re-identification", "Client shall not use the Licensed Data to identify, contact or locate "
                  "any individual or any research site that contributed records, and shall not attempt to reverse "
                  "any coding or masking method that Provider applied to the Licensed Data."),
        ("c", "5.4", "Technical Measures", "Client shall not circumvent, disable or interfere with any security "
                  "measure or access control that protects the Licensed Data, and shall not reverse engineer the "
                  "methods that Provider uses to compile its registry."),
        ("c", "5.5", "Compliance with Law", "Client shall use the Licensed Data in compliance with the laws and "
                  "regulations that apply to Client."),
        ("c", "5.6", "Notice of Unauthorized Use", "Client shall notify Provider promptly if it learns of any use or "
                  "disclosure of the Licensed Data that this Agreement does not permit, and shall take reasonable "
                  "steps to stop it and to prevent it from happening again."),

        ("h1", "6. Data Protection and Security"),
        ("c", "6.1", "Safeguards", "Client shall protect the Licensed Data with administrative, technical and "
                  "physical safeguards that are appropriate to its sensitivity and that are no less rigorous than "
                  "the requirements of Schedule 2. Client shall keep the Licensed Data in a secure environment that "
                  "meets those requirements."),
        ("c", "6.2", "Location of Licensed Data", f"{GEOGRAPHIC} On request, Client shall tell Provider in writing "
                  "where the Licensed Data is stored."),
        ("c", "6.3", "Access Controls", "Client shall limit access to the Licensed Data to named individuals who need "
                  "it to perform their duties for Client or for an Affiliate to which Section 4.4 permits Client to "
                  "give it. Client shall authenticate each of those individuals with multi-factor authentication "
                  "and shall remove a person's access promptly when the need for it ends."),
        ("c", "6.4", "Audit Logs", "Client shall keep audit logs that record each access to the Licensed Data, "
                  "showing who accessed it, when, and what the person did. Section 8.1 states how long Client shall "
                  "retain them."),
        ("c", "6.5", "Security Incidents", "Client shall notify Provider in writing within seventy-two (72) hours "
                  "after it discovers that anyone has accessed, used or disclosed the Licensed Data in a way that "
                  "this Agreement does not permit. The notice shall describe what happened, the Licensed Data "
                  "involved and the steps that Client has taken, and Client shall keep Provider informed as it "
                  "learns more."),
        ("c", "6.6", "Compliance Review", "Once in each Contract Year, and at any other time that Provider "
                  "reasonably suspects a breach of this Agreement, Provider may ask Client to confirm in writing "
                  "that it is complying with Articles 4, 5 and 6, and Client shall respond within thirty (30) days. "
                  "Provider may also review Client's audit logs, on ten (10) business days' notice and during "
                  "normal business hours, to verify that compliance."),
        ("c", "6.7", "Provider's Safeguards", "Provider shall protect the Licensed Data while it is in Provider's "
                  "possession, and while it is being delivered, with safeguards that are consistent with generally "
                  "accepted industry standards."),

        ("h1", "7. Protected Health Information"),
        ("c", "7.1", "Intent", "Provider does not intend to deliver Protected Health Information under this "
                  "Agreement. Schedule 1 describes the Licensed Data, from which Provider has removed direct "
                  "identifiers."),
        ("c", "7.2", "Business Associate Agreement", f"{BAA} Provider shall not deliver Protected Health Information "
                  "until that agreement is in effect."),
        ("c", "7.3", "Information Received in Error", "If Client receives information that appears to be Protected "
                  "Health Information and that Provider has not identified as such, Client shall stop using it, tell "
                  "Provider promptly, and protect it under Article 6 until the parties have agreed how to handle "
                  "it."),
        ("c", "7.4", "Compliance with HIPAA", "Each party shall comply with HIPAA to the extent that it applies to "
                  "that party's activities under this Agreement."),

        ("h1", "8. Retention and Records"),
        ("c", "8.1", "Retention", f"{RETENTION} The six (6) year period for each audit log entry begins on the date "
                  "of the entry and continues after the expiration or termination of this Agreement."),
        ("c", "8.2", "Records of Affiliate Agreements", "Client shall keep a copy of each written agreement that an "
                  "Affiliate gives under Section 4.4 for as long as that Affiliate has access to the Licensed Data, "
                  "and shall give Provider a copy on request."),
        ("c", "8.3", "Records Available to Provider", "Within ten (10) business days after Provider asks for them, "
                  "Client shall give Provider a copy of the audit logs and records that this Article 8 requires."),

        ("h1", "9. Fees and Payment"),
        ("c", "9.1", "Data Fee", "Client shall pay Provider the Data Fee for each Contract Year of the Term, in the "
                  "amount that Schedule 1 states or that Section 9.6 provides. Those fees are the only amounts that "
                  "Client owes for the Licensed Data unless the parties agree otherwise in writing."),
        ("c", "9.2", "Invoicing", "Provider shall invoice the Data Fee for each Contract Year on or after the first "
                  "day of that Contract Year. Each invoice shall state the number of this Agreement, the Contract "
                  "Year and the amount due, and shall show any tax separately."),
        ("c", "9.3", "Payment", "Client shall pay each undisputed invoice within forty-five (45) days after it "
                  "receives the invoice. Client shall pay in dollars, by electronic funds transfer to the account "
                  "that Provider designates in writing."),
        ("c", "9.4", "Disputed Amounts", "If Client disputes part of an invoice in good faith, it shall pay the "
                  "undisputed part when due and shall notify Provider of the dispute, and its basis, within thirty "
                  "(30) days after it receives the invoice. The parties shall work in good faith to resolve the "
                  "dispute promptly, and Client shall pay any amount that is resolved in Provider's favor within "
                  "fifteen (15) days after the resolution."),
        ("c", "9.5", "Late Payment", "An undisputed amount that remains unpaid after its due date bears interest from "
                  "the due date until it is paid, at one percent (1%) per month or at the highest rate that law "
                  "allows if that rate is lower."),
        ("c", "9.6", "Renewal Terms", "The Data Fee for each Renewal Term is the Data Fee for the preceding Contract "
                  "Year, increased by three percent (3%)."),

        ("h1", "10. Taxes"),
        ("c", "10.1", "Responsibility", "The Data Fee does not include sales, use, value added, excise or similar "
                  "taxes that a government imposes on the license or on Client's receipt of the Licensed Data. "
                  "Client shall pay those taxes, other than taxes on Provider's income, property, employees or "
                  "franchise, which Provider shall pay."),
        ("c", "10.2", "Exemption", "If Client is exempt from a tax, Client shall give Provider a valid exemption "
                  "certificate before the invoice date, and Provider shall not charge that tax on later invoices."),
        ("c", "10.3", "Withholding", "If law requires Client to withhold tax from a payment, Client shall withhold "
                  "the tax, pay it to the proper authority when due, and give Provider an official receipt. The "
                  "withheld amount is treated as paid to Provider."),

        ("h1", "11. Confidentiality"),
        ("c", "11.1", "Obligations", "Each party, as a recipient of the other party's Confidential Information, shall "
                  "(a) use it only to perform its obligations and exercise its rights under this Agreement, (b) "
                  "protect it with at least the care that it uses for its own information of the same kind, and "
                  "never less than reasonable care, and (c) not disclose it except to its own employees and "
                  "professional advisers who need to know it for those purposes and who are bound by duties of "
                  "confidentiality."),
        ("c", "11.2", "Exclusions", "Section 11.1 does not apply to information that the recipient can show (a) is or "
                  "becomes public through no fault of the recipient, (b) the recipient already knew without a duty "
                  "of confidentiality, (c) the recipient received rightfully from another source without a duty of "
                  "confidentiality, or (d) the recipient developed independently without using the other party's "
                  "Confidential Information."),
        ("c", "11.3", "Licensed Data", "Section 11.1 does not allow Client to disclose Licensed Data to anyone. "
                  "Articles 4 and 5 govern every use and disclosure of the Licensed Data."),
        ("c", "11.4", "Compelled Disclosure", "If law requires a party to disclose Confidential Information other than "
                  "Licensed Data, that party shall, where the law allows, give the other party prompt notice so "
                  "that it may seek a protective order, and shall disclose only what the law requires."),
        ("c", "11.5", "Duration", "The obligations in this Article 11 continue for five (5) years after the "
                  "expiration or termination of this Agreement, and for as long afterward as Client holds any "
                  "Licensed Data."),

        ("h1", "12. Warranties and Disclaimers"),
        ("c", "12.1", "Mutual Warranties", "Each party represents and warrants that it is duly organized and in good "
                  "standing, that it has the power and authority to enter into and perform this Agreement, and that "
                  "doing so does not breach any agreement that binds it."),
        ("c", "12.2", "Provider Warranties", "Provider represents and warrants that (a) it has the right to license "
                  "the Licensed Data to Client as this Agreement provides, (b) it has obtained the consents and "
                  "authorizations that law requires for the collection of the Licensed Data and for its delivery to "
                  "Client, and (c) each delivery of Licensed Data will conform in all material respects to the "
                  "Documentation when delivered."),
        ("c", "12.3", "Disclaimer", "EXCEPT AS THIS ARTICLE 12 EXPRESSLY STATES, PROVIDER MAKES NO WARRANTY ABOUT THE "
                  "LICENSED DATA OR THE DOCUMENTATION, WHETHER EXPRESS, IMPLIED OR STATUTORY, AND DISCLAIMS ALL "
                  "IMPLIED WARRANTIES, INCLUDING THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A "
                  "PARTICULAR PURPOSE. PROVIDER DOES NOT WARRANT THAT THE LICENSED DATA IS COMPLETE OR FREE FROM "
                  "ERRORS."),
        ("c", "12.4", "Client Acknowledgment", "Client acknowledges that registry records reflect what research sites "
                  "report, and that Client is responsible for the conclusions that it draws from the Licensed Data "
                  "and for the decisions that it makes in reliance on them."),

        ("h1", "13. Indemnification"),
        ("c", "13.1", "By Provider", "Provider shall defend Client against any claim that a third party brings "
                  "alleging that Client's use of the Licensed Data, as this Agreement permits, infringes that third "
                  "party's copyright or other intellectual property right, or alleging that Provider lacked a "
                  "consent or authorization that law required for the Licensed Data, and shall pay the losses, "
                  "costs and expenses, including reasonable attorneys' fees, that a court finally awards against "
                  "Client or that Provider agrees to pay in a settlement of the claim."),
        ("c", "13.2", "By Client", "Client shall defend Provider against any claim that a third party brings arising "
                  "from Client's breach of Article 5 or Article 6, and shall pay the losses, costs and expenses, "
                  "including reasonable attorneys' fees, that a court finally awards against Provider or that "
                  "Client agrees to pay in a settlement of the claim."),
        ("c", "13.3", "Procedure", "A party seeking indemnification shall give the other party prompt written notice "
                  "of the claim, allow the indemnifying party to control its defense and settlement, and cooperate "
                  "reasonably at the indemnifying party's expense. The indemnifying party shall not settle a claim "
                  "in a way that imposes an obligation on the indemnified party without the indemnified party's "
                  "written consent, which shall not be unreasonably withheld. A delay in giving notice relieves the "
                  "indemnifying party only to the extent that the delay prejudices its defense."),

        ("h1", "14. Limitation of Liability"),
        ("c", "14.1", "Excluded Loss", "NEITHER PARTY IS LIABLE TO THE OTHER FOR ANY INDIRECT, INCIDENTAL, SPECIAL, "
                  "CONSEQUENTIAL OR PUNITIVE LOSS, OR FOR LOST PROFITS OR LOST REVENUE, ARISING OUT OF OR RELATING "
                  "TO THIS AGREEMENT, EVEN IF THAT PARTY HAS BEEN ADVISED OF THE POSSIBILITY OF THE LOSS."),
        ("c", "14.2", "Liability Cap", "EACH PARTY'S TOTAL LIABILITY ARISING OUT OF OR RELATING TO THIS AGREEMENT IS "
                  "LIMITED TO THE DATA FEES THAT CLIENT HAS PAID OR OWES FOR THE CONTRACT YEAR IN WHICH THE EVENT "
                  "THAT GAVE RISE TO THE LIABILITY OCCURRED."),
        ("c", "14.3", "Exceptions", "Sections 14.1 and 14.2 do not apply to a party's obligations under Article 13, "
                  "to a breach of Article 5, 6 or 11, to a party's willful misconduct or gross negligence, or to "
                  "any liability that applicable law does not allow a party to limit."),
        ("c", "14.4", "Basis of the Bargain", "The parties have set the Data Fee in reliance on the limits in this "
                  "Article 14. Those limits apply however a claim arises, whether in contract, tort or otherwise."),

        ("h1", "15. Term and Termination"),
        ("c", "15.1", "Initial Term", INITIAL_TERM),
        ("c", "15.2", "Renewal and Termination", TERMINATION),
        ("c", "15.3", "Notice of Breach", "A notice of breach under Section 15.2 must describe the breach in "
                  "reasonable detail. A breach is cured if the breaching party stops it and remedies its "
                  "consequences within the period that Section 15.2 allows."),
        ("c", "15.4", "Effect on Fees", "If Client terminates this Agreement for Provider's uncured material breach, "
                  "Provider shall refund the part of the Data Fee that relates to the period after the termination "
                  "takes effect. In every other case the Data Fee is non-refundable."),
        ("c", "15.5", "Effect of Expiration or Termination", "When this Agreement expires or is terminated, "
                  "Provider's obligation to deliver further Licensed Data ends, the license in Section 4.1 ends, "
                  "and Article 16 governs what Client shall do with the Licensed Data that it has. Client shall pay "
                  "all fees that fell due before the effective date of the expiration or termination."),
        ("c", "15.6", "Survival", "Articles 5, 8, 11, 13, 14 and 16, Section 4.6, and any other term that by its "
                  "nature is meant to continue, survive the expiration or termination of this Agreement. Article 6 "
                  "continues to apply for as long as Client holds any Licensed Data."),

        ("h1", "16. Return and Destruction"),
        ("c", "16.1", "Return or Destruction", DESTRUCTION),
        ("c", "16.2", "Method", "Client shall destroy Licensed Data by a method that makes it unreadable and "
                  "impossible to reconstruct, such as secure deletion or physical destruction of the media on "
                  "which it is stored, in line with generally accepted industry standards."),
        ("c", "16.3", "Certification", "The written certification that Section 16.1 requires shall identify the "
                  "Licensed Data that Client returned or destroyed and the date and method, and an officer of "
                  "Client shall sign it. Client shall deliver the certification to Provider within the time that "
                  "Section 16.1 states."),
        ("c", "16.4", "Copies Required by Law", "If Client keeps a copy under the exception in Section 16.1, it shall "
                  "tell Provider in writing which law requires it to do so, shall continue to protect the copy under "
                  "Article 6, and shall not use the copy for any purpose other than the one that the law requires."),

        ("h1", "17. Governing Law and Venue"),
        ("c", "17.1", "Governing Law", "This Agreement, and any dispute that arises out of or relates to it, is "
                  "governed by the laws of the State of Delaware, without regard to its conflict-of-laws rules."),
        ("c", "17.2", "Venue", "Each party irrevocably submits to the exclusive jurisdiction and venue of the state "
                  "courts of the State of Delaware sitting in New Castle County for any action that arises out of or "
                  "relates to this Agreement, and waives any objection that the venue is inconvenient."),
        ("c", "17.3", "Escalation", "Before a party starts a court action, other than an action for equitable "
                  "relief, it shall give the other party written notice of the dispute, and the parties' "
                  "relationship managers shall meet, in person or by telephone, within twenty (20) days after the "
                  "notice to try to resolve it."),
        ("c", "17.4", "Jury Waiver", "EACH PARTY WAIVES, TO THE FULLEST EXTENT THAT LAW ALLOWS, ANY RIGHT TO A TRIAL "
                  "BY JURY IN ANY ACTION THAT ARISES OUT OF OR RELATES TO THIS AGREEMENT."),

        ("h1", "18. Notices"),
        ("c", "18.1", "Form and Delivery", "A notice under this Agreement must be in writing and must be delivered "
                  "by hand, by a nationally recognized overnight courier, or by certified mail with return receipt "
                  "requested, to the address in Section 18.2 or to another address that the receiving party "
                  "designates by notice."),
        ("c", "18.2", "Addresses", "Notices shall be addressed as follows:"),
        ("s", "(a)", "Notices to Provider: Tessera Clinical Research Analytics, LLC, Attention: Contracts "
                     "Administration, 88 Meadowlark Lane, Suite 12, Cambridge, Massachusetts 02139."),
        ("s", "(b)", "Notices to Client: Meridian Care Analytics, LLC, Attention: Legal Department, 1500 Corporate "
                     "Circle, Suite 220, Irving, Texas 75038."),
        ("c", "18.3", "When Effective", "A notice is effective when it is delivered or when the receiving party "
                  "refuses delivery. A notice that a courier delivers is delivered on the date that the courier's "
                  "records show, and a notice sent by certified mail is delivered on the date that the return "
                  "receipt shows."),
        ("c", "18.4", "Routine Communications", "Routine operational communications, such as delivery "
                  "confirmations and questions about the Documentation, may be sent by e-mail to the relationship "
                  "managers. They are not notices under this Article 18."),

        ("h1", "19. General"),
        ("c", "19.1", "Assignment", "Neither party may assign this Agreement, or any right or obligation under it, "
                  "without the other party's prior written consent, which the other party shall not unreasonably "
                  "withhold. Any attempted assignment without that consent is void."),
        ("c", "19.2", "Force Majeure", "Neither party is liable for a delay in performing, or a failure to perform, "
                  "an obligation under this Agreement, other than an obligation to pay money, to the extent that an "
                  "event beyond its reasonable control causes the delay or failure, including a natural disaster, "
                  "fire, flood, epidemic, war, act of terrorism, civil unrest, labor dispute, act of government, or "
                  "failure of a public utility or telecommunications network. The affected party shall give the "
                  "other party prompt notice and shall use reasonable efforts to resume performance."),
        ("c", "19.3", "Entire Agreement", "This Agreement, with its Schedules, is the entire agreement of the parties "
                  "on its subject matter and replaces all earlier proposals, statements and understandings about "
                  "it."),
        ("c", "19.4", "Amendment and Waiver", "This Agreement may be amended only by a written document that both "
                  "parties sign. A failure or delay in enforcing a right is not a waiver of that right, and a waiver "
                  "is effective only if it is in writing and signed by the party that gives it."),
        ("c", "19.5", "Severability", "If a court holds a provision of this Agreement to be invalid or "
                  "unenforceable, the provision shall be enforced to the extent that the law allows, and the rest "
                  "of this Agreement remains in effect."),
        ("c", "19.6", "Independent Contractors", "The parties are independent contractors. Nothing in this "
                  "Agreement creates a partnership, joint venture, agency or employment relationship between them."),
        ("c", "19.7", "Insurance", "During the Term each party shall maintain general liability insurance with "
                  "limits of at least $2,000,000 per occurrence, and Client shall also maintain cyber liability "
                  "insurance with limits of at least $5,000,000 per claim. Each party shall give the other a "
                  "certificate of insurance on request."),
        ("c", "19.8", "Publicity", "Neither party shall use the other party's name or marks in a press release, "
                  "advertisement or customer list without the other party's prior written consent."),
        ("c", "19.9", "No Third-Party Beneficiaries", "This Agreement creates rights only for the parties and their "
                  "permitted successors and assigns. No other person may enforce it."),
        ("c", "19.10", "Interpretation", "Headings are for convenience only. The word \"including\" means including "
                  "without limitation. Both parties have had the opportunity to review this Agreement with "
                  "counsel, and no rule that construes a term against its drafter applies to it."),
        ("c", "19.11", "Equitable Relief", "Each party acknowledges that a breach of Article 5, 6 or 11 may cause the "
                  "other party harm for which money is not an adequate remedy, and that the other party may "
                  "therefore ask a court for an injunction or other equitable relief in addition to any other "
                  "remedy that it has."),
        ("c", "19.12", "Authority to Sign", "Each person who signs this Agreement for a party represents that he or "
                  "she is authorized to sign it for that party and to bind that party to its terms."),
        ("c", "19.13", "Counterparts", "This Agreement may be signed in counterparts, each of which is an original "
                  "and all of which together are one agreement. A signature that is delivered electronically is as "
                  "effective as an original signature."),

        ("break",),
        ("h1", "Signature Page"),
        ("p", "IN WITNESS WHEREOF, the parties have caused this Agreement to be signed by their authorized "
              "representatives on the dates written below, to take effect as of the Effective Date."),
        ("signatures",),

        ("break",),
        ("h1", "Schedule 1: Description of Data, License Period and Fees"),
        ("p", "This Schedule 1 is part of the Agreement. Capitalized terms have the meanings given in the Agreement."),
        ("h2", "Part A. Description of the Licensed Data"),
        ("c", "A.1", "Data Product", "The Licensed Data is the Tessera Outcomes Registry Extract, a collection of "
                  "record-level clinical outcome data that Provider compiles from the research sites that "
                  "contribute to its registry."),
        ("c", "A.2", "Content", "Each record describes one patient episode. Provider has replaced names, street "
                  "addresses and account numbers with a coded study number. The record carries the code of the "
                  "contributing site, the diagnosis group, the procedure group, the treatment category, the outcome "
                  "measure at follow-up, the length of follow-up, the age band and the year of service."),
        ("c", "A.3", "Coverage", "The Licensed Data covers episodes that took place in the calendar years 2019 "
                  "through 2024 at the research sites that contributed to the registry."),
        ("c", "A.4", "Format", "Provider delivers the Licensed Data as comma-separated text files with a header row, "
                  "encoded in UTF-8, together with a data dictionary that describes each field."),
        ("c", "A.5", "Data Dictionary Summary", "The principal fields are:"),
        ("s", "(a)", "STUDY_ID: the coded study number that Provider assigns to the episode."),
        ("s", "(b)", "SITE_CODE: Provider's code for the contributing research site."),
        ("s", "(c)", "DIAGNOSIS_GROUP and PROCEDURE_GROUP: the diagnosis group and the procedure group for the "
                     "episode."),
        ("s", "(d)", "TREATMENT_CATEGORY: the category of the main treatment, such as surgical, medical or "
                     "rehabilitative."),
        ("s", "(e)", "OUTCOME_SCORE: the score of the outcome measure that the site recorded at follow-up."),
        ("s", "(f)", "FOLLOWUP_DAYS: the number of days between the treatment and the follow-up."),
        ("s", "(g)", "AGE_BAND: the five-year age band of the patient at the time of treatment."),
        ("s", "(h)", "SERVICE_YEAR: the calendar year in which the treatment took place."),
        ("h2", "Part B. License Period"),
        ("s", "(a)", "The license in Section 4.1 runs for the Term."),
        ("s", "(b)", "Initial Term: April 1, 2025 through March 31, 2027."),
        ("s", "(c)", "First Contract Year: April 1, 2025 through March 31, 2026."),
        ("s", "(d)", "Second Contract Year: April 1, 2026 through March 31, 2027."),
        ("s", "(e)", "Each Renewal Term is one Contract Year, as Section 15.2 provides."),
        ("h2", "Part C. Delivery Dates"),
        ("s", "(a)", "Initial delivery: on or before April 15, 2025."),
        ("s", "(b)", "Refresh for the Second Contract Year: on or before April 30, 2026."),
        ("s", "(c)", "Refresh for each Renewal Term: within thirty (30) days after the first day of the Renewal "
                     "Term."),
        ("h2", "Part D. Data Fees"),
        ("s", "(a)", "Data Fee for the First Contract Year: $210,000."),
        ("s", "(b)", "Data Fee for the Second Contract Year: $210,000."),
        ("s", "(c)", "Total of the Data Fees for the Initial Term: $420,000."),
        ("s", "(d)", "Data Fee for each Renewal Term: as Section 9.6 provides."),
        ("p", "Provider invoices each Data Fee under Section 9.2, and Client pays it under Section 9.3."),
        ("h2", "Part E. Billing Contacts"),
        ("s", "(a)", "Invoices to Client: Meridian Care Analytics, LLC, Attention: Accounts Payable, 1500 Corporate "
                     "Circle, Suite 220, Irving, Texas 75038."),
        ("s", "(b)", "Payments to Provider: by electronic funds transfer to the account that Provider's invoice "
                     "identifies, with the invoice number in the payment reference."),

        ("h1", "Schedule 2: Security Requirements"),
        ("p", "This Schedule 2 is part of the Agreement. Client shall meet the following requirements in the secure "
              "environment in which it keeps the Licensed Data."),
        ("s", "(a)", "Isolation: the secure environment is logically separated from Client's general-purpose "
                     "network and is protected by firewalls and intrusion detection."),
        ("s", "(b)", "Access: each user has an individual account with a unique credential and multi-factor "
                     "authentication, access is limited by role, and Client reviews the list of users at least once "
                     "in each calendar quarter."),
        ("s", "(c)", "Encryption: Licensed Data is encrypted at rest with AES-256 or a stronger method and in "
                     "transit with TLS 1.2 or a later version."),
        ("s", "(d)", "Logging: the audit logs record the user, the date and time and the nature of each access, and "
                     "they are protected against alteration."),
        ("s", "(e)", "Devices: Licensed Data is not copied to laptops, removable media or personal devices."),
        ("s", "(f)", "Vulnerability management: Client applies critical security patches within thirty (30) days "
                     "after they are released and scans the secure environment for vulnerabilities at least once in "
                     "each calendar quarter."),
        ("s", "(g)", "Backups: a backup that contains Licensed Data is encrypted and is kept in the secure "
                     "environment, subject to the location requirement in Section 6.2."),
        ("s", "(h)", "Training: each person who has access to the Licensed Data receives training on this Agreement "
                     "before first access and once in each calendar year afterward."),
    ],
    "signers": [
        ("Provider", "Tessera Clinical Research Analytics, LLC", "Dr. Helena Voss", "Chief Executive Officer",
         "04/03/2025"),
        ("Client", "Meridian Care Analytics, LLC", "Marcus Adeyemi", "Chief Data Officer", "04/02/2025"),
    ],
    "details": {
        "Vendor": ("Tessera Clinical Research Analytics, LLC", VENDOR),
        "VizientEntity": ("Meridian Care Analytics, LLC", CLIENT),
        "DocumentType": ("DUA", TITLE),
        "ContractIdentifier": ("Data Use Agreement No. TCR-DUA-2025-118", DUA_ID),
        "EffectiveDate": ("2025-04-01", OPENING),
        "ExpirationDate": ("2027-03-31", INITIAL_TERM),
        "RenewalTermination": ("Renews automatically for successive one-year terms unless either party gives at "
                               "least 90 days' written notice of non-renewal; either party may terminate for uncured "
                               "material breach after 30 days' notice; Client may terminate for convenience on 30 "
                               "days' notice", TERMINATION),
        "Signatories": ("Dr. Helena Voss (Chief Executive Officer, 04/03/2025); Marcus Adeyemi (Chief Data Officer, "
                        "04/02/2025)", "Dr. Helena Voss"),
        "ParentAgreementReference": ("", ""),
    },
    "rights": {
        "Right_InternalAnalytics": ("Permitted", ANALYTICS),
        "Right_AIML": ("Conditional", AIML),
        "Right_ProductDevelopment": ("Not Addressed", ""),
        "Right_BAARequired": ("Conditional", BAA),
        "Right_Retention": ("Conditional", RETENTION),
        "Right_AffiliateSharing": ("Conditional", AFFILIATES),
        "Right_ThirdPartySharing": ("Prohibited", THIRD_PARTY),
        "Right_DataLinking": ("Prohibited", LINKING),
        "Right_DeIdentification": ("Permitted", DEIDENTIFY),
        "Right_Destruction": ("Conditional", DESTRUCTION),
        "Right_Geographic": ("Prohibited", GEOGRAPHIC),
    },
    "forbidden": ("product development", "derivative", "commercial product", "commercial solution", "incorporate"),
    "exempt": (),
}
