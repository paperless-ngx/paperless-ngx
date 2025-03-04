import { Clipboard } from '@angular/cdk/clipboard'
import { provideHttpClient, withInterceptorsFromDi } from '@angular/common/http'
import { provideHttpClientTesting } from '@angular/common/http/testing'
import {
  ComponentFixture,
  TestBed,
  fakeAsync,
  tick,
} from '@angular/core/testing'
import { NgbActiveModal } from '@ng-bootstrap/ng-bootstrap'
import { NgxBootstrapIconsModule, allIcons } from 'ngx-bootstrap-icons'
import { of, throwError } from 'rxjs'
import { PaperlessTaskName } from 'src/app/data/paperless-task'
import {
  InstallType,
  SystemStatus,
  SystemStatusItemStatus,
} from 'src/app/data/system-status'
import { SystemStatusService } from 'src/app/services/system-status.service'
import { TasksService } from 'src/app/services/tasks.service'
import { ToastService } from 'src/app/services/toast.service'
import { SystemStatusDialogComponent } from './system-status-dialog.component'

const status: SystemStatus = {
  pngx_version: '2.4.3',
  server_os: 'macOS-14.1.1-arm64-arm-64bit',
  install_type: InstallType.BareMetal,
  storage: { total: 494384795648, available: 13573525504 },
  database: {
    type: 'sqlite',
    url: '/paperless-ngx/data/db.sqlite3',
    status: SystemStatusItemStatus.ERROR,
    error: null,
    migration_status: {
      latest_migration: 'socialaccount.0006_alter_socialaccount_extra_data',
      unapplied_migrations: [],
    },
  },
  tasks: {
    redis_url: 'redis://localhost:6379',
    redis_status: SystemStatusItemStatus.ERROR,
    redis_error: 'Error 61 connecting to localhost:6379. Connection refused.',
    celery_status: SystemStatusItemStatus.ERROR,
    celery_url: 'celery@localhost',
    celery_error: 'Error connecting to celery@localhost',
    index_status: SystemStatusItemStatus.OK,
    index_last_modified: new Date().toISOString(),
    index_error: null,
    classifier_status: SystemStatusItemStatus.OK,
    classifier_last_trained: new Date().toISOString(),
    classifier_error: null,
    sanity_check_status: SystemStatusItemStatus.OK,
    sanity_check_last_run: new Date().toISOString(),
    sanity_check_error: null,
  },
}

describe('SystemStatusDialogComponent', () => {
  let component: SystemStatusDialogComponent
  let fixture: ComponentFixture<SystemStatusDialogComponent>
  let clipboard: Clipboard
  let tasksService: TasksService
  let systemStatusService: SystemStatusService
  let toastService: ToastService

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [
        SystemStatusDialogComponent,
        NgxBootstrapIconsModule.pick(allIcons),
      ],
      providers: [
        NgbActiveModal,
        provideHttpClient(withInterceptorsFromDi()),
        provideHttpClientTesting(),
      ],
    }).compileComponents()

    fixture = TestBed.createComponent(SystemStatusDialogComponent)
    component = fixture.componentInstance
    component.status = status
    clipboard = TestBed.inject(Clipboard)
    tasksService = TestBed.inject(TasksService)
    systemStatusService = TestBed.inject(SystemStatusService)
    toastService = TestBed.inject(ToastService)
    fixture.detectChanges()
  })

  it('should close the active modal', () => {
    const closeSpy = jest.spyOn(component.activeModal, 'close')
    component.close()
    expect(closeSpy).toHaveBeenCalled()
  })

  it('should copy the system status to clipboard', fakeAsync(() => {
    jest.spyOn(clipboard, 'copy')
    component.copy()
    expect(clipboard.copy).toHaveBeenCalledWith(
      JSON.stringify(component.status, null, 4)
    )
    expect(component.copied).toBeTruthy()
    tick(3000)
    expect(component.copied).toBeFalsy()
  }))

  it('should calculate if date is stale', () => {
    const date = new Date()
    date.setHours(date.getHours() - 25)
    expect(component.isStale(date.toISOString())).toBeTruthy()
    expect(component.isStale(date.toISOString(), 26)).toBeFalsy()
  })

  it('should check if task is running', () => {
    component.runTask(PaperlessTaskName.IndexOptimize)
    expect(component.isRunning(PaperlessTaskName.IndexOptimize)).toBeTruthy()
    expect(component.isRunning(PaperlessTaskName.SanityCheck)).toBeFalsy()
  })

  it('should support running tasks, refresh status and show toasts', () => {
    const toastSpy = jest.spyOn(toastService, 'showInfo')
    const toastErrorSpy = jest.spyOn(toastService, 'showError')
    const getStatusSpy = jest.spyOn(systemStatusService, 'get')
    const runSpy = jest.spyOn(tasksService, 'run')

    // fail first
    runSpy.mockReturnValue(throwError(() => new Error('error')))
    component.runTask(PaperlessTaskName.IndexOptimize)
    expect(runSpy).toHaveBeenCalledWith(PaperlessTaskName.IndexOptimize)
    expect(toastErrorSpy).toHaveBeenCalledWith(
      `Failed to start task ${PaperlessTaskName.IndexOptimize}, see the logs for more details`,
      expect.any(Error)
    )

    // succeed
    runSpy.mockReturnValue(of({}))
    getStatusSpy.mockReturnValue(of(status))
    component.runTask(PaperlessTaskName.IndexOptimize)
    expect(runSpy).toHaveBeenCalledWith(PaperlessTaskName.IndexOptimize)

    expect(getStatusSpy).toHaveBeenCalled()
    expect(toastSpy).toHaveBeenCalledWith(
      `Task ${PaperlessTaskName.IndexOptimize} started`
    )
  })
})
