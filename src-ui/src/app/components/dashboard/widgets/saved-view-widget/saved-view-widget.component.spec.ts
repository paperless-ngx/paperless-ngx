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
import { FILTER_HAS_TAGS_ALL } from 'src/app/data/filter-rule-type'
import { SavedView } from 'src/app/data/saved-view'
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
}

const documentResults = [
  {
    id: 2,
    title: 'doc2',
  },
  {
    id: 3,
    title: 'doc3',
    correspondent: 0,
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
      10,
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

  it('should navigate via quickfilter on click tag', () => {
    const qfSpy = jest.spyOn(documentListViewService, 'quickFilter')
    component.clickTag({ id: 11, name: 'Tag11' }, new MouseEvent('click'))
    expect(qfSpy).toHaveBeenCalledWith([
      { rule_type: FILTER_HAS_TAGS_ALL, value: '11' },
    ])
  })
})
