import {
  HttpClientTestingModule,
  HttpTestingController,
} from '@angular/common/http/testing'
import { Subscription } from 'rxjs'
import { TestBed } from '@angular/core/testing'
import { environment } from 'src/environments/environment'
import { SearchService } from './search.service'

let httpTestingController: HttpTestingController
let service: SearchService
let subscription: Subscription
const endpoint = 'search/autocomplete'

describe('SearchService', () => {
  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [SearchService],
      imports: [HttpClientTestingModule],
    })

    httpTestingController = TestBed.inject(HttpTestingController)
    service = TestBed.inject(SearchService)
  })

  afterEach(() => {
    subscription?.unsubscribe()
    httpTestingController.verify()
  })

  it('should call correct api endpoint on autocomplete', () => {
    const term = 'apple'
    subscription = service.autocomplete(term).subscribe()
    const req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}${endpoint}/?term=${term}`
    )
    expect(req.request.method).toEqual('GET')
  })
})
