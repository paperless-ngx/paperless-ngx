import { commonAbstractNameFilterPaperlessServiceTests } from './abstract-name-filter-service.spec'
import { DocumentTypeService } from './document-type.service'

commonAbstractNameFilterPaperlessServiceTests(
  'document_types',
  DocumentTypeService
)
