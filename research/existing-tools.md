# Existing-tool check

Checked 18 September 2026. These are official product descriptions, not independent evidence of effectiveness or evidence that BHT uses a particular product.

| Primary source | Relevant documented capability | Consequence for this project |
| --- | --- | --- |
| [Oracle Financials 26A, Types of Holds](https://docs.oracle.com/en/cloud/saas/financials/26a/fappp/types-of-holds.html) | The manual Invalid PO hold addresses an absent valid PO number. Matching holds cover invoice-to-order/receipt differences, with specified correction and release routes. | Missing PO references and invoice exceptions are established software functions. The prototype cannot claim a new product category or infer that another queue is needed. |
| [SAP, Manage Workflows for Supplier Invoices, app F2873](https://help.sap.com/docs/SAP_S4HANA_CLOUD/0e602d466b99490187fcbb30d1dc897c/9bd9a6b4124446a5b31ddfecbff07508.html) | Workflows for blocked and parked invoices support approver determination, including a cost-centre responsible person or specific users, and fallback workflows. | Identifying a responsible role may be a configuration or master-data problem. Compare the current workflow and available role mappings before building routing elsewhere. |
| [NEP Cloud, Purchase to Pay](https://nepcloud.nhs.uk/solutions-and-services/purchase-to-pay-p2p/) | The NHS-sector provider describes an integrated purchasing/AP cycle covering orders, suppliers, invoice entry, approval and payment. | Sector-specific integrated options exist. This statement does not establish which features BHT has enabled or whether staff find them sufficient. |

The prototype's value hypothesis is therefore modest: an explicit source contract, time-aware evidence reconstruction and traceable cohort measurement might assist investigation where the present report is insufficient. No comparison with an installed system has occurred. Documentation alone cannot prove this incremental value, and these sources do not establish that historical reconstruction is absent from commercial products.

The first real engagement step would be to inspect the existing exception report and follow a few invoices with AP. If it already provides the same reliable evidence and route, use it. If exceptions arise mainly from late PO setup, missing receipt entry or exhausted value, investigate those causes rather than expand a header-only report by default.
