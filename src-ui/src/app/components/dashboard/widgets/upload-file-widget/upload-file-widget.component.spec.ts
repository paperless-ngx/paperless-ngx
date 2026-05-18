import { provideHttpClient, withInterceptorsFromDi } from '@angular/common/http'
import { provideHttpClientTesting } from '@angular/common/http/testing'
import {
  ComponentFixture,
  TestBed,
  fakeAsync,
  tick,
} from '@angular/core/testing'
import { By } from '@angular/platform-browser'
import { RouterTestingModule } from '@angular/router/testing'
import { NgxBootstrapIconsModule, allIcons } from 'ngx-bootstrap-icons'
import { provideUiTour } from 'ngx-ui-tour-ng-bootstrap'
import { routes } from 'src/app/app-routing.module'
import { PermissionsGuard } from 'src/app/guards/permissions.guard'
import { PermissionsService } from 'src/app/services/permissions.service'
import { UploadDocumentsService } from 'src/app/services/upload-documents.service'
import {
  FileStatus,
  FileStatusPhase,
  WebsocketStatusService,
} from 'src/app/services/websocket-status.service'
import { UploadFileWidgetComponent } from './upload-file-widget.component'

const FAILED_STATUSES = [new FileStatus()]
const WORKING_STATUSES = [new FileStatus(), new FileStatus()]
const STARTED_STATUSES = [new FileStatus(), new FileStatus(), new FileStatus()]
const SUCCESS_STATUSES = [
  new FileStatus(),
  new FileStatus(),
  new FileStatus(),
  new FileStatus(),
]
const DEFAULT_STATUSES = [
  new FileStatus(),
  new FileStatus(),
  new FileStatus(),
  new FileStatus(),
  new FileStatus(),
  new FileStatus(),
]

describe('UploadFileWidgetComponent', () => {
  let component: UploadFileWidgetComponent
  let fixture: ComponentFixture<UploadFileWidgetComponent>
  let websocketStatusService: WebsocketStatusService
  let uploadDocumentsService: UploadDocumentsService

  beforeEach(async () => {
    TestBed.configureTestingModule({
      imports: [
        RouterTestingModule.withRoutes(routes),
        NgxBootstrapIconsModule.pick(allIcons),
        UploadFileWidgetComponent,
      ],
      providers: [
        PermissionsGuard,
        {
          provide: PermissionsService,
          useValue: {
            currentUserCan: () => true,
          },
        },
        provideHttpClient(withInterceptorsFromDi()),
        provideHttpClientTesting(),
        provideUiTour(),
      ],
    }).compileComponents()

    websocketStatusService = TestBed.inject(WebsocketStatusService)
    uploadDocumentsService = TestBed.inject(UploadDocumentsService)
    fixture = TestBed.createComponent(UploadFileWidgetComponent)
    component = fixture.componentInstance

    fixture.detectChanges()
  })

  it('should support browse files', () => {
    const fileInput = fixture.debugElement.query(By.css('input'))
    const clickSpy = jest.spyOn(fileInput.nativeElement, 'click')
    fixture.debugElement
      .query(By.css('button'))
      .nativeElement.dispatchEvent(new Event('click'))
    expect(clickSpy).toHaveBeenCalled()
  })

  it('should upload files', () => {
    const uploadSpy = jest.spyOn(uploadDocumentsService, 'uploadFile')
    const file = new File(
      [new Blob(['testing'], { type: 'application/pdf' })],
      'file.pdf'
    )
    const fileInput = fixture.debugElement.query(By.css('input'))
    jest.spyOn(fileInput.nativeElement, 'files', 'get').mockReturnValue({
      item: () => file,
      length: 1,
      [Symbol.iterator]: () => ({
        next: () => ({ done: false, value: file }),
      }),
    } as any)
    fileInput.nativeElement.dispatchEvent(new Event('change'))
    expect(uploadSpy).toHaveBeenCalled()
  })

  it('should generate stats summary', () => {
    mockConsumerStatuses(websocketStatusService)
    expect(component.getStatusSummary()).toEqual(
      'Processing: 6, Failed: 1, Added: 4'
    )
  })

  it('should report an upload progress summary', () => {
    mockConsumerStatuses(websocketStatusService)
    expect(component.getTotalUploadProgress()).toEqual(0.75)
  })

  it('should change color by status phase', () => {
    const processingStatus = new FileStatus()
    processingStatus.phase = FileStatusPhase.WORKING
    expect(component.getStatusColor(processingStatus)).toEqual('primary')
    processingStatus.phase = FileStatusPhase.UPLOADING
    expect(component.getStatusColor(processingStatus)).toEqual('primary')
    const failedStatus = new FileStatus()
    failedStatus.phase = FileStatusPhase.FAILED
    expect(component.getStatusColor(failedStatus)).toEqual('danger')
    const successStatus = new FileStatus()
    successStatus.phase = FileStatusPhase.SUCCESS
    expect(component.getStatusColor(successStatus)).toEqual('success')
  })

  it('should allow dismissing an alert', () => {
    const dismissSpy = jest.spyOn(websocketStatusService, 'dismiss')
    component.dismiss(new FileStatus())
    expect(dismissSpy).toHaveBeenCalled()
  })

  it('should allow dismissing completed alerts', fakeAsync(() => {
    mockConsumerStatuses(websocketStatusService)
    fixture.detectChanges()
    jest
      .spyOn(component, 'getStatusCompleted')
      .mockImplementation(() => SUCCESS_STATUSES)
    const dismissSpy = jest.spyOn(websocketStatusService, 'dismiss')
    component.dismissCompleted()
    tick(1000)
    fixture.detectChanges()
    expect(dismissSpy).toHaveBeenCalledTimes(4)
  }))
})

function mockConsumerStatuses(consumerStatusService) {
  const partialUpload1 = new FileStatus()
  partialUpload1.currentPhaseProgress = 50
  partialUpload1.currentPhaseMaxProgress = 50
  const partialUpload2 = new FileStatus()
  partialUpload2.currentPhaseProgress = 25
  partialUpload2.currentPhaseMaxProgress = 50
  jest
    .spyOn(consumerStatusService, 'getConsumerStatus')
    .mockImplementation((phase) => {
      switch (phase) {
        case FileStatusPhase.FAILED:
          return FAILED_STATUSES
        case FileStatusPhase.WORKING:
          return WORKING_STATUSES
        case FileStatusPhase.STARTED:
          return STARTED_STATUSES
        case FileStatusPhase.SUCCESS:
          return SUCCESS_STATUSES
        case FileStatusPhase.UPLOADING:
          return [partialUpload1, partialUpload2]
        default:
          return DEFAULT_STATUSES
      }
    })
  jest
    .spyOn(consumerStatusService, 'getConsumerStatusNotCompleted')
    .mockImplementation(() => {
      return DEFAULT_STATUSES
    })
}
