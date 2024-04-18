import { DatePipe } from '@angular/common'
import { HttpClientTestingModule } from '@angular/common/http/testing'
import {
  ComponentFixture,
  TestBed,
  fakeAsync,
  tick,
} from '@angular/core/testing'
import { Router } from '@angular/router'
import { RouterTestingModule } from '@angular/router/testing'
import { NgbModule } from '@ng-bootstrap/ng-bootstrap'
import { of, Subject } from 'rxjs'
import { routes } from 'src/app/app-routing.module'
import {
  FILTER_CORRESPONDENT,
  FILTER_DOCUMENT_TYPE,
  FILTER_HAS_TAGS_ALL,
  FILTER_STORAGE_PATH,
} from 'src/app/data/filter-rule-type'
import {
  DashboardViewMode,
  DocumentDisplayField,
  SavedView,
} from 'src/app/data/saved-view'
import { IfPermissionsDirective } from 'src/app/directives/if-permissions.directive'
import { PermissionsGuard } from 'src/app/guards/permissions.guard'
import { CustomDatePipe } from 'src/app/pipes/custom-date.pipe'
import { DocumentTitlePipe } from 'src/app/pipes/document-title.pipe'
import {
  ConsumerStatusService,
  FileStatus,
} from 'src/app/services/consumer-status.service'
import { DocumentListViewService } from 'src/app/services/document-list-view.service'
import { PermissionsService } from 'src/app/services/permissions.service'
import { DocumentService } from 'src/app/services/rest/document.service'
import { WidgetFrameComponent } from '../widget-frame/widget-frame.component'
import { SavedViewWidgetComponent } from './saved-view-widget.component'
import { By } from '@angular/platform-browser'
import { SafeUrlPipe } from 'src/app/pipes/safeurl.pipe'
import { DragDropModule } from '@angular/cdk/drag-drop'
import { PreviewPopupComponent } from 'src/app/components/common/preview-popup/preview-popup.component'
import { NgxBootstrapIconsModule, allIcons } from 'ngx-bootstrap-icons'
import { CustomFieldsService } from 'src/app/services/rest/custom-fields.service'
import { CustomFieldDataType } from 'src/app/data/custom-field'

const savedView: SavedView = {
  id: 1,
  name: 'Saved View 1',
  sort_field: 'added',
  sort_reverse: true,
  show_in_sidebar: true,
  show_on_dashboard: true,
  filter_rules: [
    {
      rule_type: FILTER_HAS_TAGS_ALL,
      value: '1,2',
    },
  ],
  dashboard_view_limit: 20,
  dashboard_view_mode: DashboardViewMode.TABLE,
  document_display_fields: [
    DocumentDisplayField.CREATED,
    DocumentDisplayField.TITLE,
    DocumentDisplayField.TAGS,
    DocumentDisplayField.CORRESPONDENT,
    DocumentDisplayField.DOCUMENT_TYPE,
    DocumentDisplayField.STORAGE_PATH,
    `${DocumentDisplayField.CUSTOM_FIELD}11` as any,
    `${DocumentDisplayField.CUSTOM_FIELD}15` as any,
  ],
}

const documentResults = [
  {
    id: 2,
    title: 'doc2',
    custom_fields: [
      { id: 1, field: 11, created: new Date(), value: 'custom', document: 2 },
    ],
  },
  {
    id: 3,
    title: 'doc3',
    correspondent: 0,
    custom_fields: [],
  },
  {
    id: 4,
    title: 'doc4',
    custom_fields: [
      { id: 32, field: 3, created: new Date(), value: 'EUR123', document: 4 },
    ],
  },
  {
    id: 5,
    title: 'doc5',
    custom_fields: [
      {
        id: 22,
        field: 15,
        created: new Date(),
        value: [123, 456, 789],
        document: 5,
      },
    ],
  },
]

