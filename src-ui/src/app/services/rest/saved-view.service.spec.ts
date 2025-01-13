import { HttpTestingController } from '@angular/common/http/testing'
import { TestBed } from '@angular/core/testing'
import { Subscription } from 'rxjs'
import { SETTINGS_KEYS } from 'src/app/data/ui-settings'
import { environment } from 'src/environments/environment'
import { SettingsService } from '../settings.service'
import { commonAbstractPaperlessServiceTests } from './abstract-paperless-service.spec'
import { SavedViewService } from './saved-view.service'

let httpTestingController: HttpTestingController
let service: SavedViewService
let subscription: Subscription
const endpoint = 'saved_views'
const saved_views = [
  {
    name: 'Saved View',
    id: 1,
    show_on_dashboard: true,
    show_in_sidebar: true,
    sort_field: 'name',
    sort_reverse: true,
    filter_rules: [],
  },
  {
    name: 'Saved View 2',
    id: 2,
    show_on_dashboard: true,
    show_in_sidebar: true,
    sort_field: 'name',
    sort_reverse: true,
    filter_rules: [],
  },
  {
    name: 'Saved View 3',
    id: 3,
    show_on_dashboard: true,
    show_in_sidebar: true,
    sort_field: 'name',
    sort_reverse: true,
    filter_rules: [],
  },
  {
    name: 'Saved View 4',
    id: 4,
    show_on_dashboard: false,
    show_in_sidebar: false,
    sort_field: 'name',
    sort_reverse: true,
    filter_rules: [],
  },
]

// run common tests
commonAbstractPaperlessServiceTests(endpoint, SavedViewService)

describe(`Additional service tests for SavedViewService`, () => {
  let settingsService

  it('should retrieve saved views and sort them', () => {
    service.reload()
    const req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}${endpoint}/?page=1&page_size=100000`
    )
    req.flush({
      results: saved_views,
    })
    expect(service.allViews).toHaveLength(4)
    expect(service.dashboardViews).toHaveLength(3)
    expect(service.sidebarViews).toHaveLength(3)
  })

  it('should gracefully handle errors', () => {
    service.reload()
    const req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}${endpoint}/?page=1&page_size=100000`
    )
    req.error(new ErrorEvent('error'))
    expect(service.loading).toBeFalsy()
    expect(service.allViews).toHaveLength(0)
  })

  it('should support patchMany', () => {
    subscription = service.patchMany(saved_views).subscribe()
    saved_views.forEach((saved_view) => {
      const reqs = httpTestingController.match(
        `${environment.apiBaseUrl}${endpoint}/${saved_view.id}/`
      )
      expect(reqs).toHaveLength(1)
      expect(reqs[0].request.method).toEqual('PATCH')
    })
  })

  it('should sort dashboard views', () => {
    service['savedViews'] = saved_views
    jest.spyOn(settingsService, 'get').mockImplementation((key) => {
      if (key === SETTINGS_KEYS.DASHBOARD_VIEWS_SORT_ORDER) return [3, 1, 2]
    })
    expect(service.dashboardViews).toEqual([
      saved_views[2],
      saved_views[0],
      saved_views[1],
    ])
  })

  it('should sort sidebar views', () => {
    service['savedViews'] = saved_views
    jest.spyOn(settingsService, 'get').mockImplementation((key) => {
      if (key === SETTINGS_KEYS.SIDEBAR_VIEWS_SORT_ORDER) return [3, 1, 2]
    })
    expect(service.sidebarViews).toEqual([
      saved_views[2],
      saved_views[0],
      saved_views[1],
    ])
  })

  beforeEach(() => {
    // Dont need to setup again

    httpTestingController = TestBed.inject(HttpTestingController)
    service = TestBed.inject(SavedViewService)
    settingsService = TestBed.inject(SettingsService)
  })

  afterEach(() => {
    subscription?.unsubscribe()
    httpTestingController.verify()
  })
})
