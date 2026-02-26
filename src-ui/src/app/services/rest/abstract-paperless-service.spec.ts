import { provideHttpClient, withInterceptorsFromDi } from '@angular/common/http'
import {
  HttpTestingController,
  provideHttpClientTesting,
} from '@angular/common/http/testing'
import { TestBed } from '@angular/core/testing'
import { Subscription } from 'rxjs'
import { environment } from 'src/environments/environment'
import { AbstractPaperlessService } from './abstract-paperless-service'

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

    test('should call appropriate api endpoint for get a few objects', () => {
      subscription = service.getFew([1, 2, 3]).subscribe()
      const req = httpTestingController.expectOne(
        `${environment.apiBaseUrl}${endpoint}/?id__in=1,2,3&ordering=-id&page_size=1000`
      )
      expect(req.request.method).toEqual('GET')
      req.flush([])
      subscription = service.getFew([4, 5, 6], { foo: 'bar' }).subscribe()
      const req2 = httpTestingController.expectOne(
        `${environment.apiBaseUrl}${endpoint}/?id__in=4,5,6&ordering=-id&page_size=1000&foo=bar`
      )
      expect(req2.request.method).toEqual('GET')
      req2.flush([])
    })

    test('getCached should return object from listAll when found', () => {
      const o = { id: 1, name: 'Test' }
      let result
      subscription = service.getCached(1).subscribe((r) => (result = r))
      httpTestingController
        .expectOne(
          `${environment.apiBaseUrl}${endpoint}/?page=1&page_size=100000`
        )
        .flush({ results: [o] })
      expect(result).toEqual(o)
    })

    test('getCached should fetch from API when ID not in listAll', () => {
      const o = { id: 9999, name: 'NewItem' }
      let result
      subscription = service.getCached(9999).subscribe((r) => (result = r))
      httpTestingController
        .expectOne(
          `${environment.apiBaseUrl}${endpoint}/?page=1&page_size=100000`
        )
        .flush({ results: [] })
      httpTestingController
        .expectOne(`${environment.apiBaseUrl}${endpoint}/9999/`)
        .flush(o)
      expect(result).toEqual(o)
    })

    test('getCached should return undefined when ID not found and API returns error', () => {
      let result = 'not-set'
      subscription = service.getCached(9999).subscribe((r) => (result = r))
      httpTestingController
        .expectOne(
          `${environment.apiBaseUrl}${endpoint}/?page=1&page_size=100000`
        )
        .flush({ results: [] })
      httpTestingController
        .expectOne(`${environment.apiBaseUrl}${endpoint}/9999/`)
        .flush('Not found', { status: 404, statusText: 'Not found' })
      expect(result).toBeUndefined()
    })

    test('getCached should not make duplicate API calls for the same unknown ID', () => {
      const o = { id: 9999, name: 'NewItem' }
      let result1, result2
      service.getCached(9999).subscribe((r) => (result1 = r))
      service.getCached(9999).subscribe((r) => (result2 = r))
      httpTestingController
        .expectOne(
          `${environment.apiBaseUrl}${endpoint}/?page=1&page_size=100000`
        )
        .flush({ results: [] })
      httpTestingController
        .expectOne(`${environment.apiBaseUrl}${endpoint}/9999/`)
        .flush(o)
      expect(result1).toEqual(o)
      expect(result2).toEqual(o)
    })

    test('getCached should refetch after clearCache()', () => {
      const o = { id: 9999, name: 'NewItem' }
      subscription = service.getCached(9999).subscribe()
      httpTestingController
        .expectOne(
          `${environment.apiBaseUrl}${endpoint}/?page=1&page_size=100000`
        )
        .flush({ results: [] })
      httpTestingController
        .expectOne(`${environment.apiBaseUrl}${endpoint}/9999/`)
        .flush(o)

      service.clearCache()

      subscription = service.getCached(9999).subscribe()
      httpTestingController
        .expectOne(
          `${environment.apiBaseUrl}${endpoint}/?page=1&page_size=100000`
        )
        .flush({ results: [o] })
      httpTestingController.expectNone(
        `${environment.apiBaseUrl}${endpoint}/9999/`
      )
    })
  })

  beforeEach(() => {
    TestBed.configureTestingModule({
      teardown: { destroyAfterEach: true },
      imports: [],
      providers: [
        ServiceClass,
        provideHttpClient(withInterceptorsFromDi()),
        provideHttpClientTesting(),
      ],
    })

    httpTestingController = TestBed.inject(HttpTestingController)
    service = TestBed.inject(ServiceClass)
  })

  afterEach(() => {
    subscription?.unsubscribe()
    // httpTestingController.verify()
  })
}
