import {
  HttpClientTestingModule,
  HttpTestingController,
} from '@angular/common/http/testing'
import { AbstractPaperlessService } from './abstract-paperless-service'
import { Subscription } from 'rxjs'
import { TestBed } from '@angular/core/testing'
import { environment } from 'src/environments/environment'

let httpTestingController: HttpTestingController
let service: AbstractPaperlessService<any>
let subscription: Subscription

export const commonAbstractPaperlessServiceTests = (endpoint, ServiceClass) => {
  describe(`Common service tests for ${endpoint}`, () => {
    test('should call appropriate api endpoint for list all', () => {
      subscription = service.listAll().subscribe()
      const req = httpTestingController.expectOne(
        `${environment.apiBaseUrl}${endpoint}/?page=1&page_size=100000`
      )
      expect(req.request.method).toEqual('GET')
      req.flush([])
    })

    test('should call appropriate api endpoint for get a single object', () => {
      const id = 0
      subscription = service.get(id).subscribe()
      const req = httpTestingController.expectOne(
        `${environment.apiBaseUrl}${endpoint}/${id}/`
      )
      expect(req.request.method).toEqual('GET')
      req.flush([])
    })

    test('should call appropriate api endpoint for create a single object', () => {
      const o = {
        name: 'Name',
      }
      subscription = service.create(o).subscribe()
      const req = httpTestingController.expectOne(
        `${environment.apiBaseUrl}${endpoint}/`
      )
      expect(req.request.method).toEqual('POST')
      req.flush([])
    })

    test('should call appropriate api endpoint for delete a single object', () => {
      const id = 10
      const o = {
        name: 'Name',
        id,
      }
      subscription = service.delete(o).subscribe()
      const req = httpTestingController.expectOne(
        `${environment.apiBaseUrl}${endpoint}/${id}/`
      )
      expect(req.request.method).toEqual('DELETE')
      req.flush([])
    })

    test('should call appropriate api endpoint for update a single object', () => {
      const id = 10
      const o = {
        name: 'Name',
        id,
      }

      // some services need to call listAll first
      subscription = service.listAll().subscribe()
      let req = httpTestingController.expectOne(
        `${environment.apiBaseUrl}${endpoint}/?page=1&page_size=100000`
      )
      req.flush({
        results: [o],
      })
      subscription.unsubscribe()

      subscription = service.update(o).subscribe()
      req = httpTestingController.expectOne(
        `${environment.apiBaseUrl}${endpoint}/${id}/`
      )
      expect(req.request.method).toEqual('PUT')
      req.flush([])
    })

    test('should call appropriate api endpoint for patch a single object', () => {
      const id = 10
      const o = {
        name: 'Name',
        id,
      }
      subscription = service.patch(o).subscribe()
      const req = httpTestingController.expectOne(
        `${environment.apiBaseUrl}${endpoint}/${id}/`
      )
      expect(req.request.method).toEqual('PATCH')
      req.flush([])
    })
  })

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [ServiceClass],
      imports: [HttpClientTestingModule],
      teardown: { destroyAfterEach: true },
    })

    httpTestingController = TestBed.inject(HttpTestingController)
    service = TestBed.inject(ServiceClass)
  })

  afterEach(() => {
    subscription?.unsubscribe()
    // httpTestingController.verify()
  })
}
