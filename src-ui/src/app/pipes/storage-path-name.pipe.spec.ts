import { provideHttpClient, withInterceptorsFromDi } from '@angular/common/http'
import { provideHttpClientTesting } from '@angular/common/http/testing'
import { TestBed } from '@angular/core/testing'
import { PermissionsService } from '../services/permissions.service'
import { AbstractNameFilterService } from '../services/rest/abstract-name-filter-service'
import { StoragePathNamePipe } from './storage-path-name.pipe'

describe('StoragePathNamePipe', () => {
  let pipe: StoragePathNamePipe

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        StoragePathNamePipe,
        { provide: PermissionsService },
        { provide: AbstractNameFilterService },
        provideHttpClient(withInterceptorsFromDi()),
        provideHttpClientTesting(),
      ],
    })
  })

  // The pipe is a simple wrapper around ObjectNamePipe, see ObjectNamePipe for the actual tests.
  it('should be created', () => {
    pipe = TestBed.inject(StoragePathNamePipe)
    expect(pipe).toBeTruthy()
  })
})
