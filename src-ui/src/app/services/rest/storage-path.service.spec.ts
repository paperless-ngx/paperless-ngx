import { StoragePathService } from './storage-path.service'
import { commonAbstractNameFilterPaperlessServiceTests } from './abstract-name-filter-service.spec'
import { Subscription } from 'rxjs'
import { HttpTestingController } from '@angular/common/http/testing'
import { TestBed } from '@angular/core/testing'
import { environment } from 'src/environments/environment'

let httpTestingController: HttpTestingController
let service: StoragePathService
let subscription: Subscription
const endpoint = 'storage_paths'

commonAbstractNameFilterPaperlessServiceTests(
  'storage_paths',
  StoragePathService
)

describe(`Additional service tests for StoragePathservice`, () => {
  beforeEach(() => {
    httpTestingController = TestBed.inject(HttpTestingController)
    service = TestBed.inject(StoragePathService)
  })

  afterEach(() => {
    subscription?.unsubscribe()
    httpTestingController.verify()
  })

  it('should support testing path', () => {
    subscription = service.testPath('path', 11).subscribe()
    httpTestingController
      .expectOne(`${environment.apiBaseUrl}${endpoint}/test/`)
      .flush('ok')
  })
})
