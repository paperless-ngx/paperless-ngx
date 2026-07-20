import { commonAbstractNameFilterPaperlessServiceTests } from './abstract-name-filter-service.spec'
import { NamedCounterService } from './named-counter.service'

commonAbstractNameFilterPaperlessServiceTests(
  'named_counters',
  NamedCounterService
)
