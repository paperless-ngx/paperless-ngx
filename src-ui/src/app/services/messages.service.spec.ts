import { TestBed } from '@angular/core/testing'

import { MessagesService } from './messages.service'

import {
  HttpClientTestingModule,
  HttpTestingController,
} from '@angular/common/http/testing'
import { environment } from 'src/environments/environment'

describe('MessagesService', () => {
  let httpTestingController: HttpTestingController
  let service: MessagesService

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [MessagesService],
      imports: [HttpClientTestingModule],
    })
    httpTestingController = TestBed.inject(HttpTestingController)
    service = TestBed.inject(MessagesService)
  })

  afterEach(() => {
    httpTestingController.verify()
  })

  it('calls get profile endpoint', () => {
    service.get().subscribe()
    const req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}messages/`
    )
    expect(req.request.method).toEqual('GET')
  })
})
