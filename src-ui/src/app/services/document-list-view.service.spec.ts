import { provideHttpClient, withInterceptorsFromDi } from '@angular/common/http'
import {
  HttpTestingController,
  provideHttpClientTesting,
} from '@angular/common/http/testing'
import { TestBed } from '@angular/core/testing'
import { Params, Router, convertToParamMap } from '@angular/router'
import { RouterTestingModule } from '@angular/router/testing'
import { Subscription } from 'rxjs'
import { routes } from 'src/app/app-routing.module'
import { environment } from 'src/environments/environment'
import { ConfirmDialogComponent } from '../components/common/confirm-dialog/confirm-dialog.component'
import {
  DEFAULT_DISPLAY_FIELDS,
  DisplayField,
  DisplayMode,
} from '../data/document'
import { FilterRule } from '../data/filter-rule'
import {
  FILTER_HAS_TAGS_ALL,
  FILTER_HAS_TAGS_ANY,
} from '../data/filter-rule-type'
import { SavedView } from '../data/saved-view'
import { SETTINGS_KEYS } from '../data/ui-settings'
import { PermissionsGuard } from '../guards/permissions.guard'
import { DocumentListViewService } from './document-list-view.service'
import { SettingsService } from './settings.service'

const documents = [
  {
    id: 1,
    title: 'Doc 1',
    content: 'some content',
    tags: [1, 2, 3],
    correspondent: 11,
    document_type: 3,
    storage_path: 8,
  },
  {
    id: 2,
    title: 'Doc 2',
    content: 'some content',
  },
  {
    id: 3,
    title: 'Doc 3',
    content: 'some content',
  },
  {
    id: 4,
    title: 'Doc 4',
    content: 'some content',
  },
  {
    id: 5,
    title: 'Doc 5',
    content: 'some content',
  },
  {
    id: 6,
    title: 'Doc 6',
    content: 'some content',
  },
]
const full_results = {
  count: documents.length,
  results: documents,
}

const tags__id__all = '9'
const filterRules: FilterRule[] = [
  {
    rule_type: FILTER_HAS_TAGS_ALL,
    value: tags__id__all,
  },
]

const view: SavedView = {
  id: 3,
  name: 'Saved View',
  sort_field: 'added',
  sort_reverse: true,
  filter_rules: filterRules,
}

