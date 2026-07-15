import { Clipboard, ClipboardModule } from '@angular/cdk/clipboard'
import {
  Component,
  Input,
  OnDestroy,
  OnInit,
  inject,
  signal,
} from '@angular/core'
import {
  NgbActiveModal,
  NgbModalModule,
  NgbPopoverModule,
  NgbProgressbarModule,
} from '@ng-bootstrap/ng-bootstrap'
import { NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import { Subject, takeUntil } from 'rxjs'
import { PaperlessTaskType } from 'src/app/data/paperless-task'
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
  public PaperlessTaskType = PaperlessTaskType
  @Input() status = signal<SystemStatus>(undefined)
  public frontendVersion: string = environment.version
  readonly versionMismatch = signal(false)
  readonly copied = signal(false)
  readonly runningTasks = signal<Set<PaperlessTaskType>>(new Set())
  private unsubscribeNotifier: Subject<any> = new Subject()

  get currentUserIsSuperUser(): boolean {
    return this.permissionsService.isSuperUser()
  }

  get aiEnabled(): boolean {
    return this.settingsService.get(SETTINGS_KEYS.AI_ENABLED)
  }

  public ngOnInit() {
    const status = this.status()
    this.versionMismatch.set(
      environment.production &&
        status.pngx_version &&
        this.frontendVersion &&
        status.pngx_version !== this.frontendVersion
    )
    if (this.versionMismatch()) {
      this.status.set({
        ...status,
        pngx_version: `${status.pngx_version} (frontend: ${this.frontendVersion})`,
      })
    }
    this.updateWebsocketStatus(this.websocketStatusService.isConnected())
    this.websocketStatusService
      .onConnectionStatus()
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe((connected) => this.updateWebsocketStatus(connected))
  }

  public close() {
    this.activeModal.close()
  }

  public copy() {
    this.clipboard.copy(JSON.stringify(this.status(), null, 4))
    this.copied.set(true)
    setTimeout(() => {
      this.copied.set(false)
    }, 3000)
  }

  public isStale(dateStr: string, hours: number = 24): boolean {
    const date = new Date(dateStr)
    const now = new Date()
    return now.getTime() - date.getTime() > hours * 60 * 60 * 1000
  }

  public isRunning(taskName: PaperlessTaskType): boolean {
    return this.runningTasks().has(taskName)
  }

  public runTask(taskName: PaperlessTaskType) {
    this.setTaskRunning(taskName, true)
    this.toastService.showInfo(`Task ${taskName} started`)
    this.tasksService.run(taskName).subscribe({
      next: () => {
        this.setTaskRunning(taskName, false)
        this.systemStatusService.get().subscribe({
          next: (statusUpdate) => {
            this.status.set({
              ...this.status(),
              ...statusUpdate,
            })
          },
        })
      },
      error: (err) => {
        this.setTaskRunning(taskName, false)
        this.toastService.showError(
          `Failed to start task ${taskName}, see the logs for more details`,
          err
        )
      },
    })
  }

  private updateWebsocketStatus(connected: boolean): void {
    this.status.set({
      ...this.status(),
      websocket_connected: connected
        ? SystemStatusItemStatus.OK
        : SystemStatusItemStatus.ERROR,
    })
  }

  private setTaskRunning(taskName: PaperlessTaskType, running: boolean): void {
    const runningTasks = new Set(this.runningTasks())
    if (running) {
      runningTasks.add(taskName)
    } else {
      runningTasks.delete(taskName)
    }
    this.runningTasks.set(runningTasks)
  }

  ngOnDestroy(): void {
    this.unsubscribeNotifier.next(this)
    this.unsubscribeNotifier.complete()
  }
}
