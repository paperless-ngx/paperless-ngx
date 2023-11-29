import { HttpTestingController } from '@angular/common/http/testing'
import { TestBed } from '@angular/core/testing'
import { Subscription } from 'rxjs'
import { environment } from 'src/environments/environment'
import { commonAbstractPaperlessServiceTests } from './abstract-paperless-service.spec'
import { ShareLinkService } from './share-link.service'

let httpTestingController: HttpTestingController
let service: ShareLinkService
let subscription: Subscription
const endpoint = 'share_links'

// run common tests
commonAbstractPaperlessServiceTests(endpoint, ShareLinkService)

describe(`Additional service tests for ShareLinkService`, () => {
  beforeEach(() => {
    // Dont need to setup again

    httpTestingController = TestBed.inject(HttpTestingController)
    service = TestBed.inject(ShareLinkService)
  })

  afterEach(() => {
    subscription?.unsubscribe()
    httpTestingController.verify()
  })

  it('should support creating link for document', () => {
    subscription = service.createLinkForDocument(0).subscribe()
    httpTestingController
      .expectOne(`${environment.apiBaseUrl}${endpoint}/`)
      .flush({})
  })

  it('should support get links for a document', () => {
    subscription = service.getLinksForDocument(0).subscribe()
    httpTestingController
      .expectOne(`${environment.apiBaseUrl}documents/0/${endpoint}/`)
      .flush({})
  })
})
