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
    sort_field: 'title',
    sort_reverse: true,
    filter_rules: [],
  },
  {
    name: 'Saved View 2',
    id: 2,
    show_on_dashboard: true,
    show_in_sidebar: true,
    sort_field: 'created',
    sort_reverse: true,
    filter_rules: [],
  },
  {
    name: 'Saved View 3',
    id: 3,
    show_on_dashboard: true,
    show_in_sidebar: true,
    sort_field: 'added',
    sort_reverse: true,
    filter_rules: [],
  },
  {
    name: 'Saved View 4',
    id: 4,
    show_on_dashboard: false,
    show_in_sidebar: false,
    sort_field: 'owner',
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

  it('should treat empty display_fields as null', () => {
    subscription = service
      .patch({
        id: 1,
        name: 'Saved View',
        show_on_dashboard: true,
        show_in_sidebar: true,
        sort_field: 'name',
        sort_reverse: true,
        filter_rules: [],
        display_fields: [],
      })
      .subscribe()
    const req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}${endpoint}/1/`
    )
    expect(req.request.body.display_fields).toBeNull()
  })

  it('should support patch without reload', () => {
    subscription = service
      .patch(
        {
          id: 1,
          name: 'Saved View',
          show_on_dashboard: true,
          show_in_sidebar: true,
          sort_field: 'name',
          sort_reverse: true,
          filter_rules: [],
        },
        false
      )
      .subscribe()
    const req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}${endpoint}/1/`
    )
    expect(req.request.method).toEqual('PATCH')
    req.flush({})
    httpTestingController.verify() // no reload
  })

  it('should reload after create, delete, patch and patchMany', () => {
    const reloadSpy = jest.spyOn(service, 'reload')
    service
      .create({
        name: 'New Saved View',
        show_on_dashboard: true,
        show_in_sidebar: true,
        sort_field: 'name',
        sort_reverse: true,
        filter_rules: [],
      })
      .subscribe()
    httpTestingController
      .expectOne(`${environment.apiBaseUrl}${endpoint}/`)
      .flush({})
    expect(reloadSpy).toHaveBeenCalled()
    reloadSpy.mockClear()
    httpTestingController
      .expectOne(
        `${environment.apiBaseUrl}${endpoint}/?page=1&page_size=100000`
      )
      .flush({
        results: saved_views,
      })
    service.delete(saved_views[0]).subscribe()
    httpTestingController
      .expectOne(`${environment.apiBaseUrl}${endpoint}/1/`)
      .flush({})
    expect(reloadSpy).toHaveBeenCalled()
    reloadSpy.mockClear()
    httpTestingController
      .expectOne(
        `${environment.apiBaseUrl}${endpoint}/?page=1&page_size=100000`
      )
      .flush({
        results: saved_views,
      })
    service.patch(saved_views[0], true).subscribe()
    httpTestingController
      .expectOne(`${environment.apiBaseUrl}${endpoint}/1/`)
      .flush({})
    expect(reloadSpy).toHaveBeenCalled()
    httpTestingController
      .expectOne(
        `${environment.apiBaseUrl}${endpoint}/?page=1&page_size=100000`
      )
      .flush({
        results: saved_views,
      })
    service.patchMany(saved_views).subscribe()
    saved_views.forEach((saved_view) => {
      const req = httpTestingController.expectOne(
        `${environment.apiBaseUrl}${endpoint}/${saved_view.id}/`
      )
      req.flush({})
    })
    expect(reloadSpy).toHaveBeenCalled()
    httpTestingController
      .expectOne(
        `${environment.apiBaseUrl}${endpoint}/?page=1&page_size=100000`
      )
      .flush({
        results: saved_views,
      })
  })

  it('should accept a callback for reload', () => {
    const reloadSpy = jest.fn()
    service.reload(reloadSpy)
    const req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}${endpoint}/?page=1&page_size=100000`
    )
    req.flush({
      results: saved_views,
    })
    expect(reloadSpy).toHaveBeenCalled()
  })

  it('should support getting document counts for views', () => {
    service.maybeRefreshDocumentCounts(saved_views)
    saved_views.forEach((saved_view) => {
      const req = httpTestingController.expectOne(
        `${environment.apiBaseUrl}documents/?page=1&page_size=1&ordering=-${saved_view.sort_field}&fields=id&truncate_content=true`
      )
      req.flush({
        all: [],
        count: 1,
        results: [{ id: 1 }],
      })
    })
    expect(service.getDocumentCount(saved_views[0])).toEqual(1)
  })

  it('should not refresh document counts if setting is disabled', () => {
    jest.spyOn(settingsService, 'get').mockImplementation((key) => {
      if (key === SETTINGS_KEYS.SIDEBAR_VIEWS_SHOW_COUNT) return false
    })
    service.maybeRefreshDocumentCounts(saved_views)
    httpTestingController.expectNone(
      `${environment.apiBaseUrl}documents/?page=1&page_size=1&ordering=-${saved_views[0].sort_field}&fields=id&truncate_content=true`
    )
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
