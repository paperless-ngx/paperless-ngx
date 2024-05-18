import { DocumentTypeService } from './document-type.service'
import { commonAbstractNameFilterPaperlessServiceTests } from './abstract-name-filter-service.spec'

commonAbstractNameFilterPaperlessServiceTests(
  'document_types',
  DocumentTypeService
)
