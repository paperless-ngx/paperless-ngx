import { commonAbstractNameFilterPaperlessServiceTests } from './abstract-name-filter-service.spec'
import { TagService } from './tag.service'

commonAbstractNameFilterPaperlessServiceTests('tags', TagService)
