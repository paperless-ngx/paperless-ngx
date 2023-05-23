import { StoragePathService } from './storage-path.service'
import { commonAbstractNameFilterPaperlessServiceTests } from './abstract-name-filter-service.spec'

commonAbstractNameFilterPaperlessServiceTests(
  'storage_paths',
  StoragePathService
)
