import { DatePipe } from '@angular/common'
import { provideHttpClient, withInterceptorsFromDi } from '@angular/common/http'
import {
  HttpTestingController,
  provideHttpClientTesting,
} from '@angular/common/http/testing'
import { ComponentFixture, TestBed } from '@angular/core/testing'
import { NgbModule } from '@ng-bootstrap/ng-bootstrap'
import { SimpleChange } from '@angular/core'
import { NgxBootstrapIconsModule, allIcons } from 'ngx-bootstrap-icons'
import { ExportRecord, ExportRecordStatus } from 'src/app/data/export-record'
import { ExportTargetKind } from 'src/app/data/export-target'
import {
  PermissionAction,
  PermissionsService,
} from 'src/app/services/permissions.service'
import { ToastService } from 'src/app/services/toast.service'
import { environment } from 'src/environments/environment'
import { DocumentExportDropdownComponent } from './document-export-dropdown.component'

const records: ExportRecord[] = [
  {
    id: 1,
    target: 1,
    target_name: 'Bucket',
    document: 12,
    document_pk: 12,
    status: ExportRecordStatus.Complete,
    object_key: '0000012_invoice.pdf',
    checksum: 'abc',
    created_at: '2026-08-18T00:00:00Z',
  },
  {
    id: 2,
    target: 1,
    target_name: 'Bucket',
    document: 12,
    document_pk: 12,
    status: ExportRecordStatus.Failed,
    object_key: '',
    checksum: '',
    created_at: '2026-08-18T01:00:00Z',
    last_error: { error: 'AccessDenied', attempt: 4 },
  },
]

describe('DocumentExportDropdownComponent', () => {
  let component: DocumentExportDropdownComponent
  let fixture: ComponentFixture<DocumentExportDropdownComponent>
  let httpController: HttpTestingController
  let permissionsService: PermissionsService
  let toastService: ToastService

  beforeEach(async () => {
    TestBed.configureTestingModule({
      imports: [
        NgbModule,
        NgxBootstrapIconsModule.pick(allIcons),
        DocumentExportDropdownComponent,
      ],
      providers: [
        DatePipe,
        provideHttpClient(withInterceptorsFromDi()),
        provideHttpClientTesting(),
      ],
    }).compileComponents()

    httpController = TestBed.inject(HttpTestingController)
    permissionsService = TestBed.inject(PermissionsService)
    toastService = TestBed.inject(ToastService)
    jest.spyOn(permissionsService, 'currentUserCan').mockReturnValue(true)

    fixture = TestBed.createComponent(DocumentExportDropdownComponent)
    component = fixture.componentInstance
    component.documentId = 12
    component.ngOnChanges({
      documentId: new SimpleChange(undefined, 12, true),
    })
    httpController
      .expectOne(`${environment.apiBaseUrl}documents/12/exports/`)
      .flush(records)
    fixture.detectChanges()
  })

  it('should load records and show count badge', () => {
    expect(component.records()).toHaveLength(2)
    expect(fixture.nativeElement.textContent).toContain('2')
  })

  it('should load enabled targets on open', () => {
    component.onOpenChange(true)
    httpController
      .expectOne(
        `${environment.apiBaseUrl}export_targets/?page=1&page_size=100000`
      )
      .flush({
        count: 2,
        results: [
          {
            id: 1,
            name: 'Bucket',
            kind: ExportTargetKind.S3,
            config: {},
            enabled: true,
          },
          {
            id: 2,
            name: 'Paused',
            kind: ExportTargetKind.Local,
            config: {},
            enabled: false,
          },
        ],
      })
    expect(component.targets()).toHaveLength(1)
    expect(component.targets()[0].name).toEqual('Bucket')
  })

  it('should export now and prepend the new record', () => {
    const toastSpy = jest.spyOn(toastService, 'showInfo')
    component.exportNow({
      id: 1,
      name: 'Bucket',
      kind: ExportTargetKind.S3,
      config: {},
      enabled: true,
    })
    httpController
      .expectOne(`${environment.apiBaseUrl}documents/12/exports/`)
      .flush({
        id: 3,
        target: 1,
        target_name: 'Bucket',
        document: 12,
        document_pk: 12,
        status: ExportRecordStatus.Pending,
        object_key: '',
        checksum: '',
        created_at: '2026-08-18T02:00:00Z',
      })
    expect(toastSpy).toHaveBeenCalled()
    expect(component.records()).toHaveLength(3)
    expect(component.records()[0].id).toEqual(3)
  })

  it('should show export errors', () => {
    const toastSpy = jest.spyOn(toastService, 'showError')
    component.exportNow({
      id: 1,
      name: 'Bucket',
      kind: ExportTargetKind.S3,
      config: {},
      enabled: true,
    })
    httpController
      .expectOne(`${environment.apiBaseUrl}documents/12/exports/`)
      .flush({}, { status: 400, statusText: 'error' })
    expect(toastSpy).toHaveBeenCalled()
  })

  it('should offer export now only with both target and record permissions', () => {
    // Mirrors the API, which needs view_exporttarget *and* add_exportrecord
    jest
      .spyOn(permissionsService, 'currentUserCan')
      .mockImplementation((action) => action === PermissionAction.View)
    expect(component.canExportNow).toBeFalsy()

    jest.spyOn(permissionsService, 'currentUserCan').mockReturnValue(true)
    expect(component.canExportNow).toBeTruthy()
  })

  it('should retry a failed export and replace the record in place', () => {
    const toastSpy = jest.spyOn(toastService, 'showInfo')
    component.retry(records[1])
    expect(component.retryingRecordId()).toEqual(2)
    httpController
      .expectOne(`${environment.apiBaseUrl}documents/12/exports/2/retry/`)
      .flush({
        ...records[1],
        status: ExportRecordStatus.Pending,
        last_error: null,
      })
    expect(toastSpy).toHaveBeenCalled()
    expect(component.retryingRecordId()).toBeNull()
    expect(component.records()).toHaveLength(2)
    expect(component.records()[1].status).toEqual(ExportRecordStatus.Pending)
  })

  it('should show retry errors', () => {
    const toastSpy = jest.spyOn(toastService, 'showError')
    component.retry(records[1])
    httpController
      .expectOne(`${environment.apiBaseUrl}documents/12/exports/2/retry/`)
      .flush({}, { status: 400, statusText: 'error' })
    expect(toastSpy).toHaveBeenCalled()
    expect(component.retryingRecordId()).toBeNull()
  })

  it('should copy the object key', () => {
    jest.useFakeTimers()
    const writeText = jest.fn()
    Object.defineProperty(document, 'execCommand', { value: jest.fn() })
    component.copyObjectKey(records[0])
    expect(component.copiedRecordId()).toEqual(1)
    jest.advanceTimersByTime(4000)
    expect(component.copiedRecordId()).toBeNull()
    jest.useRealTimers()
  })
})
