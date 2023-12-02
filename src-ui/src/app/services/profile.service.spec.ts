import { TestBed } from '@angular/core/testing'

import { ProfileService } from './profile.service'
import {
  HttpClientTestingModule,
  HttpTestingController,
} from '@angular/common/http/testing'
import { environment } from 'src/environments/environment'

describe('ProfileService', () => {
  let httpTestingController: HttpTestingController
  let service: ProfileService

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [ProfileService],
      imports: [HttpClientTestingModule],
    })

    httpTestingController = TestBed.inject(HttpTestingController)
    service = TestBed.inject(ProfileService)
  })

  afterEach(() => {
    httpTestingController.verify()
  })

  it('calls get profile endpoint', () => {
    service.get().subscribe()
    const req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}profile/`
    )
    expect(req.request.method).toEqual('GET')
  })

  it('calls patch on update', () => {
    service.update({ email: 'foo@bar.com' }).subscribe()
    const req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}profile/`
    )
    expect(req.request.method).toEqual('PATCH')
    expect(req.request.body).toEqual({
      email: 'foo@bar.com',
    })
  })

  it('supports generating new auth token', () => {
    service.generateAuthToken().subscribe()
    const req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}profile/generate_auth_token/`
    )
    expect(req.request.method).toEqual('POST')
  })
})
