import { HttpTestingController } from '@angular/common/http/testing'
import { TestBed } from '@angular/core/testing'
import { Subscription } from 'rxjs'
import { environment } from 'src/environments/environment'
import { commonAbstractPaperlessServiceTests } from './abstract-paperless-service.spec'
import { ShareLinkBundleService } from './share-link-bundle.service'

const endpoint = 'share_link_bundles'

commonAbstractPaperlessServiceTests(endpoint, ShareLinkBundleService)

describe('ShareLinkBundleService', () => {
  let httpTestingController: HttpTestingController
  let service: ShareLinkBundleService
  let subscription: Subscription | undefined

  beforeEach(() => {
    httpTestingController = TestBed.inject(HttpTestingController)
    service = TestBed.inject(ShareLinkBundleService)
  })

  afterEach(() => {
    subscription?.unsubscribe()
    httpTestingController.verify()
  })

  it('creates bundled share links', () => {
    const payload = {
      document_ids: [1, 2],
      file_version: 'archive',
      expiration_days: 7,
    }
    subscription = service.createBundle(payload as any).subscribe()
    const req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}${endpoint}/`
    )
    expect(req.request.method).toBe('POST')
    expect(req.request.body).toEqual(payload)
    req.flush({})
  })

  it('rebuilds bundles', () => {
    subscription = service.rebuildBundle(12).subscribe()
    const req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}${endpoint}/12/rebuild/`
    )
    expect(req.request.method).toBe('POST')
    expect(req.request.body).toEqual({})
    req.flush({})
  })

  it('lists bundles with expected parameters', () => {
    subscription = service.listAllBundles().subscribe()
    const req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}${endpoint}/?page=1&page_size=1000&ordering=-created`
    )
    expect(req.request.method).toBe('GET')
    req.flush({ results: [] })
  })
})
