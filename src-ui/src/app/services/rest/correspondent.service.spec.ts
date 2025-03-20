import { commonAbstractNameFilterPaperlessServiceTests } from './abstract-name-filter-service.spec'
import { CorrespondentService } from './correspondent.service'

commonAbstractNameFilterPaperlessServiceTests(
  'correspondents',
  CorrespondentService
)
