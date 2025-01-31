import { Clipboard } from '@angular/cdk/clipboard'
import { provideHttpClient, withInterceptorsFromDi } from '@angular/common/http'
import { provideHttpClientTesting } from '@angular/common/http/testing'
import {
  ComponentFixture,
  TestBed,
  discardPeriodicTasks,
  fakeAsync,
  flush,
  tick,
} from '@angular/core/testing'
import { By } from '@angular/platform-browser'
import { RouterModule } from '@angular/router'
import { NgbAlert, NgbCollapse } from '@ng-bootstrap/ng-bootstrap'
import { NgxBootstrapIconsModule, allIcons } from 'ngx-bootstrap-icons'
import { of } from 'rxjs'
import { routes } from 'src/app/app-routing.module'
import {
  ConsumerStatusService,
  FileStatus,
  FileStatusPhase,
} from 'src/app/services/consumer-status.service'
import { ToastService } from 'src/app/services/toast.service'
import { UploadDocumentsService } from 'src/app/services/upload-documents.service'
import { NotificationsComponent } from './notifications.component'

const toasts = [
  {
    content: 'foo bar',
    delay: 5000,
  },
  {
    content: 'Error 1 content',
    delay: 5000,
    error: 'Error 1 string',
  },
  {
    content: 'Error 2 content',
    delay: 5000,
    error: {
      url: 'https://example.com',
      status: 500,
      statusText: 'Internal Server Error',
      message: 'Internal server error 500 message',
      error: { detail: 'Error 2 message details' },
    },
  },
]

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

describe('NotificationsComponent', () => {
  let component: NotificationsComponent
  let fixture: ComponentFixture<NotificationsComponent>
  let toastService: ToastService
  let clipboard: Clipboard
  let consumerStatusService: ConsumerStatusService
  let uploadDocumentsService: UploadDocumentsService

  beforeEach(async () => {
    TestBed.configureTestingModule({
      imports: [
        NotificationsComponent,
        NgxBootstrapIconsModule.pick(allIcons),
        RouterModule.forRoot(routes),
      ],
      providers: [
        {
          provide: ToastService,
          useValue: {
            getToasts: () => of(toasts),
          },
        },
        provideHttpClient(withInterceptorsFromDi()),
        provideHttpClientTesting(),
      ],
    }).compileComponents()

    fixture = TestBed.createComponent(NotificationsComponent)
    toastService = TestBed.inject(ToastService)
    consumerStatusService = TestBed.inject(ConsumerStatusService)
    uploadDocumentsService = TestBed.inject(UploadDocumentsService)
    clipboard = TestBed.inject(Clipboard)

    component = fixture.componentInstance

    fixture.detectChanges()
  })

  it('should call getToasts and return toasts', fakeAsync(() => {
    const spy = jest.spyOn(toastService, 'getToasts')

    component.ngOnInit()
    fixture.detectChanges()

    expect(spy).toHaveBeenCalled()
    expect(component.toasts).toContainEqual({
      content: 'foo bar',
      delay: 5000,
    })

    component.ngOnDestroy()
    flush()
    discardPeriodicTasks()
  }))

  it('should show a toast', fakeAsync(() => {
    component.ngOnInit()
    fixture.detectChanges()

    expect(fixture.nativeElement.textContent).toContain('foo bar')

    component.ngOnDestroy()
    flush()
    discardPeriodicTasks()
  }))

  it('should countdown toast', fakeAsync(() => {
    component.ngOnInit()
    fixture.detectChanges()
    component.onShow(toasts[0])
    tick(5000)
    expect(component.toasts[0].delayRemaining).toEqual(0)
    component.ngOnDestroy()
    flush()
    discardPeriodicTasks()
  }))

  it('should show an error if given with toast', fakeAsync(() => {
    component.ngOnInit()
    fixture.detectChanges()

    expect(fixture.nativeElement.querySelector('details')).not.toBeNull()
    expect(fixture.nativeElement.textContent).toContain('Error 1 content')

    component.ngOnDestroy()
    flush()
    discardPeriodicTasks()
  }))

  it('should show error details, support copy', fakeAsync(() => {
    component.ngOnInit()
    fixture.detectChanges()

    expect(fixture.nativeElement.querySelector('details')).not.toBeNull()
    expect(fixture.nativeElement.textContent).toContain(
      'Error 2 message details'
    )

    const copySpy = jest.spyOn(clipboard, 'copy')
    component.copyError(toasts[2].error)
    expect(copySpy).toHaveBeenCalled()

    component.ngOnDestroy()
    flush()
    discardPeriodicTasks()
  }))

  it('should parse error text, add ellipsis', () => {
    expect(component.getErrorText(toasts[2].error)).toEqual(
      'Error 2 message details'
    )
    expect(component.getErrorText({ error: 'Error string no detail' })).toEqual(
      'Error string no detail'
    )
    expect(component.getErrorText('Error string')).toEqual('')
    expect(
      component.getErrorText({ error: { message: 'foo error bar' } })
    ).toContain('{"message":"foo error bar"}')
    expect(
      component.getErrorText({ error: new Array(205).join('a') })
    ).toContain('...')
  })

  it('should generate stats summary', () => {
    mockConsumerStatuses(consumerStatusService)
    expect(component.getStatusSummary()).toEqual(
      'Processing: 6, Failed: 1, Added: 4'
    )
  })

  it('should report an upload progress summary', () => {
    mockConsumerStatuses(consumerStatusService)
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

  it('should enforce a maximum number of alerts', () => {
    mockConsumerStatuses(consumerStatusService)
    fixture.detectChanges()
    // 5 total, 1 hidden
    expect(fixture.debugElement.queryAll(By.directive(NgbAlert))).toHaveLength(
      6
    )
    expect(
      fixture.debugElement
        .query(By.directive(NgbCollapse))
        .queryAll(By.directive(NgbAlert))
    ).toHaveLength(1)
  })

  it('should allow dismissing an alert', () => {
    const dismissSpy = jest.spyOn(consumerStatusService, 'dismiss')
    component.dismiss(new FileStatus())
    expect(dismissSpy).toHaveBeenCalled()
  })

  it('should allow dismissing completed alerts', fakeAsync(() => {
    mockConsumerStatuses(consumerStatusService)
    component.alertsExpanded = true
    fixture.detectChanges()
    jest
      .spyOn(component, 'getStatusCompleted')
      .mockImplementation(() => SUCCESS_STATUSES)
    const dismissSpy = jest.spyOn(consumerStatusService, 'dismiss')
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
