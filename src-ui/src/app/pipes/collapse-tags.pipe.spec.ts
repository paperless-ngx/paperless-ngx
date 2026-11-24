import { provideHttpClient, withInterceptorsFromDi } from '@angular/common/http'
import { provideHttpClientTesting } from '@angular/common/http/testing'
import { TestBed } from '@angular/core/testing'
import { firstValueFrom, of, throwError } from 'rxjs'
import { Tag } from '../data/tag'
import { PermissionsService } from '../services/permissions.service'
import { TagService } from '../services/rest/tag.service'
import { SettingsService } from '../services/settings.service'
import { CollapseTagsPipe } from './collapse-tags.pipe'

const tags: Tag[] = [
  { id: 1, name: 'Parent' },
  { id: 2, name: 'Child', parent: 1 },
  { id: 3, name: 'Other' },
]

describe('CollapseTagsPipe', () => {
  let pipe: CollapseTagsPipe
  let tagService: TagService
  let settingsService: SettingsService
  let permissionsService: PermissionsService

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        CollapseTagsPipe,
        provideHttpClient(withInterceptorsFromDi()),
        provideHttpClientTesting(),
      ],
    })
    pipe = TestBed.inject(CollapseTagsPipe)
    tagService = TestBed.inject(TagService)
    settingsService = TestBed.inject(SettingsService)
    permissionsService = TestBed.inject(PermissionsService)
    jest.spyOn(permissionsService, 'currentUserCan').mockReturnValue(true)
    jest.spyOn(settingsService, 'get').mockReturnValue(true)
    jest
      .spyOn(tagService, 'listAll')
      .mockReturnValue(of({ count: 3, all: [1, 2, 3], results: tags }))
  })

  it('should drop parents implied by a selected child', async () => {
    expect(await firstValueFrom(pipe.transform([1, 2, 3]))).toEqual([2, 3])
  })

  it('should pass ids through when hierarchy display is off or not permitted', async () => {
    jest.spyOn(settingsService, 'get').mockReturnValue(false)
    expect(await firstValueFrom(pipe.transform([1, 2]))).toEqual([1, 2])

    jest.spyOn(settingsService, 'get').mockReturnValue(true)
    jest.spyOn(permissionsService, 'currentUserCan').mockReturnValue(false)
    expect(await firstValueFrom(pipe.transform([1, 2]))).toEqual([1, 2])
    expect(tagService.listAll).not.toHaveBeenCalled()
  })

  it('should handle empty input', async () => {
    expect(await firstValueFrom(pipe.transform(null))).toEqual([])
    expect(await firstValueFrom(pipe.transform([]))).toEqual([])
  })

  it('should fall back to the original ids if tags fail to load', async () => {
    jest
      .spyOn(tagService, 'listAll')
      .mockReturnValue(throwError(() => new Error('failed')))
    expect(await firstValueFrom(pipe.transform([1, 2]))).toEqual([1, 2])
  })
})
