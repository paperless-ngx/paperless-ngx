import { provideHttpClient, withInterceptorsFromDi } from '@angular/common/http'
import { provideHttpClientTesting } from '@angular/common/http/testing'
import { TestBed } from '@angular/core/testing'
import { PermissionsService } from '../services/permissions.service'
import { CorrespondentService } from '../services/rest/correspondent.service'
import { CorrespondentNamePipe } from './correspondent-name.pipe'

describe('CorrespondentNamePipe', () => {
  let pipe: CorrespondentNamePipe

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(withInterceptorsFromDi()),
        provideHttpClientTesting(),
      ],
    })
  })

  // The pipe is a simple wrapper around ObjectNamePipe, see ObjectNamePipe for the actual tests.
  it('should be created', () => {
    pipe = new CorrespondentNamePipe(
      TestBed.inject(PermissionsService),
      TestBed.inject(CorrespondentService)
    )
    expect(pipe).toBeTruthy()
  })
})
