import { CorrespondentService } from './correspondent.service'
import { commonAbstractNameFilterPaperlessServiceTests } from './abstract-name-filter-service.spec'

commonAbstractNameFilterPaperlessServiceTests(
  'correspondents',
  CorrespondentService
)
