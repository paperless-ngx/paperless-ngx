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
  private statusSignal = signal<SystemStatus>(undefined)
  public frontendVersion: string = environment.version
  private versionMismatchSignal = signal(false)

  private copiedSignal = signal(false)

  private runningTasksSignal = signal<Set<PaperlessTaskType>>(new Set())
  private unsubscribeNotifier: Subject<any> = new Subject()

  @Input()
  get status(): SystemStatus {
    return this.statusSignal()
  }

  set status(status: SystemStatus) {
    this.statusSignal.set(status)
  }

  get versionMismatch(): boolean {
    return this.versionMismatchSignal()
  }

  set versionMismatch(versionMismatch: boolean) {
    this.versionMismatchSignal.set(versionMismatch)
  }

  get copied(): boolean {
    return this.copiedSignal()
  }

  set copied(copied: boolean) {
    this.copiedSignal.set(copied)
  }

  get currentUserIsSuperUser(): boolean {
    return this.permissionsService.isSuperUser()
  }

  get aiEnabled(): boolean {
    return this.settingsService.get(SETTINGS_KEYS.AI_ENABLED)
  }

  public ngOnInit() {
    const status = this.status
    this.versionMismatch =
      environment.production &&
      status.pngx_version &&
      this.frontendVersion &&
      status.pngx_version !== this.frontendVersion
    if (this.versionMismatch) {
      this.status = {
        ...status,
        pngx_version: `${status.pngx_version} (frontend: ${this.frontendVersion})`,
      }
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

  public isRunning(taskName: PaperlessTaskType): boolean {
    return this.runningTasksSignal().has(taskName)
  }

  public runTask(taskName: PaperlessTaskType) {
    this.setTaskRunning(taskName, true)
    this.toastService.showInfo(`Task ${taskName} started`)
    this.tasksService.run(taskName).subscribe({
      next: () => {
        this.setTaskRunning(taskName, false)
        this.systemStatusService.get().subscribe({
          next: (status) => {
            this.status = {
              ...this.status,
              ...status,
            }
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
    this.status = {
      ...this.status,
      websocket_connected: connected
        ? SystemStatusItemStatus.OK
        : SystemStatusItemStatus.ERROR,
    }
  }

  private setTaskRunning(taskName: PaperlessTaskType, running: boolean): void {
    const runningTasks = new Set(this.runningTasksSignal())
    if (running) {
      runningTasks.add(taskName)
    } else {
      runningTasks.delete(taskName)
    }
    this.runningTasksSignal.set(runningTasks)
  }

  ngOnDestroy(): void {
    this.unsubscribeNotifier.next(this)
    this.unsubscribeNotifier.complete()
  }
}
