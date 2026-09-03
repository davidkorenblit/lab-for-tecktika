# Limitations & Future Roadmap

## 1. Current Stubbed Features (Permitted Under Constraints)
* **OCR for Scanned PDFs**: Document processing currently assumes text-based PDFs. Optical Character Recognition (Azure AI Document Intelligence) is abstracted behind an interface.
* **Non-PDF File Formats**: Office documents (`.docx`, `.pptx`) and plain text formats can be ingested via the same seam, but only `.pdf` validation is active in the primary pipeline.
* **Permission Trimming**: Document-level ACLs from SharePoint are not trimmed during hybrid search; all authenticated users with platform access query the single library index.
* **Multi-Tenant / Multi-Library Support**: Designed as single-tenant scoped to a single document library.

---

## 2. Behavior Under Extreme Load & Bottlenecks
* **Azure OpenAI TPM/RPM Throttling**: Under simultaneous batch backfill and high user chat volume, OpenAI may return HTTP 429. Mitigation requires exponential retry backoff and/or provisioned throughput (PTU).
* **Search Indexer Execution Queue**: Concurrent ingestion triggers serialize on the indexer schedule unless push-API indexing is enabled.
* **File Size Thresholds**: Direct browser uploads over 50 MB use chunked Blob/SharePoint upload sessions; connection drops require client-side resumable upload logic.

---

## 3. Next Steps & Production Enhancements
1. **Dynamic ACL Security Filters**: Inject user security group claims into OData filter queries in Azure AI Search.
2. **Azure AI Document Intelligence Integration**: For the current scope, standard text parsing is utilized given the clean, text-native synthetic dataset. In production environments with uncontrolled input formats (e.g., scanned PDFs, complex tables, multi-column layouts), `Microsoft.Skills.Vision.DocumentIntelligenceSkill` should be integrated into the Azure AI Search Skillset.
3. **Multi-Region Active-Passive Failover**: Geo-redundant storage and secondary AI Search replicas for business continuity.
