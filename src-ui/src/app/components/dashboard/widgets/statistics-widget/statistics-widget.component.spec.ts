import { DragDropModule } from '@angular/cdk/drag-drop'
import { provideHttpClient, withInterceptorsFromDi } from '@angular/common/http'
import {
  HttpTestingController,
  provideHttpClientTesting,
} from '@angular/common/http/testing'
import { ComponentFixture, TestBed } from '@angular/core/testing'
import { RouterTestingModule } from '@angular/router/testing'
import { NgbModule } from '@ng-bootstrap/ng-bootstrap'
import { Subject } from 'rxjs'
import { routes } from 'src/app/app-routing.module'
import { FILTER_MIME_TYPE } from 'src/app/data/filter-rule-type'
import { IfPermissionsDirective } from 'src/app/directives/if-permissions.directive'
import { PermissionsGuard } from 'src/app/guards/permissions.guard'
import { DocumentListViewService } from 'src/app/services/document-list-view.service'
import {
  FileStatus,
  WebsocketStatusService,
} from 'src/app/services/websocket-status.service'
import { environment } from 'src/environments/environment'
import { WidgetFrameComponent } from '../widget-frame/widget-frame.component'
import { StatisticsWidgetComponent } from './statistics-widget.component'

describe('StatisticsWidgetComponent', () => {
  let component: StatisticsWidgetComponent
  let fixture: ComponentFixture<StatisticsWidgetComponent>
  let httpTestingController: HttpTestingController
  let websocketStatusService: WebsocketStatusService
  let documentListViewService: DocumentListViewService
  const fileStatusSubject = new Subject<FileStatus>()

  beforeEach(async () => {
    TestBed.configureTestingModule({
      imports: [
        NgbModule,
        RouterTestingModule.withRoutes(routes),
        DragDropModule,
        StatisticsWidgetComponent,
        WidgetFrameComponent,
        IfPermissionsDirective,
      ],
      providers: [
        PermissionsGuard,
        provideHttpClient(withInterceptorsFromDi()),
        provideHttpClientTesting(),
      ],
    }).compileComponents()

    fixture = TestBed.createComponent(StatisticsWidgetComponent)
    websocketStatusService = TestBed.inject(WebsocketStatusService)
    jest
      .spyOn(websocketStatusService, 'onDocumentConsumptionFinished')
      .mockReturnValue(fileStatusSubject)
    documentListViewService = TestBed.inject(DocumentListViewService)
    component = fixture.componentInstance

    httpTestingController = TestBed.inject(HttpTestingController)

    fixture.detectChanges()
  })

  it('should call api statistics endpoint', () => {
    const req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}statistics/`
    )
    expect(req.request.method).toEqual('GET')
  })

  it('should reload after doc is consumed', () => {
    const reloadSpy = jest.spyOn(component, 'reload')
    fileStatusSubject.next(new FileStatus())
    expect(reloadSpy).toHaveBeenCalled()
  })

  it('should not call statistics endpoint on reload if already loading', () => {
    httpTestingController.expectOne(`${environment.apiBaseUrl}statistics/`)
    component.loading = true
    component.reload()
    httpTestingController.expectNone(`${environment.apiBaseUrl}statistics/`)
  })

  it('should display inbox link with count', () => {
    const mockStats = {
      documents_total: 200,
      documents_inbox: 18,
      inbox_tags: [10],
    }

    const req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}statistics/`
    )

    req.flush(mockStats)
    fixture.detectChanges()

    const goToInboxSpy = jest.spyOn(component, 'goToInbox')

    expect(fixture.nativeElement.textContent.replace(/\s/g, '')).toContain(
      'inbox:18'
    )
    const link = fixture.nativeElement.querySelector('a') as HTMLAnchorElement
    expect(link).not.toBeNull()
    link.click()
    expect(goToInboxSpy).toHaveBeenCalled()
  })

  it('should display mime types with counts', () => {
    const mockStats = {
      documents_total: 200,
      documents_inbox: 18,
      inbox_tags: [10],
      document_file_type_counts: [
        {
          mime_type: 'application/pdf',
          mime_type_count: 160,
        },
        {
          mime_type: 'text/plain',
          mime_type_count: 20,
        },
        {
          mime_type: 'text/csv',
          mime_type_count: 20,
        },
      ],
      character_count: 162312,
    }

    const req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}statistics/`
    )

    req.flush(mockStats)
    fixture.detectChanges()

    expect(fixture.nativeElement.textContent.replace(/\s/g, '')).toContain(
      'PDF(80%)'
    )
    expect(fixture.nativeElement.textContent.replace(/\s/g, '')).toContain(
      'TXT(10%)'
    )
    expect(fixture.nativeElement.textContent.replace(/\s/g, '')).toContain(
      'CSV(10%)'
    )
  })

  it('should limit mime types to 5 max', () => {
    const mockStats = {
      documents_total: 222,
      documents_inbox: 18,
      inbox_tag: 10,
      document_file_type_counts: [
        {
          mime_type: 'application/pdf',
          mime_type_count: 160,
        },
        {
          mime_type: 'text/plain',
          mime_type_count: 20,
        },
        {
          mime_type: 'text/csv',
          mime_type_count: 20,
        },
        {
          mime_type: 'application/vnd.oasis.opendocument.text',
          mime_type_count: 11,
        },
        {
          mime_type: 'application/msword',
          mime_type_count: 9,
        },
        {
          mime_type: 'image/jpeg',
          mime_type_count: 2,
        },
      ],
      character_count: 162312,
    }

    const req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}statistics/`
    )

    req.flush(mockStats)
    fixture.detectChanges()

    expect(fixture.nativeElement.textContent.replace(/\s/g, '')).toContain(
      'PDF(72.1%)'
    )
    expect(fixture.nativeElement.textContent.replace(/\s/g, '')).toContain(
      'TXT(9%)'
    )
    expect(fixture.nativeElement.textContent.replace(/\s/g, '')).toContain(
      'CSV(9%)'
    )
    expect(fixture.nativeElement.textContent.replace(/\s/g, '')).toContain(
      'ODT(5%)'
    )
    expect(fixture.nativeElement.textContent.replace(/\s/g, '')).toContain(
      'Other(0.9%)'
    )
  })

  it('should display the current ASN', () => {
    const mockStats = {
      current_asn: 122,
    }

    const req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}statistics/`
    )

    req.flush(mockStats)
    fixture.detectChanges()

    expect(fixture.nativeElement.textContent.replace(/\s/g, '')).toContain(
      'CurrentASN:122'
    )
  })

  it('should not display the current ASN if it is not available', () => {
    const mockStats = {
      current_asn: 0,
    }

    const req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}statistics/`
    )

    req.flush(mockStats)
    fixture.detectChanges()

    expect(fixture.nativeElement.textContent.replace(/\s/g, '')).not.toContain(
      'CurrentASN:'
    )
  })

  it('should support quick filter by mime type', () => {
    const qfSpy = jest.spyOn(documentListViewService, 'quickFilter')
    component.filterByFileType({
      mime_type: 'application/pdf',
      mime_type_count: 160,
    })
    expect(qfSpy).toHaveBeenCalledWith([
      {
        rule_type: FILTER_MIME_TYPE,
        value: 'application/pdf',
      },
    ])

    qfSpy.mockClear()
    component.filterByFileType({
      mime_type: 'Other',
      mime_type_count: 160,
      is_other: true,
    })
    expect(qfSpy).not.toHaveBeenCalled()
  })
})
