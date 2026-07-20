import { commonAbstractPaperlessServiceTests } from './abstract-paperless-service.spec'
import { NamedCounterService } from './named-counter.service'

const endpoint = 'named_counters'

commonAbstractPaperlessServiceTests(endpoint, NamedCounterService)
