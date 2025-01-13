import { HttpTestingController } from '@angular/common/http/testing'
import { TestBed } from '@angular/core/testing'
import { Subscription } from 'rxjs'
import { environment } from 'src/environments/environment'
import { commonAbstractNameFilterPaperlessServiceTests } from './abstract-name-filter-service.spec'
import { StoragePathService } from './storage-path.service'

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
