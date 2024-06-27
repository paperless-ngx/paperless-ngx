import {
  HttpTestingController,
  provideHttpClientTesting,
} from '@angular/common/http/testing'
import { Subscription } from 'rxjs'
import { TestBed } from '@angular/core/testing'
import { environment } from 'src/environments/environment'
import { SearchService } from './search.service'
import { SettingsService } from '../settings.service'
import { SETTINGS_KEYS } from 'src/app/data/ui-settings'
import { provideHttpClient, withInterceptorsFromDi } from '@angular/common/http'

let httpTestingController: HttpTestingController
let service: SearchService
let subscription: Subscription
let settingsService: SettingsService
const endpoint = 'search/autocomplete'

describe('SearchService', () => {
  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [],
      providers: [
        SearchService,
        provideHttpClient(withInterceptorsFromDi()),
        provideHttpClientTesting(),
      ],
    })

    httpTestingController = TestBed.inject(HttpTestingController)
    settingsService = TestBed.inject(SettingsService)
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

  it('should call correct api endpoint on globalSearch', () => {
    const query = 'apple'
    service.globalSearch(query).subscribe()
    httpTestingController.expectOne(
      `${environment.apiBaseUrl}search/?query=${query}`
    )

    settingsService.set(SETTINGS_KEYS.SEARCH_DB_ONLY, true)
    subscription = service.globalSearch(query).subscribe()
    httpTestingController.expectOne(
      `${environment.apiBaseUrl}search/?query=${query}&db_only=true`
    )
  })
})
