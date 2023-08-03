import { HttpClientTestingModule } from '@angular/common/http/testing'
import { ComponentFixture, TestBed } from '@angular/core/testing'
import { By } from '@angular/platform-browser'
import { RouterTestingModule } from '@angular/router/testing'
import {
  NgbModule,
  NgbAlertModule,
  NgbAlert,
  NgbCollapse,
} from '@ng-bootstrap/ng-bootstrap'
import { NgxFileDropModule } from 'ngx-file-drop'
import { routes } from 'src/app/app-routing.module'
import { IfPermissionsDirective } from 'src/app/directives/if-permissions.directive'
import { PermissionsGuard } from 'src/app/guards/permissions.guard'
import {
  ConsumerStatusService,
  FileStatus,
  FileStatusPhase,
} from 'src/app/services/consumer-status.service'
import { PermissionsService } from 'src/app/services/permissions.service'
import { UploadDocumentsService } from 'src/app/services/upload-documents.service'
import { WidgetFrameComponent } from '../widget-frame/widget-frame.component'
import { UploadFileWidgetComponent } from './upload-file-widget.component'

describe('UploadFileWidgetComponent', () => {
  let component: UploadFileWidgetComponent
  let fixture: ComponentFixture<UploadFileWidgetComponent>
  let consumerStatusService: ConsumerStatusService
  let uploadDocumentsService: UploadDocumentsService

  beforeEach(async () => {
    TestBed.configureTestingModule({
      declarations: [
        UploadFileWidgetComponent,
        WidgetFrameComponent,
        IfPermissionsDirective,
      ],
      providers: [
        PermissionsGuard,
        {
          provide: PermissionsService,
          useValue: {
            currentUserCan: () => true,
          },
        },
      ],
      imports: [
        HttpClientTestingModule,
        NgbModule,
        RouterTestingModule.withRoutes(routes),
        NgxFileDropModule,
        NgbAlertModule,
      ],
    }).compileComponents()

    consumerStatusService = TestBed.inject(ConsumerStatusService)
    uploadDocumentsService = TestBed.inject(UploadDocumentsService)
    fixture = TestBed.createComponent(UploadFileWidgetComponent)
    component = fixture.componentInstance

    fixture.detectChanges()
  })

  it('should support drop files', () => {
    const uploadSpy = jest.spyOn(uploadDocumentsService, 'uploadFiles')
    component.dropped([])
    expect(uploadSpy).toHaveBeenCalled()
    // coverage
    component.fileLeave(null)
    component.fileOver(null)
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

  it('should allow dismissing all alerts', () => {
    const dismissSpy = jest.spyOn(consumerStatusService, 'dismissCompleted')
    component.dismissCompleted()
    expect(dismissSpy).toHaveBeenCalled()
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
          return [new FileStatus()]
        case FileStatusPhase.WORKING:
          return [new FileStatus(), new FileStatus()]
        case FileStatusPhase.STARTED:
          return [new FileStatus(), new FileStatus(), new FileStatus()]
        case FileStatusPhase.SUCCESS:
          return [
            new FileStatus(),
            new FileStatus(),
            new FileStatus(),
            new FileStatus(),
          ]
        case FileStatusPhase.UPLOADING:
          return [partialUpload1, partialUpload2]
        default:
          return [
            new FileStatus(),
            new FileStatus(),
            new FileStatus(),
            new FileStatus(),
            new FileStatus(),
            new FileStatus(),
          ]
      }
    })
  jest
    .spyOn(consumerStatusService, 'getConsumerStatusNotCompleted')
    .mockImplementation(() => {
      return [
        new FileStatus(),
        new FileStatus(),
        new FileStatus(),
        new FileStatus(),
        new FileStatus(),
        new FileStatus(),
      ]
    })
}
