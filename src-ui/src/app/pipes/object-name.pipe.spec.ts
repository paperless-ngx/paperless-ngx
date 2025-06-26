import { provideHttpClient, withInterceptorsFromDi } from '@angular/common/http'
import { provideHttpClientTesting } from '@angular/common/http/testing'
import { TestBed } from '@angular/core/testing'
import { of, throwError } from 'rxjs'
import { MatchingModel } from '../data/matching-model'
import { PermissionsService } from '../services/permissions.service'
import { AbstractNameFilterService } from '../services/rest/abstract-name-filter-service'
import { CorrespondentService } from '../services/rest/correspondent.service'
import { CorrespondentNamePipe } from './correspondent-name.pipe'

describe('ObjectNamePipe', () => {
  /*
    ObjectNamePipe is an abstract class to prevent instantiation,
    so we test the concrete implementation CorrespondentNamePipe instead.
  */
  let pipe: CorrespondentNamePipe
  let permissionsService: PermissionsService
  let objectService: AbstractNameFilterService<MatchingModel>

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        CorrespondentNamePipe,
        { provide: PermissionsService },
        { provide: CorrespondentService },
        provideHttpClient(withInterceptorsFromDi()),
        provideHttpClientTesting(),
      ],
    })

    permissionsService = TestBed.inject(PermissionsService)
    objectService = TestBed.inject(CorrespondentService)
    pipe = TestBed.inject(CorrespondentNamePipe)
  })

  it('should return object name if user has permission', (done) => {
    const mockObjects = {
      results: [
        { id: 1, name: 'Object 1' },
        { id: 2, name: 'Object 2' },
      ],
      count: 2,
      all: [1, 2],
    }
    jest.spyOn(permissionsService, 'currentUserCan').mockReturnValue(true)
    jest.spyOn(objectService, 'listAll').mockReturnValue(of(mockObjects))

    pipe.transform(1).subscribe((result) => {
      expect(result).toBe('Object 1')
      done()
    })
  })

  it('should return Private string if object not found', (done) => {
    const mockObjects = {
      results: [{ id: 2, name: 'Object 2' }],
      count: 1,
      all: [2],
    }
    jest.spyOn(permissionsService, 'currentUserCan').mockReturnValue(true)
    jest.spyOn(objectService, 'listAll').mockReturnValue(of(mockObjects))

    pipe.transform(1).subscribe((result) => {
      expect(result).toBe('Private')
      done()
    })
  })

  it('should return "Private" if user does not have permission', (done) => {
    jest.spyOn(permissionsService, 'currentUserCan').mockReturnValue(false)

    pipe.transform(1).subscribe((result) => {
      expect(result).toBe('Private')
      done()
    })
  })

  it('should handle error and return empty string', (done) => {
    jest.spyOn(permissionsService, 'currentUserCan').mockReturnValue(true)
    jest
      .spyOn(objectService, 'listAll')
      .mockReturnValueOnce(throwError(() => new Error('Error getting objects')))

    pipe.transform(1).subscribe((result) => {
      expect(result).toBe('')
      done()
    })
  })
})
