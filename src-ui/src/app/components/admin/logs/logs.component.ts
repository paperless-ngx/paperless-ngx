import {
  ChangeDetectorRef,
  Component,
  ElementRef,
  OnDestroy,
  OnInit,
  ViewChild,
} from '@angular/core'
import { filter, takeUntil, timer } from 'rxjs'
import { LogService } from 'src/app/services/rest/log.service'
import { LoadingComponentWithPermissions } from '../../loading-component/loading.component'

@Component({
  selector: 'pngx-logs',
  templateUrl: './logs.component.html',
  styleUrls: ['./logs.component.scss'],
})
export class LogsComponent
  extends LoadingComponentWithPermissions
  implements OnInit, OnDestroy
{
  constructor(
    private logService: LogService,
    private changedetectorRef: ChangeDetectorRef
  ) {
    super()
  }

  public logs: string[] = []

  public logFiles: string[] = []

  public activeLog: string

  public autoRefreshEnabled: boolean = true

  @ViewChild('logContainer') logContainer: ElementRef

  ngOnInit(): void {
    this.logService
      .list()
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe((result) => {
        this.logFiles = result
        this.loading = false
        if (this.logFiles.length > 0) {
          this.activeLog = this.logFiles[0]
          this.reloadLogs()
        }
        timer(5000, 5000)
          .pipe(
            filter(() => this.autoRefreshEnabled),
            takeUntil(this.unsubscribeNotifier)
          )
          .subscribe(() => {
            this.reloadLogs()
          })
      })
  }

  ngOnDestroy(): void {
    super.ngOnDestroy()
  }

  reloadLogs() {
    this.loading = true
    this.logService
      .get(this.activeLog)
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe({
        next: (result) => {
          this.logs = result
          this.loading = false
          this.scrollToBottom()
        },
        error: () => {
          this.logs = []
          this.loading = false
        },
      })
  }

  getLogLevel(log: string) {
    if (log.indexOf('[DEBUG]') != -1) {
      return 10
    } else if (log.indexOf('[WARNING]') != -1) {
      return 30
    } else if (log.indexOf('[ERROR]') != -1) {
      return 40
    } else if (log.indexOf('[CRITICAL]') != -1) {
      return 50
    } else {
      return 20
    }
  }

  scrollToBottom(): void {
    this.changedetectorRef.detectChanges()
    this.logContainer?.nativeElement.scroll({
      top: this.logContainer.nativeElement.scrollHeight,
      left: 0,
      behavior: 'auto',
    })
  }
}
