import {
  ComponentFixture,
  TestBed,
  fakeAsync,
  tick,
} from '@angular/core/testing'
import {
  NgbActiveModal,
  NgbModalModule,
  NgbPopoverModule,
} from '@ng-bootstrap/ng-bootstrap'
import { Clipboard, ClipboardModule } from '@angular/cdk/clipboard'
import { SystemStatusService } from 'src/app/services/system-status.service'
import { SystemStatusDialogComponent } from './system-status-dialog.component'
import { of } from 'rxjs'
import {
  PaperlessConnectionStatus,
  PaperlessInstallType,
  PaperlessSystemStatus,
} from 'src/app/data/system-status'
import { HttpClientTestingModule } from '@angular/common/http/testing'
import { NgxBootstrapIconsModule, allIcons } from 'ngx-bootstrap-icons'
import { NgxFilesizeModule } from 'ngx-filesize'

const status: PaperlessSystemStatus = {
  pngx_version: '2.4.3',
  server_os: 'macOS-14.1.1-arm64-arm-64bit',
  install_type: PaperlessInstallType.BareMetal,
  storage: { total: 494384795648, available: 13573525504 },
  database: {
    type: 'sqlite',
    url: '/paperless-ngx/data/db.sqlite3',
    status: PaperlessConnectionStatus.ERROR,
    error: null,
    migration_status: {
      latest_migration: 'socialaccount.0006_alter_socialaccount_extra_data',
      unapplied_migrations: [],
    },
  },
  tasks: {
    redis_url: 'redis://localhost:6379',
    redis_status: PaperlessConnectionStatus.ERROR,
    redis_error: 'Error 61 connecting to localhost:6379. Connection refused.',
    celery_status: PaperlessConnectionStatus.ERROR,
  },
}

describe('SystemStatusDialogComponent', () => {
  let component: SystemStatusDialogComponent
  let fixture: ComponentFixture<SystemStatusDialogComponent>
  let systemStatusService: SystemStatusService
  let clipboard: Clipboard
  let getStatusSpy

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [SystemStatusDialogComponent],
      providers: [NgbActiveModal],
      imports: [
        NgbModalModule,
        ClipboardModule,
        HttpClientTestingModule,
        NgxBootstrapIconsModule.pick(allIcons),
        NgxFilesizeModule,
        NgbPopoverModule,
      ],
    }).compileComponents()

    systemStatusService = TestBed.inject(SystemStatusService)
    getStatusSpy = jest
      .spyOn(systemStatusService, 'get')
      .mockReturnValue(of(status))
    fixture = TestBed.createComponent(SystemStatusDialogComponent)
    component = fixture.componentInstance
    clipboard = TestBed.inject(Clipboard)
    fixture.detectChanges()
  })

  it('should subscribe to system status service', () => {
    expect(getStatusSpy).toHaveBeenCalled()
    expect(component.status).toEqual(status)
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
      JSON.stringify(component.status)
    )
    expect(component.copied).toBeTruthy()
    tick(3000)
    expect(component.copied).toBeFalsy()
  }))
})
