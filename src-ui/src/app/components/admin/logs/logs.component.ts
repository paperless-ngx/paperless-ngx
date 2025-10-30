import {
  ChangeDetectorRef,
  Component,
  ElementRef,
  OnDestroy,
  OnInit,
  ViewChild,
  inject,
} from '@angular/core'
import { FormsModule, ReactiveFormsModule } from '@angular/forms'
import { NgbNavModule } from '@ng-bootstrap/ng-bootstrap'
import { CommonModule } from '@angular/common'
import { ScrollingModule, CdkVirtualScrollViewport } from '@angular/cdk/scrolling'
import { filter, takeUntil, timer } from 'rxjs'
import { LogService } from 'src/app/services/rest/log.service'
import { PageHeaderComponent } from '../../common/page-header/page-header.component'
import { LoadingComponentWithPermissions } from '../../loading-component/loading.component'

@Component({
  selector: 'pngx-logs',
  templateUrl: './logs.component.html',
  styleUrls: ['./logs.component.scss'],
  imports: [
    CommonModule,
    PageHeaderComponent,
    NgbNavModule,
    FormsModule,
    ReactiveFormsModule,
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
      .get(this.activeLog, { tail: 1000 })
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe({
        next: (result) => {
          this.logs = this.parseLogsWithLevel(result)
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

  private parseLogsWithLevel(logs: string[]): Array<{ message: string; level: number }> {
    return logs.map(log => ({
      message: log,
      level: this.getLogLevel(log)
    }))
  }

  trackByIndex(index: number): number {
    return index
  }

  scrollToBottom(): void {
    this.changedetectorRef.detectChanges()
    if (this.logContainer && this.logContainer.elementRef?.nativeElement) {
      try {
        this.logContainer.scrollToIndex(this.logs.length - 1)
      } catch (e) {
        // Ignore errors in tests or when element is not ready
      }
    }
  }
}
