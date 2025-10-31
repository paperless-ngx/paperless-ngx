import {
  CdkVirtualScrollViewport,
  ScrollingModule,
} from '@angular/cdk/scrolling'
import { CommonModule } from '@angular/common'
import {
  ChangeDetectorRef,
  Component,
  OnDestroy,
  OnInit,
  ViewChild,
  inject,
} from '@angular/core'
import { FormsModule, ReactiveFormsModule } from '@angular/forms'
import { NgbNavModule } from '@ng-bootstrap/ng-bootstrap'
import { filter, takeUntil, timer } from 'rxjs'
import { LogService } from 'src/app/services/rest/log.service'
import { PageHeaderComponent } from '../../common/page-header/page-header.component'
import { LoadingComponentWithPermissions } from '../../loading-component/loading.component'

@Component({
  selector: 'pngx-logs',
  templateUrl: './logs.component.html',
  styleUrls: ['./logs.component.scss'],
  imports: [
    PageHeaderComponent,
    NgbNavModule,
    CommonModule,
    FormsModule,
    ReactiveFormsModule,
    CdkVirtualScrollViewport,
    ScrollingModule,
  ],
})
export class LogsComponent
  extends LoadingComponentWithPermissions
  implements OnInit, OnDestroy
{
  private logService = inject(LogService)
  private changedetectorRef = inject(ChangeDetectorRef)

  public logs: Array<{ message: string; level: number }> = []

  public logFiles: string[] = []

  public activeLog: string

  public autoRefreshEnabled: boolean = true

  public limit: number = 5000

  @ViewChild('logContainer') logContainer: CdkVirtualScrollViewport

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
      .get(this.activeLog, this.limit)
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe({
        next: (result) => {
          this.loading = false
          const parsed = this.parseLogsWithLevel(result)
          if (parsed.join('') !== this.logs.join('')) {
            this.logs = parsed
            this.scrollToBottom()
          }
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

  private parseLogsWithLevel(
    logs: string[]
  ): Array<{ message: string; level: number }> {
    return logs.map((log) => ({
      message: log,
      level: this.getLogLevel(log),
    }))
  }

  scrollToBottom(): void {
    this.changedetectorRef.detectChanges()
    if (this.logContainer) {
      this.logContainer.scrollToIndex(this.logs.length - 1)
    }
  }
}
