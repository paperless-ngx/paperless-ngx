import { HttpTestingController } from '@angular/common/http/testing'
import { TestBed } from '@angular/core/testing'
import { Subscription } from 'rxjs'
import { environment } from 'src/environments/environment'
import { commonAbstractPaperlessServiceTests } from './abstract-paperless-service.spec'
import { ProcessedMailService } from './processed-mail.service'

let httpTestingController: HttpTestingController
let service: ProcessedMailService
let subscription: Subscription
const endpoint = 'processed_mail'

// run common tests
commonAbstractPaperlessServiceTests(endpoint, ProcessedMailService)

describe('Additional service tests for ProcessedMailService', () => {
  beforeEach(() => {
    // Dont need to setup again

    httpTestingController = TestBed.inject(HttpTestingController)
    service = TestBed.inject(ProcessedMailService)
  })

  afterEach(() => {
    subscription?.unsubscribe()
    httpTestingController.verify()
  })

  it('should call appropriate api endpoint for bulk delete', () => {
    const ids = [1, 2, 3]
    subscription = service.bulk_delete(ids).subscribe()
    const req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}${endpoint}/bulk_delete/`
    )
    expect(req.request.method).toEqual('POST')
    expect(req.request.body).toEqual({ mail_ids: ids })
    req.flush({})
  })
})
