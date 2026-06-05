import { HttpTestingController } from '@angular/common/http/testing'
import { TestBed } from '@angular/core/testing'
import { Subscription } from 'rxjs'
import { environment } from 'src/environments/environment'
import { commonAbstractNameFilterPaperlessServiceTests } from './abstract-name-filter-service.spec'
import { FolderService } from './folder.service'

let httpTestingController: HttpTestingController
let service: FolderService
let subscription: Subscription
const endpoint = 'folders'

commonAbstractNameFilterPaperlessServiceTests('folders', FolderService)

describe(`Additional service tests for FolderService`, () => {
  beforeEach(() => {
    httpTestingController = TestBed.inject(HttpTestingController)
    service = TestBed.inject(FolderService)
  })

  afterEach(() => {
    subscription?.unsubscribe()
    httpTestingController.verify()
  })

  it('should request the folder tree from roots', () => {
    subscription = service.getTree().subscribe()
    const req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}${endpoint}/?page=1&page_size=100000&ordering=name&is_root=true`
    )
    expect(req.request.method).toEqual('GET')
    req.flush({ count: 0, results: [] })
  })
})
