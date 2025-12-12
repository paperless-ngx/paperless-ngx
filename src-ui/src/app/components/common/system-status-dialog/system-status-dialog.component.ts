import { Clipboard, ClipboardModule } from '@angular/cdk/clipboard'
import { Component, OnDestroy, OnInit, inject } from '@angular/core'
import {
  NgbActiveModal,
  NgbModalModule,
  NgbPopoverModule,
  NgbProgressbarModule,
} from '@ng-bootstrap/ng-bootstrap'
import { NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import { Subject, takeUntil } from 'rxjs'
import { PaperlessTaskName } from 'src/app/data/paperless-task'
import {
  SystemStatus,
  SystemStatusItemStatus,
} from 'src/app/data/system-status'
import { SETTINGS_KEYS } from 'src/app/data/ui-settings'
import { CustomDatePipe } from 'src/app/pipes/custom-date.pipe'
import { FileSizePipe } from 'src/app/pipes/file-size.pipe'
import { PermissionsService } from 'src/app/services/permissions.service'
import { SettingsService } from 'src/app/services/settings.service'
import { SystemStatusService } from 'src/app/services/system-status.service'
import { TasksService } from 'src/app/services/tasks.service'
import { ToastService } from 'src/app/services/toast.service'
import { WebsocketStatusService } from 'src/app/services/websocket-status.service'
import { environment } from 'src/environments/environment'

@Component({
  selector: 'pngx-system-status-dialog',
  templateUrl: './system-status-dialog.component.html',
  styleUrl: './system-status-dialog.component.scss',
  imports: [
    NgbModalModule,
    ClipboardModule,
    NgbPopoverModule,
    NgbProgressbarModule,
    CustomDatePipe,
    FileSizePipe,
    NgxBootstrapIconsModule,
  ],
})
export class SystemStatusDialogComponent implements OnInit, OnDestroy {
  activeModal = inject(NgbActiveModal)
  private clipboard = inject(Clipboard)
  private systemStatusService = inject(SystemStatusService)
  private tasksService = inject(TasksService)
  private toastService = inject(ToastService)
  private permissionsService = inject(PermissionsService)
  private websocketStatusService = inject(WebsocketStatusService)
  private settingsService = inject(SettingsService)

  public SystemStatusItemStatus = SystemStatusItemStatus
  public PaperlessTaskName = PaperlessTaskName
  public status: SystemStatus
  public frontendVersion: string = environment.version
  public versionMismatch: boolean = false

  public copied: boolean = false

  private runningTasks: Set<PaperlessTaskName> = new Set()
  private unsubscribeNotifier: Subject<any> = new Subject()

  get currentUserIsSuperUser(): boolean {
    return this.permissionsService.isSuperUser()
  }

  get aiEnabled(): boolean {
    return this.settingsService.get(SETTINGS_KEYS.AI_ENABLED)
  }

  public ngOnInit() {
    this.versionMismatch =
      environment.production &&
      this.status.pngx_version &&
      this.frontendVersion &&
      this.status.pngx_version !== this.frontendVersion
    if (this.versionMismatch) {
      this.status.pngx_version = `${this.status.pngx_version} (frontend: ${this.frontendVersion})`
    }
    this.status.websocket_connected = this.websocketStatusService.isConnected()
      ? SystemStatusItemStatus.OK
      : SystemStatusItemStatus.ERROR
    this.websocketStatusService
      .onConnectionStatus()
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe((connected) => {
        this.status.websocket_connected = connected
          ? SystemStatusItemStatus.OK
          : SystemStatusItemStatus.ERROR
      })
  }

  public close() {
    this.activeModal.close()
  }

  public copy() {
    this.clipboard.copy(JSON.stringify(this.status, null, 4))
    this.copied = true
    setTimeout(() => {
      this.copied = false
    }, 3000)
  }

  public isStale(dateStr: string, hours: number = 24): boolean {
    const date = new Date(dateStr)
    const now = new Date()
    return now.getTime() - date.getTime() > hours * 60 * 60 * 1000
  }

  public isRunning(taskName: PaperlessTaskName): boolean {
    return this.runningTasks.has(taskName)
  }

  public runTask(taskName: PaperlessTaskName) {
    this.runningTasks.add(taskName)
    this.toastService.showInfo(`Task ${taskName} started`)
    this.tasksService.run(taskName).subscribe({
      next: () => {
        this.runningTasks.delete(taskName)
        this.systemStatusService.get().subscribe({
          next: (status) => {
            Object.assign(this.status, status)
          },
        })
      },
      error: (err) => {
        this.runningTasks.delete(taskName)
        this.toastService.showError(
          `Failed to start task ${taskName}, see the logs for more details`,
          err
        )
      },
    })
  }

  ngOnDestroy(): void {
    this.unsubscribeNotifier.next(this)
    this.unsubscribeNotifier.complete()
  }
}