describe('SavedViewWidgetComponent', () => {
  let component: SavedViewWidgetComponent
  let fixture: ComponentFixture<SavedViewWidgetComponent>
  let documentService: DocumentService
  let consumerStatusService: ConsumerStatusService
  let documentListViewService: DocumentListViewService
  let router: Router

  beforeEach(async () => {
    TestBed.configureTestingModule({
      declarations: [
        SavedViewWidgetComponent,
        WidgetFrameComponent,
        IfPermissionsDirective,
        CustomDatePipe,
        DocumentTitlePipe,
        SafeUrlPipe,
        PreviewPopupComponent,
      ],
      providers: [
        PermissionsGuard,
        DocumentService,
        {
          provide: PermissionsService,
          useValue: {
            currentUserCan: () => true,
          },
        },
        CustomDatePipe,
        DatePipe,
        {
          provide: CustomFieldsService,
          useValue: {
            listAll: () =>
              of({
                all: [3, 11, 15],
                count: 3,
                results: [
                  {
                    id: 3,
                    name: 'Custom field 3',
                    data_type: CustomFieldDataType.Monetary,
                  },
                  {
                    id: 11,
                    name: 'Custom Field 11',
                    data_type: CustomFieldDataType.String,
                  },
                  {
                    id: 15,
                    name: 'Custom Field 15',
                    data_type: CustomFieldDataType.DocumentLink,
                  },
                ],
              }),
          },
        },
      ],
      imports: [
        HttpClientTestingModule,
        NgbModule,
        RouterTestingModule.withRoutes(routes),
        DragDropModule,
        NgxBootstrapIconsModule.pick(allIcons),
      ],
    }).compileComponents()

    documentService = TestBed.inject(DocumentService)
    consumerStatusService = TestBed.inject(ConsumerStatusService)
    documentListViewService = TestBed.inject(DocumentListViewService)
    router = TestBed.inject(Router)
    fixture = TestBed.createComponent(SavedViewWidgetComponent)
    component = fixture.componentInstance
    component.savedView = savedView

    fixture.detectChanges()
  })

  it('should show a list of documents', () => {
    jest.spyOn(documentService, 'listFiltered').mockReturnValue(
      of({
        all: [2, 3],
        count: 2,
        results: documentResults,
      })
    )
    component.ngOnInit()
    fixture.detectChanges()
    expect(fixture.debugElement.nativeElement.textContent).toContain('doc2')
    expect(fixture.debugElement.nativeElement.textContent).toContain('doc3')
    // preview + download buttons
    expect(
      fixture.debugElement.queryAll(By.css('td a.btn'))[0].attributes['href']
    ).toEqual(component.getPreviewUrl(documentResults[0]))
    expect(
      fixture.debugElement.queryAll(By.css('td a.btn'))[1].attributes['href']
    ).toEqual(component.getDownloadUrl(documentResults[0]))
  })

  it('should show preview on mouseover after delay to preload content', fakeAsync(() => {
    jest.spyOn(documentService, 'listFiltered').mockReturnValue(
      of({
        all: [2, 3],
        count: 2,
        results: documentResults,
      })
    )
    component.ngOnInit()
    fixture.detectChanges()
    component.mouseEnterPreviewButton(documentResults[0])
    expect(component.popover.isOpen()).toBeTruthy()
    expect(component.popoverHidden).toBeTruthy()
    tick(600)
    expect(component.popoverHidden).toBeFalsy()
    component.maybeClosePopover()

    component.mouseEnterPreviewButton(documentResults[1])
    tick(100)
    component.mouseLeavePreviewButton()
    component.mouseEnterPreview()
    expect(component.popover.isOpen()).toBeTruthy()
    component.mouseLeavePreview()
    tick(600)
    expect(component.popover.isOpen()).toBeFalsy()
  }))

  it('should call api endpoint and load results', () => {
    const listAllSpy = jest.spyOn(documentService, 'listFiltered')
    listAllSpy.mockReturnValue(
      of({
        all: [2, 3],
        count: 2,
        results: documentResults,
      })
    )
    component.ngOnInit()
    expect(listAllSpy).toHaveBeenCalledWith(
      1,
      20,
      savedView.sort_field,
      savedView.sort_reverse,
      savedView.filter_rules,
      {
        truncate_content: true,
      }
    )
    fixture.detectChanges()
    expect(component.documents).toEqual(documentResults)
  })

  it('should reload on document consumption finished', () => {
    const fileStatusSubject = new Subject<FileStatus>()
    jest
      .spyOn(consumerStatusService, 'onDocumentConsumptionFinished')
      .mockReturnValue(fileStatusSubject)
    const reloadSpy = jest.spyOn(component, 'reload')
    component.ngOnInit()
    fileStatusSubject.next(new FileStatus())
    expect(reloadSpy).toHaveBeenCalled()
  })

  it('should navigate on showAll', () => {
    const routerSpy = jest.spyOn(router, 'navigate')
    component.showAll()
    expect(routerSpy).toHaveBeenCalledWith(['view', savedView.id])
    savedView.show_in_sidebar = false
    component.showAll()
    expect(routerSpy).toHaveBeenCalledWith(['documents'], {
      queryParams: { view: savedView.id },
    })
  })

  it('should navigate to document', () => {
    const routerSpy = jest.spyOn(router, 'navigate')
    component.openDocumentDetail(documentResults[0])
    expect(routerSpy).toHaveBeenCalledWith(['documents', documentResults[0].id])
  })

  it('should navigate via quickfilter on click tag', () => {
    const qfSpy = jest.spyOn(documentListViewService, 'quickFilter')
    component.clickTag(11, new MouseEvent('click'))
    expect(qfSpy).toHaveBeenCalledWith([
      { rule_type: FILTER_HAS_TAGS_ALL, value: '11' },
    ])
    component.clickTag(11) // coverage
  })

  it('should navigate via quickfilter on click correspondent', () => {
    const qfSpy = jest.spyOn(documentListViewService, 'quickFilter')
    component.clickCorrespondent(11, new MouseEvent('click'))
    expect(qfSpy).toHaveBeenCalledWith([
      { rule_type: FILTER_CORRESPONDENT, value: '11' },
    ])
    component.clickCorrespondent(11) // coverage
  })

  it('should navigate via quickfilter on click doc type', () => {
    const qfSpy = jest.spyOn(documentListViewService, 'quickFilter')
    component.clickDocType(11, new MouseEvent('click'))
    expect(qfSpy).toHaveBeenCalledWith([
      { rule_type: FILTER_DOCUMENT_TYPE, value: '11' },
    ])
    component.clickDocType(11) // coverage
  })

  it('should navigate via quickfilter on click storage path', () => {
    const qfSpy = jest.spyOn(documentListViewService, 'quickFilter')
    component.clickStoragePath(11, new MouseEvent('click'))
    expect(qfSpy).toHaveBeenCalledWith([
      { rule_type: FILTER_STORAGE_PATH, value: '11' },
    ])
    component.clickStoragePath(11) // coverage
  })

  it('should get correct column title', () => {
    expect(component.getColumnTitle(DocumentDisplayField.TITLE)).toEqual(
      'Title'
    )
    expect(component.getColumnTitle(DocumentDisplayField.CREATED)).toEqual(
      'Created'
    )
    expect(component.getColumnTitle(DocumentDisplayField.ADDED)).toEqual(
      'Added'
    )
    expect(component.getColumnTitle(DocumentDisplayField.TAGS)).toEqual('Tags')
    expect(
      component.getColumnTitle(DocumentDisplayField.CORRESPONDENT)
    ).toEqual('Correspondent')
    expect(
      component.getColumnTitle(DocumentDisplayField.DOCUMENT_TYPE)
    ).toEqual('Document type')
    expect(component.getColumnTitle(DocumentDisplayField.STORAGE_PATH)).toEqual(
      'Storage path'
    )
  })

  it('should check if column is visible including permissions', () => {
    expect(
      component.visibleColumns.includes(DocumentDisplayField.TITLE)
    ).toBeTruthy()
    expect(
      component.visibleColumns.includes(DocumentDisplayField.CREATED)
    ).toBeTruthy()
    expect(
      component.visibleColumns.includes(DocumentDisplayField.ADDED)
    ).toBeTruthy()
    expect(
      component.visibleColumns.includes(DocumentDisplayField.TAGS)
    ).toBeTruthy()
    expect(
      component.visibleColumns.includes(DocumentDisplayField.CORRESPONDENT)
    ).toBeTruthy()
    expect(
      component.visibleColumns.includes(DocumentDisplayField.DOCUMENT_TYPE)
    ).toBeTruthy()
    expect(
      component.visibleColumns.includes(DocumentDisplayField.STORAGE_PATH)
    ).toBeTruthy()
    expect(
      component.visibleColumns.includes(
        `${DocumentDisplayField.CUSTOM_FIELD}11` as any
      )
    ).toBeTruthy()

    component.visibleColumns = []
    jest
      .spyOn(component.permissionsService, 'currentUserCan')
      .mockReturnValue(false)
    component.ngOnInit()
    expect(
      component.visibleColumns.includes(DocumentDisplayField.TAGS)
    ).toBeFalsy()
    expect(
      component.visibleColumns.includes(DocumentDisplayField.CORRESPONDENT)
    ).toBeFalsy()
    expect(
      component.visibleColumns.includes(DocumentDisplayField.DOCUMENT_TYPE)
    ).toBeFalsy()
    expect(
      component.visibleColumns.includes(DocumentDisplayField.STORAGE_PATH)
    ).toBeFalsy()
    expect(
      component.visibleColumns.includes(
        `${DocumentDisplayField.CUSTOM_FIELD}11` as any
      )
    ).toBeFalsy()
  })

  it('should display monetary custom field value', () => {
    expect(
      component.getMonetaryCustomFieldValue(
        documentResults[2],
        `${DocumentDisplayField.CUSTOM_FIELD}3`
      )
    ).toEqual([123, 'EUR'])
    expect(
      component.getMonetaryCustomFieldValue(
        documentResults[0],
        `${DocumentDisplayField.CUSTOM_FIELD}999`
      )
    ).toEqual([null, null])
  })

  it('should retrieve documents for document link columns', () => {
    const listAllSpy = jest.spyOn(documentService, 'listAll')
    listAllSpy.mockReturnValue(
      of({
        all: [123, 456, 789],
        count: 3,
        results: [
          { id: 123, title: 'doc123' },
          { id: 456, title: 'doc456' },
          { id: 789, title: 'doc789' },
        ],
      })
    )
    jest.spyOn(documentService, 'listFiltered').mockReturnValue(
      of({
        all: [4, 5],
        count: 2,
        results: [documentResults[2], documentResults[3]],
      })
    )
    component.ngOnInit()
    expect(listAllSpy).toHaveBeenCalledWith(null, false, {
      id__in: '123,456,789',
    })
    fixture.detectChanges()
    expect(fixture.debugElement.nativeElement.textContent).toContain('doc123')
    component.maybeGetDocuments() // coverage
  })
})
