import { provideHttpClient, withInterceptorsFromDi } from '@angular/common/http'
import { provideHttpClientTesting } from '@angular/common/http/testing'
import { TestBed } from '@angular/core/testing'
import { firstValueFrom, of, throwError } from 'rxjs'
import { Tag } from '../data/tag'
import { PermissionsService } from '../services/permissions.service'
import { TagService } from '../services/rest/tag.service'
import { SettingsService } from '../services/settings.service'
import { DisplayTagsPipe } from './display-tags.pipe'

const tags: Tag[] = [
  { id: 1, name: 'Parent' },
  { id: 2, name: 'Child', parent: 1 },
  { id: 3, name: 'Other' },
]

describe('DisplayTagsPipe', () => {
  let pipe: DisplayTagsPipe
  let tagService: TagService
  let settingsService: SettingsService
  let permissionsService: PermissionsService

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        DisplayTagsPipe,
        provideHttpClient(withInterceptorsFromDi()),
        provideHttpClientTesting(),
      ],
    })
    pipe = TestBed.inject(DisplayTagsPipe)
    tagService = TestBed.inject(TagService)
    settingsService = TestBed.inject(SettingsService)
    permissionsService = TestBed.inject(PermissionsService)
    jest.spyOn(permissionsService, 'currentUserCan').mockReturnValue(true)
    jest.spyOn(settingsService, 'get').mockReturnValue(true)
    jest
      .spyOn(tagService, 'listAll')
      .mockReturnValue(of({ count: 3, all: [1, 2, 3], results: tags }))
  })

  it('should split visible and hidden tags, collapsing implied parents', async () => {
    expect(await firstValueFrom(pipe.transform([1, 2, 98, 3]))).toEqual({
      visible: [2, 3],
      hidden: [98],
    })
  })

  it('should not collapse parents when hierarchy display is off', async () => {
    jest.spyOn(settingsService, 'get').mockReturnValue(false)
    expect(await firstValueFrom(pipe.transform([1, 2]))).toEqual({
      visible: [1, 2],
      hidden: [],
    })
  })

  it('should hide all tags without tag view permission', async () => {
    jest.spyOn(permissionsService, 'currentUserCan').mockReturnValue(false)
    expect(await firstValueFrom(pipe.transform([1, 2]))).toEqual({
      visible: [],
      hidden: [1, 2],
    })
    expect(tagService.listAll).not.toHaveBeenCalled()
  })

  it('should handle empty input', async () => {
    const empty = { visible: [], hidden: [] }
    expect(await firstValueFrom(pipe.transform(null))).toEqual(empty)
    expect(await firstValueFrom(pipe.transform([]))).toEqual(empty)
  })

  it('should show the original ids if tags fail to load', async () => {
    jest
      .spyOn(tagService, 'listAll')
      .mockReturnValue(throwError(() => new Error('failed')))
    expect(await firstValueFrom(pipe.transform([1, 2]))).toEqual({
      visible: [1, 2],
      hidden: [],
    })
  })
})
