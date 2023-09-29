import { SsoGroupService } from './sso-group.service'
import { commonAbstractNameFilterPaperlessServiceTests } from './abstract-name-filter-service.spec'

commonAbstractNameFilterPaperlessServiceTests('sso_groups', SsoGroupService)
