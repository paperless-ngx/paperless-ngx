import { ComponentFixture, TestBed } from '@angular/core/testing'
import { DocumentListComponent } from './document-list.component'
import { HttpClientTestingModule } from '@angular/common/http/testing'
import { RouterTestingModule } from '@angular/router/testing'
import { routes } from 'src/app/app-routing.module'
import { FilterEditorComponent } from './filter-editor/filter-editor.component'
import { PermissionsFilterDropdownComponent } from '../common/permissions-filter-dropdown/permissions-filter-dropdown.component'
import { DateDropdownComponent } from '../common/date-dropdown/date-dropdown.component'
import { FilterableDropdownComponent } from '../common/filterable-dropdown/filterable-dropdown.component'
import { PageHeaderComponent } from '../common/page-header/page-header.component'
import { BulkEditorComponent } from './bulk-editor/bulk-editor.component'
import { FilterPipe } from 'src/app/pipes/filter.pipe'
import {
  NgbDatepickerModule,
  NgbDropdown,
  NgbDropdownItem,
  NgbDropdownModule,
  NgbModal,
  NgbModalRef,
  NgbPopoverModule,
  NgbTooltipModule,
} from '@ng-bootstrap/ng-bootstrap'
import { ClearableBadgeComponent } from '../common/clearable-badge/clearable-badge.component'
import { FormsModule, ReactiveFormsModule } from '@angular/forms'
import { IfPermissionsDirective } from 'src/app/directives/if-permissions.directive'
import { ToggleableDropdownButtonComponent } from '../common/filterable-dropdown/toggleable-dropdown-button/toggleable-dropdown-button.component'
import { CustomDatePipe } from 'src/app/pipes/custom-date.pipe'
import { DatePipe } from '@angular/common'
import { DocumentListViewService } from 'src/app/services/document-list-view.service'
import {
  ConsumerStatusService,
  FileStatus,
} from 'src/app/services/consumer-status.service'
import { Subject, of, throwError } from 'rxjs'
import { SavedViewService } from 'src/app/services/rest/saved-view.service'
import { ActivatedRoute, Router, convertToParamMap } from '@angular/router'
import { SavedView } from 'src/app/data/saved-view'
import {
  FILTER_FULLTEXT_MORELIKE,
  FILTER_FULLTEXT_QUERY,
  FILTER_HAS_TAGS_ANY,
} from 'src/app/data/filter-rule-type'
import { By } from '@angular/platform-browser'
import { SortableDirective } from 'src/app/directives/sortable.directive'
import { ToastService } from 'src/app/services/toast.service'
import { DocumentCardSmallComponent } from './document-card-small/document-card-small.component'
import { DocumentCardLargeComponent } from './document-card-large/document-card-large.component'
import { DocumentTitlePipe } from 'src/app/pipes/document-title.pipe'
import { UsernamePipe } from 'src/app/pipes/username.pipe'
import { Document } from 'src/app/data/document'
import {
  DOCUMENT_SORT_FIELDS,
  DOCUMENT_SORT_FIELDS_FULLTEXT,
  DocumentService,
} from 'src/app/services/rest/document.service'
import { ConfirmDialogComponent } from '../common/confirm-dialog/confirm-dialog.component'
import { SafeHtmlPipe } from 'src/app/pipes/safehtml.pipe'
import { SaveViewConfigDialogComponent } from './save-view-config-dialog/save-view-config-dialog.component'
import { TextComponent } from '../common/input/text/text.component'
import { CheckComponent } from '../common/input/check/check.component'
import { HttpErrorResponse } from '@angular/common/http'
import { PermissionsGuard } from 'src/app/guards/permissions.guard'
import { SettingsService } from 'src/app/services/settings.service'
import { SETTINGS_KEYS } from 'src/app/data/ui-settings'
import { IsNumberPipe } from 'src/app/pipes/is-number.pipe'
import { NgxBootstrapIconsModule, allIcons } from 'ngx-bootstrap-icons'

const docs: Document[] = [
  {
    id: 1,
    title: 'Doc1',
    notes: [],
    tags$: new Subject(),
    content: 'document content 1',
  },
  {
    id: 2,
    title: 'Doc2',
    notes: [],
    tags$: new Subject(),
    content: 'document content 2',
  },
  {
    id: 3,
    title: 'Doc3',
    notes: [],
    tags$: new Subject(),
    content: 'document content 3',
  },
]