describe('DocumentListViewService', () => {
  let httpTestingController: HttpTestingController
  let documentListViewService: DocumentListViewService
  let subscriptions: Subscription[] = []
  let router: Router
  let settingsService: SettingsService

  beforeEach(() => {
    TestBed.configureTestingModule({
      declarations: [ConfirmDialogComponent],
      teardown: { destroyAfterEach: true },
      imports: [RouterTestingModule.withRoutes(routes)],
      providers: [
        DocumentListViewService,
        PermissionsGuard,
        SettingsService,
        provideHttpClient(withInterceptorsFromDi()),
        provideHttpClientTesting(),
      ],
    })

    sessionStorage.clear()
    httpTestingController = TestBed.inject(HttpTestingController)
    documentListViewService = TestBed.inject(DocumentListViewService)
    settingsService = TestBed.inject(SettingsService)
    router = TestBed.inject(Router)
  })

  afterEach(() => {
    documentListViewService.cancelPending()
    httpTestingController.verify()
    sessionStorage.clear()
  })

  afterAll(() => {
    subscriptions?.forEach((subscription) => {
      subscription.unsubscribe()
    })
  })

  it('should reload the list', () => {
    expect(documentListViewService.currentPage).toEqual(1)
    documentListViewService.reload()
    const req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}documents/?page=1&page_size=50&ordering=-created&truncate_content=true`
    )
    expect(req.request.method).toEqual('GET')
    req.flush(full_results)
    httpTestingController.expectOne(
      `${environment.apiBaseUrl}documents/selection_data/`
    )
    expect(req.request.method).toEqual('GET')
    expect(documentListViewService.isReloading).toBeFalsy()
    expect(documentListViewService.activeSavedViewId).toBeNull()
    expect(documentListViewService.activeSavedViewTitle).toBeNull()
    expect(documentListViewService.collectionSize).toEqual(documents.length)
    expect(documentListViewService.getLastPage()).toEqual(1)
  })

  it('should handle error on page request out of range', () => {
    documentListViewService.currentPage = 50
    let req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}documents/?page=50&page_size=50&ordering=-created&truncate_content=true`
    )
    expect(req.request.method).toEqual('GET')
    req.flush([], { status: 404, statusText: 'Unexpected error' })
    req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}documents/?page=1&page_size=50&ordering=-created&truncate_content=true`
    )
    expect(req.request.method).toEqual('GET')
    expect(documentListViewService.currentPage).toEqual(1)
  })

  it('should handle error on filtering request', () => {
    documentListViewService.currentPage = 1
    const tags__id__in = 'hello'
    const filterRulesAny = [
      {
        rule_type: FILTER_HAS_TAGS_ANY,
        value: tags__id__in,
      },
    ]
    documentListViewService.filterRules = filterRulesAny
    let req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}documents/?page=1&page_size=50&ordering=-created&truncate_content=true&tags__id__in=${tags__id__in}`
    )
    expect(req.request.method).toEqual('GET')
    req.flush(
      { archive_serial_number: 'hello' },
      { status: 404, statusText: 'Unexpected error' }
    )
    req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}documents/?page=1&page_size=50&ordering=-created&truncate_content=true`
    )
    expect(req.request.method).toEqual('GET')
    // reset the list
    documentListViewService.filterRules = []
    req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}documents/?page=1&page_size=50&ordering=-created&truncate_content=true`
    )
  })

  it('should support setting sort', () => {
    expect(documentListViewService.sortField).toEqual('created')
    expect(documentListViewService.sortReverse).toBeTruthy()
    documentListViewService.setSort('added', false)
    let req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}documents/?page=1&page_size=50&ordering=added&truncate_content=true`
    )
    expect(req.request.method).toEqual('GET')
    expect(documentListViewService.sortField).toEqual('added')
    expect(documentListViewService.sortReverse).toBeFalsy()

    documentListViewService.sortField = 'created'
    req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}documents/?page=1&page_size=50&ordering=created&truncate_content=true`
    )
    expect(documentListViewService.sortField).toEqual('created')
    documentListViewService.sortReverse = true
    req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}documents/?page=1&page_size=50&ordering=-created&truncate_content=true`
    )
    expect(req.request.method).toEqual('GET')
    expect(documentListViewService.sortReverse).toBeTruthy()
  })

  it('should load from query params', () => {
    expect(documentListViewService.currentPage).toEqual(1)
    const page = 2
    const sort = 'added'
    const reverse = true
    const params: Params = {
      page,
      sort,
      reverse,
    }
    documentListViewService.loadFromQueryParams(convertToParamMap(params))
    const req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}documents/?page=${page}&page_size=${
        documentListViewService.pageSize
      }&ordering=${reverse ? '-' : ''}${sort}&truncate_content=true`
    )
    expect(req.request.method).toEqual('GET')
    expect(documentListViewService.currentPage).toEqual(page)
    expect(documentListViewService.filterRules).toEqual([])
  })

  it('should load filter rules from query params', () => {
    const sort = 'added'
    const reverse = true
    const params: Params = {
      sort,
      reverse,
      tags__id__all,
    }
    documentListViewService.loadFromQueryParams(convertToParamMap(params))
    let req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}documents/?page=${documentListViewService.currentPage}&page_size=${documentListViewService.pageSize}&ordering=-added&truncate_content=true&tags__id__all=${tags__id__all}`
    )
    expect(req.request.method).toEqual('GET')
    expect(documentListViewService.filterRules).toEqual([
      {
        rule_type: FILTER_HAS_TAGS_ALL,
        value: tags__id__all,
      },
    ])
    req.flush(full_results)
    httpTestingController.expectOne(
      `${environment.apiBaseUrl}documents/selection_data/`
    )
  })

  it('should use filter rules to update query params', () => {
    documentListViewService.filterRules = filterRules
    const req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}documents/?page=${documentListViewService.currentPage}&page_size=${documentListViewService.pageSize}&ordering=-created&truncate_content=true&tags__id__all=${tags__id__all}`
    )
    expect(req.request.method).toEqual('GET')
  })

  it('should support quick filter', () => {
    documentListViewService.quickFilter(filterRules)
    const req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}documents/?page=${documentListViewService.currentPage}&page_size=${documentListViewService.pageSize}&ordering=-created&truncate_content=true&tags__id__all=${tags__id__all}`
    )
    expect(req.request.method).toEqual('GET')
  })

  it('should support loading saved view', () => {
    const routerSpy = jest.spyOn(router, 'navigate')
    documentListViewService.activateSavedView(view)
    expect(routerSpy).toHaveBeenCalledWith(['view', view.id])
    documentListViewService.activateSavedView(null)
  })

  it('should support loading saved view view query params', () => {
    const page = 2
    const params: Params = {
      view: view.id,
      page,
    }
    documentListViewService.activateSavedViewWithQueryParams(
      view,
      convertToParamMap(params)
    )
    let req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}documents/?page=${page}&page_size=${documentListViewService.pageSize}&ordering=-added&truncate_content=true&tags__id__all=${tags__id__all}`
    )
    expect(req.request.method).toEqual('GET')
    // reset the list
    documentListViewService.currentPage = 1
    req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}documents/?page=1&page_size=50&ordering=-added&truncate_content=true&tags__id__all=9`
    )
    documentListViewService.filterRules = []
    req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}documents/?page=1&page_size=50&ordering=-added&truncate_content=true`
    )
    documentListViewService.sortField = 'created'
    req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}documents/?page=1&page_size=50&ordering=-created&truncate_content=true`
    )
    documentListViewService.activateSavedView(null)
  })

  it('should support navigating next / previous', () => {
    documentListViewService.filterRules = []
    let req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}documents/?page=1&page_size=50&ordering=-created&truncate_content=true`
    )
    expect(documentListViewService.currentPage).toEqual(1)
    documentListViewService.pageSize = 3
    req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}documents/?page=1&page_size=3&ordering=-created&truncate_content=true`
    )
    expect(req.request.method).toEqual('GET')
    req.flush({
      count: 3,
      results: documents.slice(0, 3),
    })
    httpTestingController
      .expectOne(`${environment.apiBaseUrl}documents/selection_data/`)
      .flush([])
    expect(documentListViewService.hasNext(documents[0].id)).toBeTruthy()
    expect(documentListViewService.hasPrevious(documents[0].id)).toBeFalsy()
    documentListViewService.getNext(documents[0].id).subscribe((docId) => {
      expect(docId).toEqual(documents[1].id)
    })
    documentListViewService.getNext(documents[2].id).subscribe((docId) => {
      expect(docId).toEqual(documents[3].id)
      expect(documentListViewService.currentPage).toEqual(2)
    })
    documentListViewService.getPrevious(documents[3].id).subscribe((docId) => {
      expect(docId).toEqual(documents[2].id)
      expect(documentListViewService.currentPage).toEqual(1)
    })
  })

  it('should not return next doc when documents is null', () => {
    jest
      .spyOn(documentListViewService, 'documents', 'get')
      .mockReturnValue(null)
    const complete = jest.fn()
    documentListViewService.getNext(1).subscribe({
      next: () => fail('Observable should not emit any value'),
      complete: complete(),
    })
    expect(complete).toHaveBeenCalled()
  })

  it('should return next doc when exists', () => {
    jest
      .spyOn(documentListViewService, 'documents', 'get')
      .mockReturnValue(documents)
    const next = jest.fn()
    documentListViewService.getNext(3).subscribe({
      next: (id) => next(id),
      complete: () => {},
    })
    expect(next).toHaveBeenCalledWith(4)
  })

  it('should increase page on get next doc if needed', () => {
    jest
      .spyOn(documentListViewService, 'documents', 'get')
      .mockReturnValue(documents)
    expect(documentListViewService.currentPage).toEqual(1)
    documentListViewService.pageSize = 3
    httpTestingController.match(
      `${environment.apiBaseUrl}documents/?page=1&page_size=3&ordering=-created&truncate_content=true`
    )
    jest
      .spyOn(documentListViewService, 'getLastPage')
      .mockReturnValue(Math.ceil(documents.length / 3))
    const reloadSpy = jest.spyOn(documentListViewService, 'reload')
    documentListViewService
      .getNext(documents[documents.length - 1].id)
      .subscribe({
        next: () => {},
        complete: () => {},
      })
    expect(reloadSpy).toHaveBeenCalled()
    expect(documentListViewService.currentPage).toEqual(2)
    const reqs = httpTestingController.match(
      `${environment.apiBaseUrl}documents/?page=2&page_size=3&ordering=-created&truncate_content=true`
    )
    expect(reqs.length).toBeGreaterThan(0)
  })

  it('should not return previous doc when documents is null', () => {
    jest
      .spyOn(documentListViewService, 'documents', 'get')
      .mockReturnValue(null)
    const complete = jest.fn()
    documentListViewService.getPrevious(1).subscribe({
      next: () => fail('Observable should not emit any value'),
      complete: complete(),
    })
    expect(complete).toHaveBeenCalled()
  })

  it('should return previous doc when exists', () => {
    jest
      .spyOn(documentListViewService, 'documents', 'get')
      .mockReturnValue(documents)
    const next = jest.fn()
    documentListViewService.getPrevious(3).subscribe({
      next: (id) => next(id),
      complete: () => {},
    })
    expect(next).toHaveBeenCalledWith(2)
  })

  it('should decrease page on get previous doc if needed', () => {
    jest
      .spyOn(documentListViewService, 'documents', 'get')
      .mockReturnValue(documents)
    documentListViewService.currentPage = 2
    httpTestingController.match(
      `${environment.apiBaseUrl}documents/?page=2&page_size=50&ordering=-created&truncate_content=true`
    )
    documentListViewService.pageSize = 3
    httpTestingController.match(
      `${environment.apiBaseUrl}documents/?page=2&page_size=3&ordering=-created&truncate_content=true`
    )
    const reloadSpy = jest.spyOn(documentListViewService, 'reload')
    documentListViewService.getPrevious(1).subscribe({
      next: () => {},
      complete: () => {},
    })
    expect(reloadSpy).toHaveBeenCalled()
    expect(documentListViewService.currentPage).toEqual(1)
    const reqs = httpTestingController.match(
      `${environment.apiBaseUrl}documents/?page=1&page_size=3&ordering=-created&truncate_content=true`
    )
    expect(reqs.length).toBeGreaterThan(0)
  })

  it('should update page size from settings', () => {
    settingsService.set(SETTINGS_KEYS.DOCUMENT_LIST_SIZE, 10)
    expect(documentListViewService.pageSize).toEqual(10)
  })

  it('should support select a document', () => {
    documentListViewService.reload()
    const req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}documents/?page=1&page_size=50&ordering=-created&truncate_content=true`
    )
    expect(req.request.method).toEqual('GET')
    req.flush(full_results)
    httpTestingController.expectOne(
      `${environment.apiBaseUrl}documents/selection_data/`
    )
    documentListViewService.toggleSelected(documents[0])
    expect(documentListViewService.isSelected(documents[0])).toBeTruthy()
    documentListViewService.toggleSelected(documents[0])
    expect(documentListViewService.isSelected(documents[0])).toBeFalsy()
  })

  it('should support select all', () => {
    documentListViewService.selectAll()
    const req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}documents/?page=1&page_size=100000&fields=id`
    )
    expect(req.request.method).toEqual('GET')
    req.flush(full_results)
    expect(documentListViewService.selected.size).toEqual(documents.length)
    expect(documentListViewService.isSelected(documents[0])).toBeTruthy()
    documentListViewService.selectNone()
  })

  it('should support select page', () => {
    documentListViewService.pageSize = 3
    const req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}documents/?page=1&page_size=3&ordering=-created&truncate_content=true`
    )
    expect(req.request.method).toEqual('GET')
    req.flush({
      count: 3,
      results: documents.slice(0, 3),
    })
    httpTestingController.expectOne(
      `${environment.apiBaseUrl}documents/selection_data/`
    )
    documentListViewService.selectPage()
    expect(documentListViewService.selected.size).toEqual(3)
    expect(documentListViewService.isSelected(documents[5])).toBeFalsy()
  })

  it('should support select range', () => {
    documentListViewService.reload()
    const req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}documents/?page=1&page_size=50&ordering=-created&truncate_content=true`
    )
    expect(req.request.method).toEqual('GET')
    req.flush(full_results)
    httpTestingController.expectOne(
      `${environment.apiBaseUrl}documents/selection_data/`
    )
    documentListViewService.toggleSelected(documents[0])
    expect(documentListViewService.isSelected(documents[0])).toBeTruthy()
    documentListViewService.selectRangeTo(documents[2])
    expect(documentListViewService.isSelected(documents[1])).toBeTruthy()
    documentListViewService.selectRangeTo(documents[4])
    expect(documentListViewService.isSelected(documents[3])).toBeTruthy()
  })

  it('should support selection range reduction', () => {
    documentListViewService.selectAll()
    let req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}documents/?page=1&page_size=100000&fields=id`
    )
    expect(req.request.method).toEqual('GET')
    req.flush(full_results)
    expect(documentListViewService.selected.size).toEqual(6)

    documentListViewService.filterRules = filterRules
    httpTestingController.expectOne(
      `${environment.apiBaseUrl}documents/?page=1&page_size=50&ordering=-created&truncate_content=true&tags__id__all=9`
    )
    const reqs = httpTestingController.match(
      `${environment.apiBaseUrl}documents/?page=1&page_size=100000&fields=id&tags__id__all=9`
    )
    reqs[0].flush({
      count: 3,
      results: documents.slice(0, 3),
    })
    expect(documentListViewService.selected.size).toEqual(3)
  })

  it('should cancel on reload the list', () => {
    const cancelSpy = jest.spyOn(documentListViewService, 'cancelPending')
    documentListViewService.reload()
    httpTestingController.expectOne(
      `${environment.apiBaseUrl}documents/?page=1&page_size=50&ordering=-created&truncate_content=true&tags__id__all=9`
    )
    expect(cancelSpy).toHaveBeenCalled()
  })

  it('should reset sort field if changing from search result', () => {
    const view2 = {
      id: 22,
      name: 'Saved View 2',
      sort_field: 'score',
      sort_reverse: true,
      filter_rules: filterRules,
    }

    documentListViewService.loadSavedView(view2)
    expect(documentListViewService.sortField).toEqual('score')
    documentListViewService.filterRules = []
    expect(documentListViewService.sortField).toEqual('created')
    httpTestingController.expectOne(
      `${environment.apiBaseUrl}documents/?page=1&page_size=50&ordering=-created&truncate_content=true`
    )
  })

  it('should update default view state when display mode changes', () => {
    const localStorageSpy = jest.spyOn(localStorage, 'setItem')
    expect(documentListViewService.displayMode).toEqual(DisplayMode.SMALL_CARDS)
    documentListViewService.displayMode = DisplayMode.LARGE_CARDS
    expect(documentListViewService.displayMode).toEqual(DisplayMode.LARGE_CARDS)
    documentListViewService.displayMode = 'details' as any // legacy
    expect(documentListViewService.displayMode).toEqual(DisplayMode.TABLE)
    expect(localStorageSpy).toHaveBeenCalledTimes(2)
  })

  it('should update default view state when display fields change', () => {
    const localStorageSpy = jest.spyOn(localStorage, 'setItem')
    documentListViewService.displayFields = [
      DisplayField.ADDED,
      DisplayField.TITLE,
    ]
    expect(documentListViewService.displayFields).toEqual([
      DisplayField.ADDED,
      DisplayField.TITLE,
    ])
    expect(localStorageSpy).toHaveBeenCalled()
    // reload triggered
    httpTestingController.match(
      `${environment.apiBaseUrl}documents/?page=1&page_size=50&ordering=-created&truncate_content=true`
    )
    documentListViewService.displayFields = null
    httpTestingController.match(
      `${environment.apiBaseUrl}documents/?page=1&page_size=50&ordering=-created&truncate_content=true`
    )
    expect(documentListViewService.displayFields).toEqual(
      DEFAULT_DISPLAY_FIELDS.filter((f) => f.id !== DisplayField.ADDED).map(
        (f) => f.id
      )
    )
  })

  it('should not filter out custom fields if settings not initialized', () => {
    const customFields = ['custom_field_1', 'custom_field_2']
    documentListViewService.displayFields = customFields as any
    expect(documentListViewService.displayFields).toEqual(customFields)
    jest.spyOn(settingsService, 'allDisplayFields', 'get').mockReturnValue([
      { id: DisplayField.ADDED, name: 'Added' },
      { id: DisplayField.TITLE, name: 'Title' },
      { id: 'custom_field_1', name: 'Custom Field 1' },
    ] as any)
    settingsService.displayFieldsInit.emit(true)
    expect(documentListViewService.displayFields).toEqual(['custom_field_1'])

    // will now filter on set
    documentListViewService.displayFields = customFields as any
    expect(documentListViewService.displayFields).toEqual(['custom_field_1'])
  })
})
