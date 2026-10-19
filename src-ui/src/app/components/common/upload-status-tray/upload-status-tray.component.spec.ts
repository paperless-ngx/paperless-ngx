import { provideHttpClient, withInterceptorsFromDi } from '@angular/common/http'
import { provideHttpClientTesting } from '@angular/common/http/testing'
import { ComponentFixture, TestBed } from '@angular/core/testing'
import { By } from '@angular/platform-browser'
import { RouterTestingModule } from '@angular/router/testing'
import { NgxBootstrapIconsModule, allIcons } from 'ngx-bootstrap-icons'
import { routes } from 'src/app/app-routing.module'
import { PermissionsGuard } from 'src/app/guards/permissions.guard'
import { PermissionsService } from 'src/app/services/permissions.service'
import {
  FileStatus,
  FileStatusPhase,
  WebsocketStatusService,
} from 'src/app/services/websocket-status.service'
import { UploadStatusTrayComponent } from './upload-status-tray.component'

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

describe('UploadStatusTrayComponent', () => {
  let component: UploadStatusTrayComponent
  let fixture: ComponentFixture<UploadStatusTrayComponent>
  let websocketStatusService: WebsocketStatusService

  beforeEach(async () => {
    TestBed.configureTestingModule({
      imports: [
        RouterTestingModule.withRoutes(routes),
        NgxBootstrapIconsModule.pick(allIcons),
        UploadStatusTrayComponent,
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
      ],
    }).compileComponents()

    websocketStatusService = TestBed.inject(WebsocketStatusService)
    fixture = TestBed.createComponent(UploadStatusTrayComponent)
    component = fixture.componentInstance

    fixture.detectChanges()
  })

  it('should not render without statuses', () => {
    expect(
      fixture.nativeElement.querySelector('.consumer-status-card')
    ).toBeNull()
  })

  it('should render statuses and support collapsing', () => {
    const status = new FileStatus()
    status.filename = 'invoice.pdf'
    status.phase = FileStatusPhase.WORKING
    jest
      .spyOn(websocketStatusService, 'getConsumerStatus')
      .mockReturnValue([status])
    // a mocked return value doesn't mark the zoneless view dirty, so re-create it
    fixture = TestBed.createComponent(UploadStatusTrayComponent)
    component = fixture.componentInstance
    fixture.detectChanges()
    const el: HTMLElement = fixture.nativeElement
    expect(el.querySelector('.consumer-status-card')).not.toBeNull()
    expect(el.textContent).toContain('invoice.pdf')

    component.toggleCollapsed()
    fixture.detectChanges()
    expect(el.querySelector('.consumer-status-card')).not.toBeNull()
    expect(el.textContent).not.toContain('invoice.pdf')

    component.toggleCollapsed()
    fixture.detectChanges()
    expect(el.textContent).toContain('invoice.pdf')
  })

  it('should expand again once all statuses are dismissed', () => {
    const status = websocketStatusService.newFileUpload('invoice.pdf')
    fixture.detectChanges()
    component.toggleCollapsed()
    expect(component.collapsed()).toBe(true)
    websocketStatusService.dismiss(status)
    fixture.detectChanges()
    expect(component.collapsed()).toBe(false)
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

  it('should allow dismissing completed alerts', () => {
    jest.useFakeTimers()
    mockConsumerStatuses(websocketStatusService)
    fixture.detectChanges()
    jest
      .spyOn(component, 'getStatusCompleted')
      .mockImplementation(() => SUCCESS_STATUSES)
    const dismissSpy = jest.spyOn(websocketStatusService, 'dismiss')
    component.dismissCompleted()
    jest.advanceTimersByTime(1000)
    fixture.detectChanges()
    expect(dismissSpy).toHaveBeenCalledTimes(4)
    jest.useRealTimers()
  })
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