describe('DocumentListComponent', () => {
  let component: DocumentListComponent
  let fixture: ComponentFixture<DocumentListComponent>
  let documentListService: DocumentListViewService
  let documentService: DocumentService
  let consumerStatusService: ConsumerStatusService
  let savedViewService: SavedViewService
  let router: Router
  let activatedRoute: ActivatedRoute
  let toastService: ToastService
  let modalService: NgbModal
  let settingsService: SettingsService

  beforeEach(async () => {
    TestBed.configureTestingModule({
      declarations: [
        DocumentListComponent,
        PageHeaderComponent,
        FilterEditorComponent,
        FilterableDropdownComponent,
        DateDropdownComponent,
        PermissionsFilterDropdownComponent,
        ToggleableDropdownButtonComponent,
        BulkEditorComponent,
        ClearableBadgeComponent,
        DocumentCardSmallComponent,
        DocumentCardLargeComponent,
        ConfirmDialogComponent,
        SaveViewConfigDialogComponent,
        TextComponent,
        CheckComponent,
        IfPermissionsDirective,
        FilterPipe,
        CustomDatePipe,
        SortableDirective,
        DocumentTitlePipe,
        UsernamePipe,
        SafeHtmlPipe,
        IsNumberPipe,
      ],
      providers: [
        FilterPipe,
        CustomDatePipe,
        DatePipe,
        DocumentTitlePipe,
        UsernamePipe,
        SafeHtmlPipe,
        PermissionsGuard,
      ],
      imports: [
        HttpClientTestingModule,
        RouterTestingModule.withRoutes(routes),
        FormsModule,
        ReactiveFormsModule,
        NgbDropdownModule,
        NgbDatepickerModule,
        NgbPopoverModule,
        NgbTooltipModule,
        NgxBootstrapIconsModule.pick(allIcons),
      ],
    }).compileComponents()

    documentListService = TestBed.inject(DocumentListViewService)
    documentService = TestBed.inject(DocumentService)
    consumerStatusService = TestBed.inject(ConsumerStatusService)
    savedViewService = TestBed.inject(SavedViewService)
    router = TestBed.inject(Router)
    activatedRoute = TestBed.inject(ActivatedRoute)
    toastService = TestBed.inject(ToastService)
    modalService = TestBed.inject(NgbModal)
    settingsService = TestBed.inject(SettingsService)
    fixture = TestBed.createComponent(DocumentListComponent)
    component = fixture.componentInstance
  })

  it('should load display mode from local storage', () => {
    window.localStorage.setItem('document-list:displayMode', 'largeCards')
    fixture.detectChanges()
    expect(component.displayMode).toEqual('largeCards')
    component.displayMode = 'smallCards'
    component.saveDisplayMode()
    expect(window.localStorage.getItem('document-list:displayMode')).toEqual(
      'smallCards'
    )
  })

  it('should reload on new document consumed', () => {
    const reloadSpy = jest.spyOn(documentListService, 'reload')
    const fileStatusSubject = new Subject<FileStatus>()
    jest
      .spyOn(consumerStatusService, 'onDocumentConsumptionFinished')
      .mockReturnValue(fileStatusSubject)
    fixture.detectChanges()
    fileStatusSubject.next(new FileStatus())
    expect(reloadSpy).toHaveBeenCalled()
  })

  it('should show score sort fields on fulltext queries', () => {
    documentListService.filterRules = [
      {
        rule_type: FILTER_HAS_TAGS_ANY,
        value: '10',
      },
    ]
    fixture.detectChanges()
    expect(component.getSortFields()).toEqual(DOCUMENT_SORT_FIELDS)

    documentListService.filterRules = [
      {
        rule_type: FILTER_FULLTEXT_QUERY,
        value: 'foo',
      },
    ]
    fixture.detectChanges()
    expect(component.getSortFields()).toEqual(DOCUMENT_SORT_FIELDS_FULLTEXT)
  })

  it('should determine if filtered, support reset', () => {
    fixture.detectChanges()
    documentListService.filterRules = [
      {
        rule_type: FILTER_HAS_TAGS_ANY,
        value: '10',
      },
    ]
    documentListService.isReloading = false
    fixture.detectChanges()
    expect(component.isFiltered).toBeTruthy()
    expect(fixture.nativeElement.textContent.match(/Reset/g)).toHaveLength(2)
    component.resetFilters()
    fixture.detectChanges()
    expect(fixture.nativeElement.textContent.match(/Reset/g)).toHaveLength(1)
  })

  it('should load saved view from URL', () => {
    const view: SavedView = {
      id: 10,
      sort_field: 'added',
      sort_reverse: true,
      filter_rules: [
        {
          rule_type: FILTER_HAS_TAGS_ANY,
          value: '20',
        },
      ],
    }
    const queryParams = { id: view.id.toString() }
    const getSavedViewSpy = jest.spyOn(savedViewService, 'getCached')
    getSavedViewSpy.mockReturnValue(of(view))
    const activateSavedViewSpy = jest.spyOn(
      documentListService,
      'activateSavedViewWithQueryParams'
    )
    activateSavedViewSpy.mockImplementation((view, params) => {})
    jest
      .spyOn(activatedRoute, 'paramMap', 'get')
      .mockReturnValue(of(convertToParamMap(queryParams)))
    activatedRoute.snapshot.queryParams = queryParams
    fixture.detectChanges()
    expect(getSavedViewSpy).toHaveBeenCalledWith(view.id)
    expect(activateSavedViewSpy).toHaveBeenCalledWith(
      view,
      convertToParamMap(queryParams)
    )
  })

  it('should 404 on load saved view from URL if no view', () => {
    jest.spyOn(savedViewService, 'getCached').mockReturnValue(of(null)) // e.g. no saved view found
    jest
      .spyOn(activatedRoute, 'paramMap', 'get')
      .mockReturnValue(of(convertToParamMap({ id: '10' })))
    const navigateSpy = jest.spyOn(router, 'navigate')
    fixture.detectChanges()
    expect(navigateSpy).toHaveBeenCalledWith(['404'], { replaceUrl: true })
  })

  it('should load saved view from query params', () => {
    const view: SavedView = {
      id: 10,
      sort_field: 'added',
      sort_reverse: true,
      filter_rules: [
        {
          rule_type: FILTER_HAS_TAGS_ANY,
          value: '20',
        },
      ],
    }
    const getSavedViewSpy = jest.spyOn(savedViewService, 'getCached')
    getSavedViewSpy.mockReturnValue(of(view))
    jest
      .spyOn(activatedRoute, 'queryParamMap', 'get')
      .mockReturnValue(of(convertToParamMap({ view: view.id.toString() })))
    fixture.detectChanges()
    expect(getSavedViewSpy).toHaveBeenCalledWith(view.id)
  })

  it('should support 3 different display modes', () => {
    jest.spyOn(documentListService, 'documents', 'get').mockReturnValue(docs)
    fixture.detectChanges()
    const displayModeButtons = fixture.debugElement.queryAll(
      By.css('input[type="radio"]')
    )
    expect(component.displayMode).toEqual('smallCards')

    displayModeButtons[0].nativeElement.checked = true
    displayModeButtons[0].triggerEventHandler('change')
    fixture.detectChanges()
    expect(component.displayMode).toEqual('details')
    expect(fixture.debugElement.queryAll(By.css('tr'))).toHaveLength(3)

    displayModeButtons[1].nativeElement.checked = true
    displayModeButtons[1].triggerEventHandler('change')
    fixture.detectChanges()
    expect(component.displayMode).toEqual('smallCards')
    expect(
      fixture.debugElement.queryAll(By.directive(DocumentCardSmallComponent))
    ).toHaveLength(3)

    displayModeButtons[2].nativeElement.checked = true
    displayModeButtons[2].triggerEventHandler('change')
    fixture.detectChanges()
    expect(component.displayMode).toEqual('largeCards')
    expect(
      fixture.debugElement.queryAll(By.directive(DocumentCardLargeComponent))
    ).toHaveLength(3)
  })

  it('should support setting sort field', () => {
    expect(documentListService.sortField).toEqual('created')
    fixture.detectChanges()
    const sortDropdown = fixture.debugElement.queryAll(
      By.directive(NgbDropdown)
    )[1]
    const asnSortFieldButton = sortDropdown.query(By.directive(NgbDropdownItem))

    asnSortFieldButton.triggerEventHandler('click')
    fixture.detectChanges()
    expect(documentListService.sortField).toEqual('archive_serial_number')
    documentListService.sortField = 'created'
  })

  it('should support setting sort field by table head', () => {
    jest.spyOn(documentListService, 'documents', 'get').mockReturnValue(docs)
    fixture.detectChanges()
    expect(documentListService.sortField).toEqual('created')

    const detailsDisplayModeButton = fixture.debugElement.query(
      By.css('input[type="radio"]')
    )
    detailsDisplayModeButton.nativeElement.checked = true
    detailsDisplayModeButton.triggerEventHandler('change')
    fixture.detectChanges()
    expect(component.displayMode).toEqual('details')

    const sortTh = fixture.debugElement.query(By.directive(SortableDirective))
    sortTh.triggerEventHandler('click')
    fixture.detectChanges()
    expect(documentListService.sortField).toEqual('archive_serial_number')
    documentListService.sortField = 'created'
    expect(documentListService.sortReverse).toBeFalsy()
    component.listSortReverse = true
    expect(documentListService.sortReverse).toBeTruthy()
  })

  it('should support select all, none, page & range', () => {
    jest.spyOn(documentListService, 'documents', 'get').mockReturnValue(docs)
    jest
      .spyOn(documentService, 'listAllFilteredIds')
      .mockReturnValue(of(docs.map((d) => d.id)))
    fixture.detectChanges()
    expect(documentListService.selected.size).toEqual(0)
    const docCards = fixture.debugElement.queryAll(
      By.directive(DocumentCardLargeComponent)
    )
    const displayModeButtons = fixture.debugElement.queryAll(
      By.directive(NgbDropdownItem)
    )

    const selectAllSpy = jest.spyOn(documentListService, 'selectAll')
    displayModeButtons[2].triggerEventHandler('click')
    expect(selectAllSpy).toHaveBeenCalled()
    fixture.detectChanges()
    expect(documentListService.selected.size).toEqual(3)
    docCards.forEach((card) => {
      expect(card.context.selected).toBeTruthy()
    })

    const selectNoneSpy = jest.spyOn(documentListService, 'selectNone')
    displayModeButtons[0].triggerEventHandler('click')
    expect(selectNoneSpy).toHaveBeenCalled()
    fixture.detectChanges()
    expect(documentListService.selected.size).toEqual(0)
    docCards.forEach((card) => {
      expect(card.context.selected).toBeFalsy()
    })

    const selectPageSpy = jest.spyOn(documentListService, 'selectPage')
    displayModeButtons[1].triggerEventHandler('click')
    expect(selectPageSpy).toHaveBeenCalled()
    fixture.detectChanges()
    expect(documentListService.selected.size).toEqual(3)
    docCards.forEach((card) => {
      expect(card.context.selected).toBeTruthy()
    })

    component.toggleSelected(docs[0], new MouseEvent('click'))
    fixture.detectChanges()
    expect(documentListService.selected.size).toEqual(2)
    // reset
    displayModeButtons[0].triggerEventHandler('click')
    fixture.detectChanges()
    expect(documentListService.selected.size).toEqual(0)

    // select a range
    component.toggleSelected(docs[0], new MouseEvent('click'))
    component.toggleSelected(
      docs[2],
      new MouseEvent('click', { shiftKey: true })
    )
    fixture.detectChanges()
    expect(documentListService.selected.size).toEqual(3)
  })

  it('should support saving an edited view', () => {
    const view: SavedView = {
      id: 10,
      name: 'Saved View 10',
      sort_field: 'added',
      sort_reverse: true,
      filter_rules: [
        {
          rule_type: FILTER_HAS_TAGS_ANY,
          value: '20',
        },
      ],
    }
    jest.spyOn(savedViewService, 'getCached').mockReturnValue(of(view))
    const queryParams = { view: view.id.toString() }
    jest
      .spyOn(activatedRoute, 'queryParamMap', 'get')
      .mockReturnValue(of(convertToParamMap(queryParams)))
    activatedRoute.snapshot.queryParams = queryParams
    router.routerState.snapshot.url = '/view/10/'
    fixture.detectChanges()
    expect(documentListService.activeSavedViewId).toEqual(10)

    const modifiedView = Object.assign({}, view)
    delete modifiedView.name
    const savedViewServicePatch = jest.spyOn(savedViewService, 'patch')
    savedViewServicePatch.mockReturnValue(of(modifiedView))
    const toastSpy = jest.spyOn(toastService, 'showInfo')

    component.saveViewConfig()
    expect(savedViewServicePatch).toHaveBeenCalledWith(modifiedView)
    expect(toastSpy).toHaveBeenCalledWith(
      `View "${view.name}" saved successfully.`
    )
  })

  it('should support edited view saving as', () => {
    const view: SavedView = {
      id: 10,
      name: 'Saved View 10',
      sort_field: 'added',
      sort_reverse: true,
      filter_rules: [
        {
          rule_type: FILTER_HAS_TAGS_ANY,
          value: '20',
        },
      ],
    }
    jest.spyOn(savedViewService, 'getCached').mockReturnValue(of(view))
    const queryParams = { view: view.id.toString() }
    jest
      .spyOn(activatedRoute, 'queryParamMap', 'get')
      .mockReturnValue(of(convertToParamMap(queryParams)))
    activatedRoute.snapshot.queryParams = queryParams
    router.routerState.snapshot.url = '/view/10/'
    fixture.detectChanges()
    expect(documentListService.activeSavedViewId).toEqual(10)

    const modifiedView = Object.assign({}, view)
    modifiedView.name = 'Foo Bar'

    let openModal: NgbModalRef
    modalService.activeInstances.subscribe((modal) => (openModal = modal[0]))
    const modalSpy = jest.spyOn(modalService, 'open')
    const toastSpy = jest.spyOn(toastService, 'showInfo')
    const savedViewServiceCreate = jest.spyOn(savedViewService, 'create')
    savedViewServiceCreate.mockReturnValueOnce(of(modifiedView))
    component.saveViewConfigAs()

    const modalCloseSpy = jest.spyOn(openModal, 'close')
    openModal.componentInstance.saveClicked.next({
      name: 'Foo Bar',
      show_on_dashboard: true,
      show_in_sidebar: true,
    })
    expect(savedViewServiceCreate).toHaveBeenCalled()
    expect(modalSpy).toHaveBeenCalled()
    expect(toastSpy).toHaveBeenCalled()
    expect(modalCloseSpy).toHaveBeenCalled()
  })

  it('should handle error on edited view saving as', () => {
    const view: SavedView = {
      id: 10,
      name: 'Saved View 10',
      sort_field: 'added',
      sort_reverse: true,
      filter_rules: [
        {
          rule_type: FILTER_HAS_TAGS_ANY,
          value: '20',
        },
      ],
    }
    jest.spyOn(savedViewService, 'getCached').mockReturnValue(of(view))
    const queryParams = { view: view.id.toString() }
    jest
      .spyOn(activatedRoute, 'queryParamMap', 'get')
      .mockReturnValue(of(convertToParamMap(queryParams)))
    activatedRoute.snapshot.queryParams = queryParams
    router.routerState.snapshot.url = '/view/10/'
    fixture.detectChanges()
    expect(documentListService.activeSavedViewId).toEqual(10)

    const modifiedView = Object.assign({}, view)
    modifiedView.name = 'Foo Bar'

    let openModal: NgbModalRef
    modalService.activeInstances.subscribe((modal) => (openModal = modal[0]))
    jest.spyOn(savedViewService, 'create').mockReturnValueOnce(
      throwError(
        () =>
          new HttpErrorResponse({
            error: { filter_rules: [{ value: '11' }] },
          })
      )
    )
    component.saveViewConfigAs()

    openModal.componentInstance.saveClicked.next({
      name: 'Foo Bar',
      show_on_dashboard: true,
      show_in_sidebar: true,
    })
    expect(openModal.componentInstance.error).toEqual({ filter_rules: ['11'] })
  })

  it('should navigate to a document', () => {
    fixture.detectChanges()
    const routerSpy = jest.spyOn(router, 'navigate')
    component.openDocumentDetail({ id: 99 })
    expect(routerSpy).toHaveBeenCalledWith(['documents', 99])
  })

  it('should support checking if notes enabled to hide column', () => {
    jest.spyOn(documentListService, 'documents', 'get').mockReturnValue(docs)
    fixture.detectChanges()
    expect(documentListService.sortField).toEqual('created')

    const detailsDisplayModeButton = fixture.debugElement.query(
      By.css('input[type="radio"]')
    )
    detailsDisplayModeButton.nativeElement.checked = true
    detailsDisplayModeButton.triggerEventHandler('change')
    fixture.detectChanges()
    expect(component.displayMode).toEqual('details')

    expect(
      fixture.debugElement.queryAll(By.directive(SortableDirective))
    ).toHaveLength(9)

    expect(component.notesEnabled).toBeTruthy()
    settingsService.set(SETTINGS_KEYS.NOTES_ENABLED, false)
    fixture.detectChanges()
    expect(component.notesEnabled).toBeFalsy()
    expect(
      fixture.debugElement.queryAll(By.directive(SortableDirective))
    ).toHaveLength(8)
  })

  it('should support toggle on document objects', () => {
    // TODO: this is just for coverage atm
    fixture.detectChanges()
    component.clickTag(1)
    component.clickCorrespondent(2)
    component.clickDocumentType(3)
    component.clickStoragePath(4)
  })

  it('should support quick filter on document more like', () => {
    fixture.detectChanges()
    const qfSpy = jest.spyOn(documentListService, 'quickFilter')
    component.clickMoreLike(99)
    expect(qfSpy).toHaveBeenCalledWith([
      { rule_type: FILTER_FULLTEXT_MORELIKE, value: '99' },
    ])
  })
})
