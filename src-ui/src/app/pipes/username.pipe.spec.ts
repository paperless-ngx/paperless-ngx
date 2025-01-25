import { provideHttpClient, withInterceptorsFromDi } from '@angular/common/http'
import {
  HttpTestingController,
  provideHttpClientTesting,
} from '@angular/common/http/testing'
import { TestBed } from '@angular/core/testing'
import { environment } from 'src/environments/environment'
import { PermissionsService } from '../services/permissions.service'
import { UsernamePipe } from './username.pipe'

describe('UsernamePipe', () => {
  let pipe: UsernamePipe
  let httpTestingController: HttpTestingController
  let permissionsService: PermissionsService

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [],
      providers: [
        UsernamePipe,
        PermissionsService,
        provideHttpClient(withInterceptorsFromDi()),
        provideHttpClientTesting(),
      ],
    })

    httpTestingController = TestBed.inject(HttpTestingController)
    permissionsService = TestBed.inject(PermissionsService)
    const permissionsSpy = jest.spyOn(permissionsService, 'currentUserCan')
    permissionsSpy.mockImplementation((action, type) => {
      return true
    })
    pipe = TestBed.inject(UsernamePipe)
  })

  afterEach(() => {
    httpTestingController.verify()
  })

  it('should transform user id to username', (done) => {
    pipe.transform(2).subscribe((username) => {
      expect(username).toEqual('username2')
    })

    const req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}users/?page=1&page_size=100000`
    )
    req.flush({
      results: [
        {
          id: 2,
          username: 'username2',
        },
        {
          id: 3,
          username: 'username3',
          first_name: 'User',
          last_name: 'Name3',
        },
      ],
    })
    pipe.transform(3).subscribe((username) => {
      expect(username).toEqual('User Name3')
    })

    pipe.transform(4).subscribe((username) => {
      expect(username).toEqual('')
      done()
    })
  })

  it('should show generic label when insufficient permissions', (done) => {
    jest
      .spyOn(permissionsService, 'currentUserCan')
      .mockImplementation((action, type) => {
        return false
      })
    pipe.transform(4).subscribe((username) => {
      expect(username).toEqual('Shared')
      done()
    })
    httpTestingController.expectNone(
      `${environment.apiBaseUrl}users/?page=1&page_size=100000`
    )
  })

  it('should show empty string when no users retrieved due to error', (done) => {
    pipe.transform(4).subscribe((username) => {
      expect(username).toEqual('')
      done()
    })
    const req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}users/?page=1&page_size=100000`
    )
    req.error(new ProgressEvent('error'))
  })
})
